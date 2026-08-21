"""FastAPI server bootstrap.

`run_server()` starts uvicorn on localhost:8765 by default and, unless
`open_browser=False`, points the user's browser at it.

The web UI is strictly local by design — see `--host 0.0.0.0` warning
below if you want to expose it beyond your machine.
"""
from __future__ import annotations

import threading
import time
import webbrowser
from typing import Any

from fastapi import FastAPI

from .routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="bibcpr",
        version="0.1.0",
        description="Local evidence-first BibTeX auditor.",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.include_router(router)
    return app


def _open_browser_when_ready(url: str, delay: float = 0.75) -> None:
    def _job() -> None:
        time.sleep(delay)
        try:
            webbrowser.open_new_tab(url)
        except Exception:
            # Never crash the server because we couldn't open a browser
            pass

    threading.Thread(target=_job, daemon=True).start()


def run_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    log_level: str = "info",
) -> None:
    """Launch the local bibcpr web UI."""
    import uvicorn

    if host not in ("127.0.0.1", "localhost"):
        print(
            f"[bibcpr] WARNING: binding to {host} exposes your bibliographies "
            "beyond this machine. Use --host 127.0.0.1 to keep it local."
        )

    url = f"http://{host}:{port}/"
    if open_browser:
        _open_browser_when_ready(url)

    print(f"[bibcpr] serving on {url}  (Ctrl-C to stop)")
    uvicorn.run(
        "cpr.webapp.server:create_app",
        host=host,
        port=port,
        log_level=log_level,
        factory=True,
        reload=False,
    )
