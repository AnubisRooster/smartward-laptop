"""A project's architecture map as files to take elsewhere: a draw.io diagram you can rearrange, clean Mermaid source and the map text.
The PNG and SVG are drawn by the browser (that is where Mermaid runs); this module only builds text formats."""
import os, re
from xml.sax.saxutils import quoteattr
from . import db, maps

FORMATS = {"drawio": (".drawio", "application/vnd.jgraph.mxfile"), "mermaid": (".mmd", "text/plain"), "text": (".txt", "text/plain")}

# draw.io shapes per part type, with a light fill so the file reads well on white
STYLE = {"actor": "shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;fillColor=#f5f5f5;strokeColor=#666666;",
         "app": "rounded=1;fillColor=#dae8fc;strokeColor=#6c8ebf;",
         "agent": "shape=hexagon;perimeter=hexagonPerimeter2;size=0.12;fillColor=#e1d5e7;strokeColor=#9673a6;",
         "service": "rounded=0;fillColor=#dae8fc;strokeColor=#6c8ebf;",
         "gateway": "shape=parallelogram;perimeter=parallelogramPerimeter;size=0.1;fillColor=#fff2cc;strokeColor=#d6b656;",
         "datastore": "shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=8;fillColor=#d5e8d4;strokeColor=#82b366;",
         "model": "shape=process;size=0.08;fillColor=#ffe6cc;strokeColor=#d79b00;",
         "external": "ellipse;shape=cloud;fillColor=#f5f5f5;strokeColor=#666666;",
         "infra": "shape=trapezoid;perimeter=trapezoidPerimeter;size=0.12;flipV=1;fillColor=#f8cecc;strokeColor=#b85450;"}
ZONE = "swimlane;startSize=26;rounded=1;dashed=1;fillColor=none;strokeColor=#888888;fontStyle=1;horizontal=1;"
W, H, GAP, PAD, PER_ROW = 160, 64, 40, 20, 4


def _depths(m):
    """How far down the request path each part sits (longest data path from a part nothing calls), so callers land above callees."""
    outs = {p["id"]: [] for p in m["parts"]}
    for e in m["edges"]: outs[e["a"]].append(e["b"])
    called = {e["b"] for e in m["edges"]}
    depth = {p["id"]: 0 for p in m["parts"]}
    frontier = [p["id"] for p in m["parts"] if p["id"] not in called] or [m["parts"][0]["id"]] if m["parts"] else []
    for _ in range(len(m["parts"])):           # bounded relaxation, so cycles can't loop forever
        nxt = []
        for a in frontier:
            for b in outs[a]:
                if depth[b] < depth[a] + 1 and depth[a] + 1 < len(m["parts"]): depth[b] = depth[a] + 1; nxt.append(b)
        if not nxt: break
        frontier = nxt
    return depth


def _layout(m):
    """Positions: zones side by side, parts in rows by depth inside each zone (wrapping long rows), unzoned parts in a row above."""
    depth, cells, x0 = _depths(m), {}, 0
    loose = [p for p in m["parts"] if not p["zone"]]
    for i, p in enumerate(loose): cells[p["id"]] = (None, i * (W + GAP), 0)
    top = (H + GAP * 2) if loose else 0
    zones = []
    for i, z in enumerate(m["zones"], 1):
        inside = sorted((p for p in m["parts"] if p["zone"] == z), key=lambda p: depth[p["id"]])
        if not inside: continue
        rows, row, last = [], [], None
        for p in inside:
            if row and (depth[p["id"]] != last or len(row) == PER_ROW): rows.append(row); row = []
            row.append(p); last = depth[p["id"]]
        rows.append(row)
        cols = max(len(r) for r in rows)
        w, h = PAD * 2 + cols * W + (cols - 1) * GAP, 26 + PAD * 2 + len(rows) * H + (len(rows) - 1) * GAP
        for r, rw in enumerate(rows):
            off = (cols - len(rw)) * (W + GAP) / 2       # centre short rows
            for c, p in enumerate(rw): cells[p["id"]] = (f"z{i}", PAD + off + c * (W + GAP), 26 + PAD + r * (H + GAP))
        zones.append((f"z{i}", z, x0, top, w, h)); x0 += w + GAP * 2
    return zones, cells


