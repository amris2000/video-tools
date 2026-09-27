from __future__ import annotations

import socket
import threading
import time
import webbrowser

import uvicorn


HOST = "127.0.0.1"
PORT = 8765


def wait_for_server() -> None:
    """
    Wait briefly for FastAPI to start before opening the browser.
    """
    deadline = time.monotonic() + 10

    while time.monotonic() < deadline:
        try:
            with socket.create_connection(
                (HOST, PORT),
                timeout=0.5,
            ):
                webbrowser.open(
                    f"http://{HOST}:{PORT}"
                )
                return
        except OSError:
            time.sleep(0.1)


def run_application() -> None:
    browser_thread = threading.Thread(
        target=wait_for_server,
        daemon=True,
    )
    browser_thread.start()

    uvicorn.run(
        "videotools.web.app:app",
        host=HOST,
        port=PORT,
        reload=False,
    )