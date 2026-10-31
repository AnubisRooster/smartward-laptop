"""Running a small benchmark script so that it can measure, and nothing else.

The script runs under bubblewrap with no network at all, no home folder (so no library, keys or files of yours), a private /tmp, its own process
and user namespaces, and limits on memory, CPU time, file size and open files. It reaches the model server only by asking SmartWard: each request
is a line on its stdout, SmartWard's broker decides (approved model only, capped calls and lengths) and answers on its stdin. Its own prints go to a
log. The answer is one JSON result line; anything else is not a result."""
import json, os, queue, resource, shutil, subprocess, tempfile, threading, time

BWRAP = shutil.which("bwrap")
PYTHON = "/usr/bin/python3"
MAX_LOG = 32_000
MAX_RESULT = 20_000

HARNESS = r'''
import json, os, sys
_proto = os.fdopen(os.dup(1), "w"); sys.stdout = sys.stderr          # the script's prints go to the log, never into the protocol
class SmartWard:
    """What a bench script can do: ask the model server to generate (through SmartWard), and report one result."""
    def generate(self, model, prompt, **options):
        _proto.write("@@call " + json.dumps({"op": "generate", "model": model, "prompt": prompt, "options": options}) + "\n"); _proto.flush()
        line = sys.stdin.readline()
        if not line: raise SystemExit("SmartWard closed the connection")
        r = json.loads(line)
        if "error" in r: raise RuntimeError(r["error"])
        return r
    def result(self, **fields):
        _proto.write("@@result " + json.dumps(fields) + "\n"); _proto.flush()
    def log(self, *a): print(*a)
ns = {"__name__": "bench"}
exec(compile(open("/work/bench.py").read(), "bench.py", "exec"), ns)
ns["run"](SmartWard())
'''


class Refused(Exception):
    """The broker said no to a request; the script sees it as an error."""


def available(): return bool(BWRAP and os.path.exists(PYTHON))


def _limits(cpu_seconds, memory_mb):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 5))
        resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 2**20, memory_mb * 2**20))
        resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 2**20, 10 * 2**20))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return apply


def command(work):
    return [BWRAP, "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/bin", "/bin",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--ro-bind", work, "/work", "--chdir", "/tmp",
            "--unshare-all", "--die-with-parent", "--new-session", "--clearenv", "--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/tmp",
            PYTHON, "-I", "-S", "-B", "/work/harness.py"]


def run(script, broker, timeout=300, cpu_seconds=120, memory_mb=512):
    """Run a bench script. broker(request) -> dict (or raises Refused). Returns {"result", "log", "calls", "seconds", "error"}."""
    if not available(): return {"result": None, "log": "", "calls": 0, "seconds": 0, "error": "The sandbox (bubblewrap) isn't installed: sudo apt install bubblewrap"}
    work = tempfile.mkdtemp(prefix="sw-bench-")
    try:
        with open(os.path.join(work, "harness.py"), "w") as f: f.write(HARNESS)
        with open(os.path.join(work, "bench.py"), "w") as f: f.write(script)
        os.chmod(work, 0o755)
        p = subprocess.Popen(command(work), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
                             preexec_fn=_limits(cpu_seconds, memory_mb), close_fds=True)
        lines, log = queue.Queue(), []
        def pump_out():
            for line in p.stdout: lines.put(line)
            lines.put(None)
        def pump_err():
            n = 0
            for line in p.stderr:
                if n < MAX_LOG: log.append(line[: MAX_LOG - n]); n += len(line)
        threading.Thread(target=pump_out, daemon=True).start(); threading.Thread(target=pump_err, daemon=True).start()
        start = time.monotonic(); result = error = None; calls = 0
        while True:
            left = timeout - (time.monotonic() - start)
            if left <= 0: error = f"Stopped after {timeout} seconds."; break
            try: line = lines.get(timeout=min(left, 1))
            except queue.Empty: continue
            if line is None: break
            if line.startswith("@@call "):
                calls += 1
                try: reply = broker(json.loads(line[7:]))
                except Refused as e: reply = {"error": str(e)}
                except Exception as e: reply = {"error": f"The model server failed: {type(e).__name__}: {str(e)[:200]}"}
                try: p.stdin.write(json.dumps(reply) + "\n"); p.stdin.flush()
                except (BrokenPipeError, ValueError): break
            elif line.startswith("@@result "):
                if result is not None: error = "The script reported more than one result."; break
                if len(line) > MAX_RESULT: error = "The result was too large."; break
                try: result = json.loads(line[9:])
                except ValueError: error = "The result wasn't valid JSON."; break
                if not isinstance(result, dict): result, error = None, "The result wasn't a set of named values."; break
            else: log.append(line[:500])
        if p.poll() is None: p.kill()
        try: p.wait(timeout=10)
        except subprocess.TimeoutExpired: pass
        time.sleep(0.05)
        text = "".join(log)[-MAX_LOG:]
        if error is None and result is None:
            error = "The script ended without a result." + (f" (exit code {p.returncode})" if p.returncode else "")
        return {"result": result if error is None else None, "log": text, "calls": calls, "seconds": round(time.monotonic() - start, 1), "error": error}
    finally:
        shutil.rmtree(work, ignore_errors=True)
