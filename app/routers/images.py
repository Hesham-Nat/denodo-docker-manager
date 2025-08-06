# app/routers/images.py

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.utils.docker_utils import verbose_pull, verbose_load
import os, tempfile, gzip
from docker import from_env

router = APIRouter()
client = from_env()
templates = Jinja2Templates(directory="app/templates")


@router.get("/images", response_class=HTMLResponse)
def images_page(request: Request):
    """
    Show all available Docker images.
    """
    images = client.images.list()
    tags = [tag for img in images for tag in img.tags]
    return templates.TemplateResponse("images.html", {
        "request": request,
        "images": tags
    })


@router.post("/images/import")
async def import_image(request: Request, imageFile: UploadFile = File(...)):
    """
    Upload and import a Docker image from a .tar/.tar.gz/.tgz archive.
    """
    allowed_exts = (".tar", ".tar.gz", ".tgz")
    filename = imageFile.filename or ""
    if not any(filename.endswith(ext) for ext in allowed_exts):
        return RedirectResponse("/images?error=Unsupported+file+type", status_code=303)

    suffix = ".tar.gz" if filename.endswith((".tar.gz", ".tgz")) else ".tar"
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(tmp_fd)

    try:
        with open(tmp_path, "wb") as out:
            while chunk := await imageFile.read(8 * 1024 * 1024):
                out.write(chunk)

        with (gzip.open(tmp_path, "rb") if tmp_path.endswith(".gz") else open(tmp_path, "rb")) as f:
            verbose_load(f)

        return RedirectResponse("/images?success=Image+imported+successfully", status_code=303)

    except Exception as e:
        return RedirectResponse(f"/images?error={str(e).replace(' ', '+')}", status_code=303)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@router.post("/images/pull")
async def pull_image(image_name: str = Form(...)):
    """
    Pull an image from a Docker registry.
    """
    try:
        verbose_pull(image_name)
        return RedirectResponse(url=f"/images?success=Image+{image_name}+pulled", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/images?error={str(e).replace(' ', '+')}", status_code=303)


@router.post("/images/delete")
def delete_image(image: str = Form(...)):
    """
    Delete a Docker image by tag or ID.
    """
    try:
        client.images.remove(image=image, force=True)
        return RedirectResponse(url=f"/images?success=Deleted+{image}", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/images?error={str(e).replace(' ', '+')}", status_code=303)
