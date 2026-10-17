"""Double-click macOS launcher for an internal, bundled app build."""

import threading
import time
import webbrowser

import uvicorn

from app.api import create_app
from app.config import settings


def main() -> None:
    application = create_app(settings)
    server = uvicorn.Server(uvicorn.Config(
        application, host="127.0.0.1", port=settings.port,
        reload=False, access_log=False,
    ))
    application.state.desktop_exit = lambda: setattr(server, "should_exit", True)

    def open_dashboard() -> None:
        for _ in range(100):
            if server.started:
                webbrowser.open(f"http://127.0.0.1:{settings.port}/")
                return
            if server.should_exit:
                return
            time.sleep(0.1)

    threading.Thread(target=open_dashboard, daemon=True).start()
    server.run()  # FastAPI lifespan stops output and camera before process exit.


if __name__ == "__main__":
    main()
