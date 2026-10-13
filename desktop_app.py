"""
Murimi Fara - Desktop App Entry Point

This is what turns the project into a real one-click app: no terminal
windows, no visible code, no bash/bat scripts for the farmer to see or
run. Just one icon they double-click.

WHAT THIS DOES, IN ORDER:
1. Silently starts llama-server in the background (the "brain")
2. Silently starts the backend API in the background (the "translator")
3. Waits until the backend is ACTUALLY ready to respond, instead of
   guessing a fixed delay - this is what fixes "127.0.0.1 refused to
   connect", which happens when the window opens before the server has
   finished starting up
4. Opens ONE clean window showing the app - that's the only thing the
   farmer ever sees
5. When they close that window, everything shuts down cleanly behind
   the scenes

If anything goes wrong during startup, it's written to
murimifara_error.log next to the app - since --noconsole hides all
normal output, this log file is the only way to see what happened.

FOLDER LAYOUT THIS EXPECTS (all sitting next to this file/the built .exe):
    index.html
    rag.py
    corpus_livestock_crops.md
    faw_classifier.onnx
    vendor/
        react.production.min.js
        react-dom.production.min.js
    llama/
        llama-server.exe
        (all its .dll files)
    model/
        qwen2.5-1.5b-instruct-q4_k_m.gguf

SETUP (only needed once, on YOUR machine, to build the app):
    pip install pywebview pyinstaller

BUILDING THE ACTUAL APP (produces the real one-click .exe):
    pyinstaller --onedir --noconsole --icon=murimifara.ico --collect-all cv2 --name MurimiFara desktop_app.py

    Note the added --collect-all cv2 flag: OpenCV bundles native binary
    files that PyInstaller doesn't always detect automatically on its
    own. This flag forces PyInstaller to include everything OpenCV
    needs. If the packaged app crashes specifically when you try the
    photo-upload feature (but the chat/RAG feature still works fine),
    this is the first thing to check - rebuild with this flag if you
    left it off.

Then copy index.html, rag.py, corpus_livestock_crops.md,
faw_classifier.onnx, vendor/, llama/, and model/ into the same folder
PyInstaller creates (dist/MurimiFara/).
"""

import os
import sys
import subprocess
import tempfile
import threading
import time
import traceback
import urllib.request

# When built with --noconsole, there is no console attached at all, so
# Python's stdout/stderr are literally None rather than just empty.
# Several libraries (including uvicorn, which crashed here) call
# .isatty() on them to decide about colored output, which fails on
# None with "AttributeError: 'NoneType' object has no attribute
# 'isatty'". Giving them a real (harmless, discarded) file object
# instead of None fixes this whole class of bug, not just uvicorn's
# specific case of it.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)  # so every relative path used elsewhere resolves correctly

LLAMA_SERVER_PATH = os.path.join(BASE_DIR, "llama", "llama-server.exe")
MODEL_PATH = os.path.join(BASE_DIR, "model", "qwen2.5-1.5b-instruct-q4_k_m.gguf")


def get_data_dir():
    """A folder this user can always write to, for logs.

    The installer puts the app under Program Files, which ordinary Windows
    users cannot write to - so the error log (previously written next to the
    exe) would fail exactly when it was needed. Logs now go to
    %LOCALAPPDATA%\\MurimiFara, falling back to a "data" folder beside the app,
    then to the temp folder."""
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
# app.py reads this to know where to keep its query log
os.environ["MURIMIFARA_DATA_DIR"] = DATA_DIR or ""
ERROR_LOG_PATH = os.path.join(DATA_DIR or BASE_DIR, "murimifara_error.log")

llama_process = None


def log_error(context, exc):
    """Writes any startup failure to a log file next to the app. This is
    essential because --noconsole suppresses all normal print/error
    output - without this, a crash would be completely silent and
    impossible to diagnose."""
    # Logging must never be what crashes the app: if the file can't be
    # written, carry on rather than raising from inside an error handler.
    try:
        with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n--- {context} ---\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except OSError:
        pass


