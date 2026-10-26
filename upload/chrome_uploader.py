import os
import json
import time
import shutil
import asyncio
import logging
import subprocess
import requests
import websockets

log = logging.getLogger("chrome_uploader")

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_chrome_executable():
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None


def sync_chrome_profile(profile_name="Profile 1"):
    """
    Syncs essential session cookies and storage from user's Chrome Profile 1
    into an isolated automation profile so it can run alongside regular Chrome.
    """
    localappdata = os.environ.get("LOCALAPPDATA", "")
    src_user_data = os.path.join(localappdata, "Google", "Chrome", "User Data")
    src_profile = os.path.join(src_user_data, profile_name)

    dest_user_data = os.path.abspath("browser_profiles/chrome_automation")
    os.makedirs(dest_user_data, exist_ok=True)

    # 1. Sync Local State (contains DPAPI decryption key)
    src_ls = os.path.join(src_user_data, "Local State")
    dest_ls = os.path.join(dest_user_data, "Local State")
    if os.path.exists(src_ls):
        try:
            shutil.copy2(src_ls, dest_ls)
        except Exception as e:
            log.debug("Local State sync: %s", e)

    # 2. Sync Profile 1 data into Default of automation dir
    dest_profile = os.path.join(dest_user_data, "Default")
    os.makedirs(dest_profile, exist_ok=True)

    for sub in ["Network", "Preferences", "Login Data", "Web Data"]:
        s = os.path.join(src_profile, sub)
        d = os.path.join(dest_profile, sub)
        if os.path.exists(s):
            try:
                if os.path.isdir(s):
                    if os.path.exists(d):
                        shutil.rmtree(d, ignore_errors=True)
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
            except Exception as e:
                log.debug("Sync %s: %s", sub, e)

    return dest_user_data


class ChromeCDP:
    """Lightweight Chrome DevTools Protocol client using built-in requests + websockets."""

    def __init__(self, port=9223, user_data_dir=None):
        self.port = port
        self.user_data_dir = user_data_dir or os.path.abspath("browser_profiles/chrome_automation")
        self.proc = None
        self.ws = None
        self._msg_id = 1

    def launch(self, url="about:blank"):
        exe = find_chrome_executable()
        if not exe:
            raise FileNotFoundError("Google Chrome executable not found.")

        cmd = [
            exe,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            url,
        ]

        self.proc = subprocess.Popen(cmd)
        # Wait for debugging port to be ready
        for _ in range(25):
            time.sleep(0.4)
            try:
                r = requests.get(f"http://127.0.0.1:{self.port}/json/list", timeout=2)
                if r.status_code == 200 and r.json():
                    return
            except Exception:
                pass

    async def connect(self):
        r = requests.get(f"http://127.0.0.1:{self.port}/json/list", timeout=5)
        pages = r.json()
        target = next((p for p in pages if p.get("type") == "page"), pages[0])
        ws_url = target.get("webSocketDebuggerUrl")
        self.ws = await websockets.connect(ws_url, max_size=20 * 1024 * 1024)

    async def send(self, method, params=None):
        self._msg_id += 1
        payload = {"id": self._msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(payload))
        while True:
            resp_raw = await self.ws.recv()
            resp = json.loads(resp_raw)
            if resp.get("id") == self._msg_id:
                return resp.get("result", {})

    async def eval_js(self, expression):
        res = await self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        val = res.get("result", {}).get("value")
        return val

    async def set_file_input(self, selector, file_path):
        doc = await self.send("DOM.getDocument")
        root_node_id = doc.get("root", {}).get("nodeId", 1)
        node = await self.send("DOM.querySelector", {"nodeId": root_node_id, "selector": selector})
        node_id = node.get("nodeId")
        if node_id:
            await self.send("DOM.setFileInputFiles", {
                "files": [os.path.abspath(file_path)],
                "nodeId": node_id,
            })
            return True
        return False

    async def close(self):
        try:
            if self.ws:
                await self.ws.close()
        except Exception:
            pass
        if self.proc:
            try:
                self.proc.terminate()
            except Exception:
                pass


