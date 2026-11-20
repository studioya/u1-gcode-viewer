"""U1 G-code Viewer launcher for Windows.

Double-click (or use the shortcut) to open the viewer in its own window.
It serves index.html from this repo on http://localhost:8765, visible to
this computer only, which the U1's stock Moonraker accepts for uploads.

    pythonw u1_viewer.pyw              open the viewer
    pythonw u1_viewer.pyw --serve      serve only, no window and no idle exit (what runs at sign-in)
    python  u1_viewer.pyw --install    add Desktop and Start menu shortcuts, and serve at sign-in
    python  u1_viewer.pyw --uninstall  remove all of them

G-code files in Documents/U1 jobs are served at /jobs/<name>, so
http://localhost:8765/?file=<name> opens that file in the viewer.

/relay/... forwards the viewer's printer requests to Moonraker, so the page never has to
reach the printer itself. Browsers that block pages from the local network (like the
browser pane a Claude chat session drives) can still send prints this way.

Only the Python standard library is used.
"""
import http.client
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
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
# G-code files dropped here can be opened with ?file=<name>. Only plain names with a G-code
# extension are served, from this folder only (no subfolders, no "..").
def documents_dirs():
    """Windows' Documents folder (often moved into OneDrive), then the plain one under the user folder."""
    dirs = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            dirs.append(os.path.expandvars(winreg.QueryValueEx(k, "Personal")[0]))
    except Exception:
        pass
    dirs.append(os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), "Documents"))
    out = []
    for d in map(os.path.abspath, dirs):
        if os.path.normcase(d) not in map(os.path.normcase, out):
            out.append(d)
    return out


# Files are looked up in every candidate folder; the first is where --install creates it.
JOBS_DIRS = [os.path.join(d, "U1 jobs") for d in documents_dirs()]
JOBS = JOBS_DIRS[0]
JOB_NAME = re.compile(r"^[^/\\:*?\"<>|]+\.(gcode|gco|g)$", re.IGNORECASE)


# The printer relay forwards only the requests the viewer makes, only to addresses on the
# local network (never the internet or this computer).
RELAY_ROUTES = {("GET", "/server/info"), ("GET", "/printer/objects/query"), ("POST", "/server/files/upload")}
RELAY_TIMEOUT = {"GET": 5, "POST": 120}  # seconds per network step; the viewer gives up on GETs after 6


