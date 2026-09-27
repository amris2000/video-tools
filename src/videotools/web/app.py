from fastapi import FastAPI

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