"""
Murimi Fara - desktop app (and web server) entry point.

    MurimiFara.exe              opens the app in its own window. While it is open,
                                phones on this computer's Wi-Fi/hotspot can use it
                                too, in their browser (the address is shown in the app).
    MurimiFara.exe --server     no window: just the web app, for a shared computer
                                or a server. Open http://<this computer>:8000.

There is no AI model to start: answers come from the farm book and Murimi
Fara's own small model (see advisor.py), so it opens in seconds and runs on
old, low-memory computers.

Problems are written to murimifara_error.log in %LOCALAPPDATA%\\MurimiFara,
because the packaged app has no console.

FILES IT EXPECTS beside the exe (build_exe.ps1 copies them):
    index.html, murimifara.png, corpus_livestock_crops.md, vendor/,
    models/murimi_model.json, data/, audio/
"""

import json
import os
import sys
import tempfile
import threading
import time
import traceback
import urllib.request

# With --noconsole there is no console, so stdout/stderr are None; several
# libraries (uvicorn) call .isatty() on them and crash. Give them a real file.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)  # so every relative path used elsewhere resolves correctly

PORT = 8000


def get_data_dir():
    """A folder this user can always write to (logs, feedback, farm records).
    The installer puts the app under Program Files, which ordinary users cannot
    write to, so use %LOCALAPPDATA%\\MurimiFara, then a "data" folder beside the
    app, then the temp folder."""
    candidates = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(os.path.join(local, "MurimiFara"))
    candidates.append(os.path.join(BASE_DIR, "data"))
    candidates.append(os.path.join(tempfile.gettempdir(), "MurimiFara"))
    for folder in candidates:
        try:
            os.makedirs(folder, exist_ok=True)
            probe = os.path.join(folder, ".write_test")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            return folder
        except OSError:
            continue
    return None


DATA_DIR = get_data_dir()
os.environ["MURIMIFARA_DATA_DIR"] = DATA_DIR or ""      # app.py keeps its files here
ERROR_LOG_PATH = os.path.join(DATA_DIR or BASE_DIR, "murimifara_error.log")
_instance_mutex = None   # held for the life of the app (single-instance check)


def log_error(context, exc_info=None):
    """Write a startup problem to the log. Must never crash the app itself."""
    try:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} {context} ---\n")
            if exc_info and exc_info[0]:
                f.write("".join(traceback.format_exception(*exc_info)))
    except OSError:
        pass


def already_open():
    """Windows: True if another copy of Murimi Fara is already running (two
    copies fight over the same port)."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        global _instance_mutex
        _instance_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\MurimiFaraAdvisor")
        return ctypes.windll.kernel32.GetLastError() == 183      # ERROR_ALREADY_EXISTS
    except Exception:
        return False


def tell_already_open():
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None, "Murimi Fara is already open.\n\nLook for its window on the taskbar.", "Murimi Fara", 0x40)
    except Exception:
        pass


def start_backend():
    """Run the web server inside this program. Listens on every network
    interface (0.0.0.0) so phones on the same Wi-Fi can reach it. Retries while
    Windows is still releasing the port from a run that just closed."""
    try:
        import uvicorn
        import app
    except BaseException:
        log_error("Backend failed to load", sys.exc_info())
        return
    for attempt in range(1, 6):
        try:
            uvicorn.run(app.app, host="0.0.0.0", port=PORT, log_level="warning", log_config=None)
            return
        except SystemExit:
            log_error(f"Backend start attempt {attempt} failed (port busy?)", sys.exc_info())
            time.sleep(3)
        except BaseException:
            log_error("Backend failed to start", sys.exc_info())
            return


def wait_for_backend(timeout_seconds=60):
    start, last_error = time.time(), None
    while time.time() - start < timeout_seconds:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=2)
            return True
        except Exception as e:  # noqa: BLE001
            last_error = e
            time.sleep(0.3)
    log_error(f"Backend did not become ready after {timeout_seconds}s. Last error: {last_error!r}")
    return False


def run_officer_selftest():
    """Used by build_exe.ps1 after building: answers one question and drafts one
    officer advisory, and writes OK or the error to murimifara_selftest.txt."""
    import asyncio
    result_path = os.path.join(DATA_DIR or BASE_DIR, "murimifara_selftest.txt")
    try:
        from advisor import Advisor, default_model_path
        found = Advisor("corpus_livestock_crops.md", default_model_path(BASE_DIR)).ask("Mombe yangu iri kuita weti tsvuku")
        if "B3" not in found["entries"]:
            raise RuntimeError("farm book answer check failed: " + json.dumps(found["entries"]))
        from challenge_agent.orchestrator import draft
        db = os.path.join(tempfile.mkdtemp(), "selftest.sqlite3")
        result = asyncio.run(draft("my maize has ragged holes and frass in the whorl", db))
        status = "OK " + result["id"] if result.get("id") else "FAIL " + json.dumps(result)
    except Exception as exc:  # noqa: BLE001
        status = f"FAIL {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(status + "\n")


def main():
    if "--officer-selftest" in sys.argv:
        run_officer_selftest()
        return
    if already_open():
        tell_already_open()
        return
    if "--server" in sys.argv:
        start_backend()            # runs until the process is stopped
        return
    try:
        threading.Thread(target=start_backend, daemon=True).start()
        ready = wait_for_backend()
        import webview
        if ready:
            webview.create_window("Murimi Fara - Offline Farm Advisor", f"http://127.0.0.1:{PORT}/",
                                  width=900, height=720, min_size=(500, 500))
        else:
            webview.create_window("Murimi Fara - Startup Error",
                                  html="<h2>Something went wrong starting Murimi Fara.</h2>"
                                       f"<p>Please send this file to the Murimi Fara team:<br>{ERROR_LOG_PATH}</p>",
                                  width=520, height=300)
        webview.start()
    except Exception:
        log_error("Fatal error in main()", sys.exc_info())


if __name__ == "__main__":
    main()