def drawio(m, title="Architecture"):
    """An uncompressed draw.io file: zones as containers, a shape per type, data arrows solid and control arrows dashed."""
    zones, cells = _layout(m)
    out = ['<mxfile host="SmartWard">', f'  <diagram name={quoteattr(title)} id="smartward-map">',
           '    <mxGraphModel grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" page="0">', '      <root>',
           '        <mxCell id="0" />', '        <mxCell id="1" parent="0" />']
    for zid, name, x, y, w, h in zones:
        out.append(f'        <mxCell id="{zid}" value={quoteattr(name)} style="{ZONE}" vertex="1" parent="1">'
                   f'<mxGeometry x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" as="geometry" /></mxCell>')
    for p in m["parts"]:
        parent, x, y = cells[p["id"]]
        style = "whiteSpace=wrap;html=0;" + STYLE[p["type"]] + ("dashed=1;" if p["suggested"] else "")
        note = f' tooltip={quoteattr(p["note"])}' if p["note"] else ""
        out.append(f'        <object id="{p["id"]}" label={quoteattr(p["label"])} type={quoteattr(p["type"])}{note}>'
                   f'<mxCell style="{style}" vertex="1" parent="{parent or 1}">'
                   f'<mxGeometry x="{x:.0f}" y="{y:.0f}" width="{W}" height="{H}" as="geometry" /></mxCell></object>')
    for i, e in enumerate(m["edges"], 1):
        lab = " · ".join(x for x in (e["verb"], e["protocol"]) if x)
        style = "edgeStyle=orthogonalEdgeStyle;rounded=1;html=0;endArrow=block;fontSize=10;labelBackgroundColor=#ffffff;" + ("dashed=1;" if e["kind"] == "control" else "")
        out.append(f'        <mxCell id="e{i}" value={quoteattr(lab)} style="{style}" edge="1" parent="1" source="{e["a"]}" target="{e["b"]}">'
                   '<mxGeometry relative="1" as="geometry" /></mxCell>')
    out += ['      </root>', '    </mxGraphModel>', '  </diagram>', '</mxfile>', '']
    return "\n".join(out)


def export(pid, fmt):
    """{filename, type, content} for a project's saved map in one of FORMATS."""
    if fmt not in FORMATS: raise ValueError("Format must be one of: " + ", ".join(FORMATS) + ".")
    saved = maps.get(pid)
    if not saved: raise LookupError("This project has no saved architecture yet.")
    name = (db.q("SELECT name FROM projects WHERE id=?", (pid,), one=True) or {}).get("name") or "Project"
    m = maps.parse(saved["text"])
    title = f"{name}: architecture"
    content = {"drawio": lambda: drawio(m, title),
               "mermaid": lambda: f"%% {title}\n" + maps.mermaid(m, {}) + "\n",     # no evidence counts or colours: the bare design
               "text": lambda: saved["text"].rstrip() + "\n"}[fmt]()
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if len(slug) > 40: slug = slug[:41].rsplit("-", 1)[0]          # whole words, short enough to read in a folder
    slug = slug or "project"
    ext, kind = FORMATS[fmt]
    return {"filename": f"{slug}-architecture{ext}", "type": kind, "content": content}


# ---------- saving a file the desktop window made (its web view doesn't do browser downloads) ----------
SAVE_TYPES = {".svg", ".png", ".drawio", ".mmd", ".txt", ".md", ".html", ".xml"}
SAVE_LIMIT = 20 * 1024 * 1024
DOWNLOADS = "~/Downloads"


def save_download(filename, data: bytes):
    """Writes into ~/Downloads under a safe, unused name and returns the path. Only plain names with a known extension are accepted."""
    base = os.path.basename(str(filename or "")).strip()
    base = re.sub(r"[^\w .()-]+", "-", base).strip(" .")[:120]
    stem, ext = os.path.splitext(base)
    if not stem or ext.lower() not in SAVE_TYPES: raise ValueError("That kind of file can't be saved here.")
    if len(data) > SAVE_LIMIT: raise ValueError("That file is too large.")
    folder = os.path.expanduser(DOWNLOADS); os.makedirs(folder, exist_ok=True)
    path, n = os.path.join(folder, base), 2
    while os.path.exists(path): path = os.path.join(folder, f"{stem} ({n}){ext}"); n += 1
    with open(path, "xb") as f: f.write(data)
    return path
