"""U1 G-code Viewer launcher for Windows.

Double-click (or use the shortcut) to open the viewer in its own window.
It serves index.html from this repo on http://localhost:8765, visible to
this computer only, which the U1's stock Moonraker accepts for uploads.

    pythonw u1_viewer.pyw              open the viewer
    python  u1_viewer.pyw --install    add Desktop and Start menu shortcuts
    python  u1_viewer.pyw --uninstall  remove them

Only the Python standard library is used.
"""
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

APP_NAME = "U1 Viewer"
HOST = "127.0.0.1"
PORTS = range(8765, 8775)          # 8765 is also what .claude/launch.json uses
IDLE_EXIT_SECONDS = 2 * 60 * 60    # stop the server after 2 hours without requests
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)       # the repo folder, where index.html lives
ICON = os.path.join(HERE, "u1.ico")
# Only these files are served; everything else (.git, .claude, the launcher) is a 404.
ALLOWED = {"/": "index.html", "/index.html": "index.html", "/favicon.ico": os.path.join("launcher", "u1.ico")}
MARKER = b"<title>U1 G-code Viewer</title>"


def message(text, error=False):
    """Show a Windows message box (pythonw has no console)."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, 0x10 if error else 0x40)
    except Exception:
        print(text, file=sys.stderr)


# ---------- server ----------
last_request = time.monotonic()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def send_head(self):
        global last_request
        last_request = time.monotonic()
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        rel = ALLOWED.get(path)
        if rel is None:
            self.send_error(404)
            return None
        self.path = "/" + rel.replace(os.sep, "/")
        return super().send_head()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass


def viewer_running(port):
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/", timeout=1.5) as r:
            return MARKER in r.read(4096)
    except Exception:
        return False


def start_server():
    """Return the port the viewer is served on, starting a server if needed."""
    for port in PORTS:
        if viewer_running(port):
            return port, None
        try:
            srv = ThreadingHTTPServer((HOST, port), Handler)
        except OSError:
            continue  # port taken by something else
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return port, srv
    raise RuntimeError(f"No free port between {PORTS.start} and {PORTS.stop - 1}.")


# ---------- browser window ----------
def find_browser():
    pf = [os.environ.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
    candidates = []
    for base in filter(None, pf):
        candidates += [os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
                       os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")]
    return next((c for c in candidates if os.path.isfile(c)), None)


def open_window(url):
    exe = find_browser()
    if exe:
        subprocess.Popen([exe, f"--app={url}", "--window-size=1400,900"], close_fds=True)
    else:
        webbrowser.open(url)


# ---------- shortcuts ----------
def shortcut_paths():
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    try:  # OneDrive can move the Desktop; ask Windows where it is
        out = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                             capture_output=True, text=True, timeout=20, creationflags=0x08000000)
        if out.stdout.strip():
            desktop = out.stdout.strip()
    except Exception:
        pass
    programs = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs")
    return [os.path.join(desktop, APP_NAME + ".lnk"), os.path.join(programs, APP_NAME + ".lnk")]


def ps_quote(s):
    return "'" + s.replace("'", "''") + "'"


def install():
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.isfile(pyw):
        pyw = sys.executable
    script = os.path.abspath(__file__)
    made = []
    for lnk in shortcut_paths():
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut(" + ps_quote(lnk) + ");"
              "$s.TargetPath=" + ps_quote(pyw) + ";"
              "$s.Arguments=" + ps_quote('"' + script + '"') + ";"
              "$s.WorkingDirectory=" + ps_quote(HERE) + ";"
              "$s.IconLocation=" + ps_quote(ICON + ",0") + ";"
              "$s.Description=" + ps_quote("Open the U1 G-code Viewer") + ";"
              "$s.Save()")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           capture_output=True, text=True, timeout=30, creationflags=0x08000000)
        if r.returncode != 0 or not os.path.isfile(lnk):
            message(f"Couldn't create the shortcut:\n{lnk}\n\n{r.stderr.strip()}", error=True)
            return 1
        made.append(lnk)
    message("Added the U1 Viewer shortcut to your Desktop and Start menu.\n\n"
            "To pin it to the taskbar: open Start, right-click U1 Viewer, then Pin to taskbar.")
    return 0


def uninstall():
    removed = [p for p in shortcut_paths() if os.path.isfile(p)]
    for p in removed:
        os.remove(p)
    message("Removed the U1 Viewer shortcuts." if removed else "There were no U1 Viewer shortcuts to remove.")
    return 0


# ---------- main ----------
def main():
    if "--install" in sys.argv:
        return install()
    if "--uninstall" in sys.argv:
        return uninstall()
    if not os.path.isfile(os.path.join(ROOT, "index.html")):
        message(f"index.html wasn't found next to the launcher folder:\n{ROOT}", error=True)
        return 1
    try:
        port, srv = start_server()
    except Exception as e:
        message(f"Couldn't start the viewer: {e}", error=True)
        return 1
    open_window(f"http://localhost:{port}/")
    if srv is None:
        return 0  # another copy is already serving; it keeps running
    while time.monotonic() - last_request < IDLE_EXIT_SECONDS:
        time.sleep(30)
    srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