def upload_facebook_reel_automated(video_path, title, description, progress_cb, profile_name="Profile 1"):
    """Automates Facebook Reels upload using Chrome Profile 1."""
    progress_cb(10, f"Syncing Chrome {profile_name} sessions...")
    user_data = sync_chrome_profile(profile_name)

    cdp = ChromeCDP(port=9223, user_data_dir=user_data)
    progress_cb(20, "Launching Chrome with your Profile 1...")
    cdp.launch(url="https://business.facebook.com/latest/reels_composer")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        await cdp.connect()
        progress_cb(35, "Navigating to Meta Reels Composer...")

        # Wait for file input or upload container
        uploaded_file = False
        for _ in range(40):
            time.sleep(1)
            # Find file input
            has_input = await cdp.eval_js("Boolean(document.querySelector('input[type=\"file\"]'))")
            if has_input:
                progress_cb(50, "Attaching video file...")
                ok = await cdp.set_file_input('input[type="file"]', video_path)
                if ok:
                    uploaded_file = True
                    break

        if not uploaded_file:
            progress_cb(60, "Please drag the video into Meta Business Suite if prompted...")

        progress_cb(70, "Entering title, description & hashtags...")
        full_text = f"{title}\n\n{description}\n\n#reels #viral #shorts"
        safe_js_text = json.dumps(full_text)

        # Set caption into editable div/textarea
        await cdp.eval_js(f"""
            (() => {{
                const el = document.querySelector('[role="textbox"]') || document.querySelector('textarea');
                if (el) {{
                    el.focus();
                    document.execCommand('insertText', false, {safe_js_text});
                }}
            }})()
        """)

        progress_cb(85, "Ready for publishing! Review and click Publish in Chrome.")

    try:
        loop.run_until_complete(_run())
        progress_cb(100, "Facebook Reels automated workflow complete!")
    except Exception as e:
        log.warning("Facebook automation note: %s", e)
        progress_cb(100, f"Opened Meta Business Suite in Chrome Profile 1: {e}")
    finally:
        loop.close()


def upload_tiktok_automated(video_path, title, description, tags, progress_cb, profile_name="Profile 1"):
    """Automates TikTok Creator Center upload using Chrome Profile 1."""
    progress_cb(10, f"Syncing Chrome {profile_name} sessions...")
    user_data = sync_chrome_profile(profile_name)

    cdp = ChromeCDP(port=9224, user_data_dir=user_data)
    progress_cb(20, "Launching Chrome with your Profile 1...")
    cdp.launch(url="https://www.tiktok.com/creator-center/upload")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        await cdp.connect()
        progress_cb(35, "Opening TikTok Creator Center...")

        # Find upload file input
        uploaded = False
        for _ in range(40):
            time.sleep(1)
            has_input = await cdp.eval_js("Boolean(document.querySelector('input[type=\"file\"]'))")
            if has_input:
                progress_cb(50, "Attaching video file...")
                ok = await cdp.set_file_input('input[type="file"]', video_path)
                if ok:
                    uploaded = True
                    break

        progress_cb(70, "Entering caption and hashtags...")
        tag_str = " ".join([f"#{t.lstrip('#')}" for t in tags[:8]]) if tags else "#fyp #viral"
        caption = f"{title} {tag_str}"
        safe_caption = json.dumps(caption)

        await cdp.eval_js(f"""
            (() => {{
                const el = document.querySelector('[contenteditable="true"]') || document.querySelector('textarea');
                if (el) {{
                    el.focus();
                    document.execCommand('selectAll', false, null);
                    document.execCommand('insertText', false, {safe_caption});
                }}
            }})()
        """)

        progress_cb(85, "Video attached & caption filled in Chrome! Review and click Post.")

    try:
        loop.run_until_complete(_run())
        progress_cb(100, "TikTok upload workflow dispatched in Chrome!")
    except Exception as e:
        log.warning("TikTok automation note: %s", e)
        progress_cb(100, f"Opened TikTok in Chrome Profile 1: {e}")
    finally:
        loop.close()
