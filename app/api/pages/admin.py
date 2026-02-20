from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, RedirectResponse

router = APIRouter()
STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
ADMIN_APP = STATIC_DIR / "admin/pages/app.html"


@router.get("/admin", include_in_schema=False)
async def admin_root():
    return RedirectResponse(url="/admin/login")


@router.get("/admin/login", include_in_schema=False)
async def admin_login():
    return FileResponse(STATIC_DIR / "admin/pages/login.html")


@router.get("/admin/{path:path}", include_in_schema=False)
async def admin_app(path: str):
    return FileResponse(ADMIN_APP)
