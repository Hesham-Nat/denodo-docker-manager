# app/routers/home.py

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from app.utils.image_utils import parse_docker_image_file_for_denodo, parse_docker_image_file_for_sm

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/favicon.ico")
async def favicon():
    """
    Serves the favicon for the app.
    """
    return FileResponse("app/static/favicon.ico")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Renders the homepage showing available Denodo and Solution Manager image tags.
    """
    denodo_tags = parse_docker_image_file_for_denodo()
    sm_tags = parse_docker_image_file_for_sm()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "denodo_images": denodo_tags,
        "sm_images": sm_tags
    })
