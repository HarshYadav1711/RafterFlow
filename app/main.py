"""Minimal FastAPI entrypoint for Phase 0."""

from fastapi import FastAPI

app = FastAPI(title="RafterFlow", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "rafterflow"}