def start_llama_server():
    """Starts the model server completely hidden - no console window
    pops up, unlike when we ran this manually from a terminal before."""
    global llama_process
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    llama_process = subprocess.Popen(
        [
            LLAMA_SERVER_PATH,
            "-m", MODEL_PATH,
            "-t", "4",
            "-c", "4096",
            "--port", "8080",
        ],
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def start_backend():
    """Starts the API server in the background, inside this same
    program - no separate uvicorn command, no separate window. Any
    startup failure (missing file, import error, etc.) gets written to
    the error log instead of vanishing silently.

    Retries a few times on "port already in use" specifically - this
    happens intermittently when a previous run's process hasn't fully
    released the port yet (Windows can hold a just-closed socket in a
    "cooling down" state for a few seconds), especially if the app was
    closed and reopened quickly. Most of the time this clears up within
    a few seconds on its own.
    """
    try:
        import uvicorn
        import app  # your existing app.py, unchanged
    except BaseException:
        # Catches any failure while app.py itself loads (missing file,
        # corpus/model loading error, etc.) - this must stay wrapped in
        # its own try/except, separate from the retry loop below, or a
        # failure here would crash the thread with nothing to catch it.
        log_error("Backend failed to import required modules", sys.exc_info())
        return

    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            # 0.0.0.0 means "listen on every network interface", not just
            # this laptop itself - this is what lets other devices (a
            # farmer's phone, connected to the same WiFi/hotspot)
            # actually reach this backend. 127.0.0.1 alone would only
            # ever work from this laptop.
            uvicorn.run(app.app, host="0.0.0.0", port=8000, log_level="warning", log_config=None)
            return  # uvicorn.run only returns on a clean shutdown
        except SystemExit:
            if attempt < max_attempts:
                log_error(f"Backend startup attempt {attempt} failed (likely port still releasing), retrying...", sys.exc_info())
                time.sleep(3)
            else:
                log_error("Backend failed to start after all retry attempts", sys.exc_info())
                return
        except BaseException:
            # Any other failure (not the specific port-retry case above)
            # gets logged immediately, same as before.
            log_error("Backend failed to start", sys.exc_info())
            return


def wait_for_backend(timeout_seconds=90):
    """Repeatedly checks whether the backend is actually ready to answer
    requests, instead of guessing a fixed delay. Returns True once ready,
    False if it never came up in time.

    Timeout raised from 40 to 90 seconds - antivirus software commonly
    scans newly-launched executables (especially ones bundling many
    native binaries, like this app does with OpenCV and llama.cpp) on
    first run, which can legitimately add real delay that isn't a bug,
    just a slow-but-working startup. A longer wait that eventually
    succeeds is far better than a short one that falsely reports failure.

    Also logs every failed attempt's actual error - previously a timeout
    here just logged "NoneType: None" with no useful information. Now,
    if this ever times out again, the log will show exactly what was
    happening on each attempt (connection refused? timed out? something
    else?) instead of nothing at all.
    """
    start = time.time()
    last_error = None
    attempts = 0
    while time.time() - start < timeout_seconds:
        attempts += 1
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2)
            return True
        except Exception as e:
            last_error = e
            time.sleep(0.5)

    log_error(
        f"Backend did not become ready after {timeout_seconds}s "
        f"({attempts} attempts). Last error: {last_error!r}. "
        f"llama_process still running: {llama_process.poll() is None if llama_process else 'N/A'}",
        None,
    )
    return False


def main():
    try:
        start_llama_server()

        backend_thread = threading.Thread(target=start_backend, daemon=True)
        backend_thread.start()

        backend_ready = wait_for_backend()

        import webview
        if backend_ready:
            webview.create_window(
                "Murimi Fara - Offline Farm Advisor",
                "http://127.0.0.1:8000/",
                width=900,
                height=720,
                min_size=(500, 500),
            )
        else:
            # wait_for_backend() already logged detailed diagnostics
            # (attempt count, last error, whether llama_process is still
            # alive) - no need to log the same failure twice here.
            webview.create_window(
                "Murimi Fara - Startup Error",
                html="<h2>Something went wrong starting the advisor.</h2>"
                     "<p>Check murimifara_error.log in the app folder.</p>",
                width=500,
                height=300,
            )

        webview.start()

    except Exception:
        log_error("Fatal error in main()", sys.exc_info())

    finally:
        if llama_process:
            llama_process.terminate()


if __name__ == "__main__":
    main()