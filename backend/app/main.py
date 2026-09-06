"""Entrypoint module for the combined frontend and backend server.

All actual routes live in app/api/search.py (auth, projects, documents,
hybrid-search RAG, agents, admin/RBAC, notes). This module just re-exports
the configured FastAPI instance under the conventional app.main:app path.
"""

from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse

from app.api.search import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST = PROJECT_ROOT / "dist"


@app.middleware("http")
async def rewrite_frontend_api_prefix(request: Request, call_next):
    """Keep browser requests on /api while routing them to FastAPI endpoints."""
    if request.scope["path"].startswith("/api"):
        request.scope["path"] = request.scope["path"][4:] or "/"
    return await call_next(request)


@app.get("/{path:path}", include_in_schema=False)
async def serve_frontend(path: str):
    """Serve the built React app for browser routes not handled by the API."""
    index_file = FRONTEND_DIST / "index.html"
    if not index_file.is_file():
        return {"detail": "Frontend build not found. Run npm run build first."}
    requested_file = FRONTEND_DIST / path
    if path and requested_file.is_file() and FRONTEND_DIST in requested_file.parents:
        return FileResponse(requested_file)
    return FileResponse(index_file)


__all__ = ["app"]
