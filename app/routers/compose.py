# app/routers/compose.py

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.utils.docker_utils import run_command, container_exists
import tempfile, shutil, os, json
from docker import from_env

router = APIRouter()
client = from_env()
templates = Jinja2Templates(directory="app/templates")


@router.get("/containers/compose-groups", response_class=HTMLResponse)
def list_compose_groups(request: Request):
    """
    Display all imported Docker Compose groups and their containers.
    """
    group_dir = "docker-compose-groups"
    group_folders = [d for d in os.listdir(group_dir) if os.path.isdir(os.path.join(group_dir, d))]
    groups = []

    for group in group_folders:
        try:
            meta_path = os.path.join(group_dir, group, "metadata.json")
            with open(meta_path) as f:
                meta = json.load(f)
                containers = []
                for cid in meta.get("containers", []):
                    if container_exists(cid):
                        containers.append(client.containers.get(cid).attrs)
                groups.append({"name": group, "containers": containers})
        except Exception as e:
            groups.append({"name": group, "containers": [], "error": str(e)})

    return templates.TemplateResponse("compose_groups.html", {"request": request, "groups": groups})


@router.post("/containers/import-compose")
async def import_compose(group_name: str = Form(...), compose_file: UploadFile = File(...)):
    """
    Import and start a new Docker Compose group from uploaded file.
    """
    try:
        group_dir = os.path.join("docker-compose-groups", group_name)
        if os.path.exists(group_dir):
            return RedirectResponse("/containers/compose-groups?error=Group already exists", status_code=303)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml") as tmp:
            tmp.write(await compose_file.read())
            tmp_path = tmp.name

        # Validate compose file
        success, output = run_command(f"docker compose -f {tmp_path} config")
        if not success:
            os.unlink(tmp_path)
            return RedirectResponse("/containers/compose-groups?error=Invalid compose file", status_code=303)

        # Start containers
        success, output = run_command(f"docker compose -f {tmp_path} -p {group_name} up -d")
        if not success:
            os.unlink(tmp_path)
            return RedirectResponse("/containers/compose-groups?error=Failed to start containers", status_code=303)

        os.makedirs(group_dir, exist_ok=True)
        compose_path = os.path.join(group_dir, "docker-compose.yaml")
        shutil.move(tmp_path, compose_path)

        containers = client.containers.list(all=True, filters={"label": f"com.docker.compose.project={group_name}"})
        container_ids = [c.id for c in containers]

        with open(os.path.join(group_dir, "metadata.json"), "w") as meta:
            json.dump({
                "group_name": group_name,
                "file_path": compose_path,
                "containers": container_ids
            }, meta, indent=2)

        return RedirectResponse("/containers/compose-groups?success=Group imported and started", status_code=303)

    except Exception as e:
        return RedirectResponse(url=f"/containers/compose-groups?error={str(e)}", status_code=303)


@router.post("/containers/compose-groups/{group_name}/start")
def start_group(group_name: str):
    """
    Start all containers in a Docker Compose group.
    """
    try:
        compose_path = f"docker-compose-groups/{group_name}/docker-compose.yaml"
        success, output = run_command(f"docker compose -f {compose_path} -p {group_name} up -d")
        if not success:
            return RedirectResponse(f"/containers/compose-groups?error=Failed to start group: {output}", status_code=303)
        return RedirectResponse("/containers/compose-groups?success=Group started", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/containers/compose-groups?error={str(e)}", status_code=303)


@router.post("/containers/compose-groups/{group_name}/stop")
def stop_group(group_name: str):
    """
    Stop all containers in a Docker Compose group.
    """
    try:
        containers = client.containers.list(filters={"label": f"com.docker.compose.project={group_name}"})
        for c in containers:
            c.stop()
        return RedirectResponse("/containers/compose-groups?success=Group stopped", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/containers/compose-groups?error={str(e)}", status_code=303)


@router.post("/containers/compose-groups/{group_name}/rebuild")
async def rebuild_group(group_name: str):
    """
    Rebuild and restart all containers in a Docker Compose group.
    """
    try:
        compose_path = f"docker-compose-groups/{group_name}/docker-compose.yaml"
        success, output = run_command(f"docker compose -f {compose_path} -p {group_name} up --build -d")
        if not success:
            return RedirectResponse(url=f"/containers/compose-groups?error=Failed to rebuild group: {output}", status_code=303)

        containers = client.containers.list(all=True, filters={"label": f"com.docker.compose.project={group_name}"})
        container_ids = [c.id for c in containers]

        with open(f"docker-compose-groups/{group_name}/metadata.json", "w") as f:
            json.dump({
                "group_name": group_name,
                "file_path": compose_path,
                "containers": container_ids
            }, f, indent=2)

        return RedirectResponse("/containers/compose-groups?success=Group rebuilt", status_code=303)

    except Exception as e:
        return RedirectResponse(url=f"/containers/compose-groupserror={str(e)}", status_code=303)


@router.post("/containers/compose-groups/{group_name}/delete")
def delete_group(group_name: str):
    """
    Delete all containers and files for a Docker Compose group.
    """
    try:
        containers = client.containers.list(all=True, filters={"label": f"com.docker.compose.project={group_name}"})
        for container in containers:
            container.remove(force=True)

        shutil.rmtree(f"docker-compose-groups/{group_name}", ignore_errors=True)
        return RedirectResponse("/containers/compose-groups?success=Group deleted", status_code=303)

    except Exception as e:
        return RedirectResponse(url=f"/containers/compose-groups?error={str(e)}", status_code=303)
