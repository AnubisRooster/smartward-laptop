/** Turning the architecture's Mermaid drawing into files: a standalone light SVG and a PNG drawn from it. */

/** Mermaid's SVG made to stand alone: a real width and height (it ships as width="100%" with a max-width style) and a white background,
 *  so it looks the same in any viewer, slide or page, whatever the app's theme. */
export function standaloneSvg(svg: string): { svg: string; width: number; height: number } {
  const vb = /viewBox="\s*([-\d.]+)[\s,]+([-\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)\s*"/.exec(svg);
  if (!vb) throw new Error('The drawing has no size.');
  const [x, y, width, height] = vb.slice(1).map(Number);
  const out = svg.replace(/<svg\b[^>]*>/, tag => {
    const t = tag.replace(/\s(width|height)="[^"]*"/g, '').replace(/\sstyle="[^"]*"/, '');
    return t.replace(/>$/, ` width="${Math.ceil(width)}" height="${Math.ceil(height)}"${/xmlns=/.test(t) ? '' : ' xmlns="http://www.w3.org/2000/svg"'}>`)
      + `<rect x="${x}" y="${y}" width="${width}" height="${height}" fill="#ffffff"/>`;
  });
  return { svg: out, width: Math.ceil(width), height: Math.ceil(height) };
}

/** The PNG's pixel size: twice the drawing for sharp slides, held under what browsers will draw into one canvas. */
export function pngSize(width: number, height: number, scale = 2, max = 8192): { width: number; height: number } {
  const s = Math.min(scale, max / Math.max(width, height));
  return { width: Math.round(width * s), height: Math.round(height * s) };
}

/** Draws Mermaid source in the light theme (whatever the app uses) and returns the standalone SVG. */
export async function lightSvg(src: string, id: string) {
  const { default: mermaid } = await import('mermaid');
  // Plain SVG text labels (Mermaid 12 reads htmlLabels at the top level): HTML labels would taint the PNG's canvas and break other SVG viewers.
  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'default', htmlLabels: false, flowchart: { htmlLabels: false, curve: 'basis' } } as any);
  const { svg } = await mermaid.render(id, src);
  if (svg.includes('<foreignObject')) throw new Error('The drawing still has HTML labels, so it can’t be saved as an image.');
  return standaloneSvg(svg);
}

export async function svgToPng(svg: string, width: number, height: number): Promise<Blob> {
  const size = pngSize(width, height);
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
  try {
    const img = new Image(); img.decoding = 'sync';
    await new Promise<void>((ok, fail) => { img.onload = () => ok(); img.onerror = () => fail(new Error('The drawing couldn’t be turned into an image.')); img.src = url; });
    const canvas = document.createElement('canvas'); canvas.width = size.width; canvas.height = size.height;
    const g = canvas.getContext('2d'); if (!g) throw new Error('This window can’t draw images.');
    g.fillStyle = '#ffffff'; g.fillRect(0, 0, size.width, size.height); g.drawImage(img, 0, 0, size.width, size.height);
    return await new Promise<Blob>((ok, fail) => canvas.toBlob(b => b ? ok(b) : fail(new Error('The image couldn’t be made.')), 'image/png'));
  } finally { URL.revokeObjectURL(url); }
}
