"""Minimal Chrome DevTools Protocol driver used by the BONKAGEDDON test suite (dev-only)."""
import json, os, subprocess, sys, time, urllib.request, base64
import websocket

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT_HTTP = 8765
PORT_CDP = 9333


class Env:
    def __init__(self, scratch):
        self.scratch = scratch
        os.makedirs(scratch, exist_ok=True)
        self.http = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT_HTTP), "--bind", "127.0.0.1"],
                                     cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.chrome = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT_CDP}",
                                        "--remote-allow-origins=*", f"--user-data-dir={os.path.join(scratch, 'prof')}",
                                        "--no-first-run", "--autoplay-policy=no-user-gesture-required",
                                        "--lang=en-US", "--accept-lang=en-US",
                                        "--window-size=450,820", "about:blank"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT_CDP}/json"))
                page = [t for t in tabs if t.get("type") == "page"][0]
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("chrome did not start")
        self.cdp = CDP(page["webSocketDebuggerUrl"])
        self.cdp.send("Runtime.enable")
        self.cdp.send("Page.enable")
        self.cdp.send("Network.enable")

    def close(self):
        try:
            self.cdp.ws.close()
        except Exception:
            pass
        self.chrome.kill()
        self.http.kill()


class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=120, suppress_origin=True)
        self.mid = 0
        self.events = []

    def send(self, method, **params):
        self.mid += 1
        mid = self.mid
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            self.events.append(msg)

    def ev(self, expr, awaitp=False):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=awaitp)
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise RuntimeError(d.get("exception", {}).get("description") or d.get("text"))
        return r["result"].get("value")

    def pump(self, secs=0.05):
        self.ws.settimeout(secs)
        try:
            while True:
                self.events.append(json.loads(self.ws.recv()))
        except Exception:
            pass
        self.ws.settimeout(120)

    def errors(self, clear=True):
        out = []
        for m in self.events:
            if m.get("method") == "Runtime.exceptionThrown":
                d = m["params"]["exceptionDetails"]
                out.append("EXC " + (d.get("exception", {}).get("description") or d.get("text", ""))[:400])
            elif m.get("method") == "Runtime.consoleAPICalled" and m["params"]["type"] == "error":
                out.append("ERR " + " ".join(str(a.get("value", a.get("description", ""))) for a in m["params"]["args"])[:400])
        if clear:
            self.events = []
        return out

    def warnings(self):
        return [" ".join(str(a.get("value", a.get("description", ""))) for a in m["params"]["args"])[:300]
                for m in self.events if m.get("method") == "Runtime.consoleAPICalled" and m["params"]["type"] == "warning"]

    def nav(self, url, wait_expr="window.BONK && BONK.Game.state!=='BOOT'", timeout=20):
        self.send("Page.navigate", url=url)
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.ev(f"!!({wait_expr})"):
                    return
            except Exception:
                pass
            time.sleep(0.1)
        raise RuntimeError("page did not boot: " + url)

    def screenshot(self, path):
        r = self.send("Page.captureScreenshot", format="png")
        with open(path, "wb") as f:
            f.write(base64.b64decode(r["data"]))

    def mouse(self, typ, x, y):
        self.send("Input.dispatchMouseEvent", type=typ, x=x, y=y, button="left", buttons=1 if typ != "mouseReleased" else 0, clickCount=1)

    def touch(self, typ, x, y):
        pts = [] if typ == "touchEnd" else [{"x": x, "y": y, "id": 1}]
        self.send("Input.dispatchTouchEvent", type=typ, touchPoints=pts)

    def metrics(self, w, h, dpr=1, mobile=False):
        self.send("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=dpr, mobile=mobile)
        self.send("Emulation.setTouchEmulationEnabled", enabled=mobile, maxTouchPoints=5 if mobile else 1)
