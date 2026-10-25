"""Point SmartWard at a throwaway data folder BEFORE anything can import `sw.db`.

`sw.db` opens the library the moment it is imported, using SMARTWARD_DATA. Importing `tests` runs this
file first, whatever order test modules import things in, so a test can never touch your real library.
"""
import atexit, os, shutil, tempfile

DATA = tempfile.mkdtemp(prefix="smartward-test-")
os.environ["SMARTWARD_DATA"] = DATA
os.environ["OLLAMA_API_BASE"] = "http://127.0.0.1:9"
atexit.register(shutil.rmtree, DATA, ignore_errors=True)
# Remote access holds a "don't sleep" lock; tests must never take the real one.
os.environ["SMARTWARD_INHIBIT_CMD"] = "true"
os.environ["SMARTWARD_TAILSCALE_CMD"] = "/nonexistent/tailscale"
