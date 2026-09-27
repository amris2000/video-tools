from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from videotools.web.frontend import find_frontend_build
from videotools.web.routers import config, projects


app = FastAPI(
    title="Video Tools",
    version="0.1.0",
)

app.include_router(
    config.router,
    prefix="/api",
)

app.include_router(
    projects.router,
    prefix="/api",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
    }


frontend_build = find_frontend_build()

if frontend_build is not None:
    assets_directory = frontend_build / "assets"

    if assets_directory.is_dir():
        app.mount(
            "/assets",
            StaticFiles(
                directory=assets_directory
            ),
            name="frontend-assets",
        )


@app.get("/{path:path}")
def frontend(path: str):
    if frontend_build is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Frontend has not been built. "
                "Run 'video-tools install' first."
            ),
        )

    requested_file = (
        frontend_build / path
    ).resolve()

    try:
        requested_file.relative_to(
            frontend_build.resolve()
        )
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Not found.",
        )

    if (
        path
        and requested_file.is_file()
    ):
        return FileResponse(requested_file)

    return FileResponse(
        frontend_build / "index.html"
    )