def private_host(host):
    """True if every address the name resolves to is on a private or link-local network."""
    try:
        addrs = {ai[4][0] for ai in socket.getaddrinfo(host, None)}
    except OSError:
        return False
    def ok(a):
        ip = ipaddress.ip_address(a.split("%", 1)[0])
        return (ip.is_private or ip.is_link_local) and not ip.is_loopback and not ip.is_unspecified
    return bool(addrs) and all(ok(a) for a in addrs)


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
        if path.startswith("/jobs/"):
            return self.send_job(urllib.parse.unquote(path[len("/jobs/"):]))
        rel = ALLOWED.get(path)
        if rel is None:
            self.send_error(404)
            return None
        self.path = "/" + rel.replace(os.sep, "/")
        return super().send_head()

    def send_job(self, name):
        if not JOB_NAME.match(name) or ".." in name:
            self.send_error(404)
            return None
        full = next((p for p in (os.path.join(d, name) for d in JOBS_DIRS) if os.path.isfile(p)), None)
        if full is None:
            self.send_error(404)
            return None
        f = open(full, "rb")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(os.fstat(f.fileno()).st_size))
        self.end_headers()
        return f

    # ----- printer relay -----
    def do_GET(self):
        if self.path.startswith("/relay/"):
            return self.relay("GET")
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/relay/"):
            return self.relay("POST")
        self.send_error(405)

    def relay_error(self, status, text):
        body = ('{"error":{"message":' + json.dumps(text) + '}}').encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def relay(self, method):
        """Forward a Moonraker request to the printer, so the page only ever talks to localhost."""
        global last_request
        last_request = time.monotonic()
        # Only the viewer itself may use this: a custom header makes browsers refuse it to other
        # sites (they'd need a CORS preflight, which is never granted), and the Host and Origin
        # checks stop DNS-rebinding pages.
        port = self.server.server_address[1]
        local = {f"localhost:{port}", f"127.0.0.1:{port}"}
        origin = self.headers.get("Origin")
        if (self.headers.get("X-U1-Relay") != "1" or self.headers.get("Host") not in local
                or (origin is not None and urllib.parse.urlsplit(origin).netloc not in local)):
            return self.relay_error(403, "Only the U1 viewer on this computer can use the printer relay.")
        path = self.path[len("/relay"):]
        if path == "/ping":  # lets the viewer know the relay is here
            return self.relay_error(200, "relay")
        if (method, path.split("?", 1)[0]) not in RELAY_ROUTES:
            return self.relay_error(404, "The relay doesn't forward that request.")
        target = urllib.parse.urlsplit(self.headers.get("X-U1-Printer", ""))
        if target.scheme not in ("http", "https") or not target.hostname or not private_host(target.hostname):
            return self.relay_error(400, "The printer's address must be on your own network, like 10.0.0.18.")
        conn_cls = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
        conn = conn_cls(target.hostname, target.port, timeout=RELAY_TIMEOUT[method])
        try:
            conn.putrequest(method, path, skip_accept_encoding=True)
            for h in ("X-Api-Key", "Content-Type", "Accept"):
                if self.headers.get(h):
                    conn.putheader(h, self.headers[h])
            length = int(self.headers.get("Content-Length") or 0)
            if method == "POST":
                conn.putheader("Content-Length", str(length))
            conn.endheaders()
            while length > 0:  # stream the upload straight through
                chunk = self.rfile.read(min(length, 256 * 1024))
                if not chunk:
                    break
                conn.send(chunk)
                length -= len(chunk)
            resp = conn.getresponse()
            body = resp.read()
        except (OSError, http.client.HTTPException) as e:
            return self.relay_error(502, f"Couldn't reach the printer at {target.hostname}: {e}")
        finally:
            conn.close()
        self.send_response(resp.status)
        self.send_header("Content-Type", resp.getheader("Content-Type", "application/json"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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


def startup_path():
    startup = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    return os.path.join(startup, APP_NAME + " (server).lnk")


def ps_quote(s):
    return "'" + s.replace("'", "''") + "'"


def make_shortcut(lnk, pyw, args, description):
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut(" + ps_quote(lnk) + ");"
          "$s.TargetPath=" + ps_quote(pyw) + ";"
          "$s.Arguments=" + ps_quote(args) + ";"
          "$s.WorkingDirectory=" + ps_quote(HERE) + ";"
          "$s.IconLocation=" + ps_quote(ICON + ",0") + ";"
          "$s.Description=" + ps_quote(description) + ";"
          "$s.Save()")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       capture_output=True, text=True, timeout=30, creationflags=0x08000000)
    if r.returncode != 0 or not os.path.isfile(lnk):
        message(f"Couldn't create the shortcut:\n{lnk}\n\n{r.stderr.strip()}", error=True)
        return False
    return True


def install():
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.isfile(pyw):
        pyw = sys.executable
    script = '"' + os.path.abspath(__file__) + '"'
    for lnk in shortcut_paths():
        if not make_shortcut(lnk, pyw, script, "Open the U1 G-code Viewer"):
            return 1
    if not make_shortcut(startup_path(), pyw, script + " --serve", "Serve the U1 G-code Viewer on localhost"):
        return 1
    os.makedirs(JOBS, exist_ok=True)
    # start the background server now, so it's there before the next sign-in
    subprocess.Popen([pyw, os.path.abspath(__file__), "--serve"], close_fds=True, creationflags=0x08000000)
    message("Added the U1 Viewer shortcut to your Desktop and Start menu, and set the viewer to run in the "
            "background whenever you sign in, at http://localhost:8765.\n\n"
            f"G-code files in {JOBS} open with http://localhost:8765/?file=<name>.\n\n"
            "To pin it to the taskbar: open Start, right-click U1 Viewer, then Pin to taskbar.")
    return 0


def uninstall():
    removed = [p for p in shortcut_paths() + [startup_path()] if os.path.isfile(p)]
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
    serve_only = "--serve" in sys.argv
    try:
        port, srv = start_server()
    except Exception as e:
        if not serve_only:
            message(f"Couldn't start the viewer: {e}", error=True)
        return 1
    if serve_only:
        while srv is not None:  # run until sign-out; if another copy is serving, just exit
            time.sleep(3600)
        return 0
    open_window(f"http://localhost:{port}/")
    if srv is None:
        return 0  # another copy is already serving; it keeps running
    while time.monotonic() - last_request < IDLE_EXIT_SECONDS:
        time.sleep(30)
    srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
