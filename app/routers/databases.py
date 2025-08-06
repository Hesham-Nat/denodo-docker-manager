# app/routers/databases.py

from fastapi import APIRouter, Request, Query, HTTPException
from app.utils.lifespan import start_db_container, load_database_configs
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from app.utils.helper import *
from docker.errors import ImageNotFound
from docker import from_env

router = APIRouter()
client = from_env()
templates = Jinja2Templates(directory="app/templates")

@router.get("/databases", response_class=HTMLResponse)
async def databases_ui(request: Request):
    """
    List all databases in the yaml file.
    """
    configs = load_database_configs()
    containers = {c.name: c for c in client.containers.list(all=True)}
    dbs = []
    track = 0
    for key, spec in configs.items():
        full_name = spec["name"]
        container = containers.get(full_name)
        status = "not created"

        if container:
            if container.status == "running":
                status = "running"
            else:
                status = container.status

        ports = spec.get("ports", {})
        first_port = next(iter(ports.values()), "N/A")
        track = track + 1
        dbs.append({
            "track": track,
            "key": key,
            "name": full_name.replace("denodo-db-", ""),
            "host": full_name,
            "port": first_port,
            "status": status,
            "image": spec["image"]
        })

    return templates.TemplateResponse("databases.html", {
        "request": request,
        "databases": dbs
    })

@router.post("/databases/{name}/stop")
def stop_db(name: str):
    """
    Stop a database container by name.
    """
    
    try:
        client.containers.get(f"denodo-db-{name}").stop()
        return RedirectResponse(url="/databases?success=Database+stopped", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/databases?error={str(e)}", status_code=303)


@router.get("/databases/{name}/terminal", response_class=HTMLResponse)
async def db_terminal(request: Request, name: str):
    """
    Open terminal interface to a DB container.
    """
    try:
        container = client.containers.get(f"denodo-db-{name}")
        return templates.TemplateResponse("terminal.html", {
            "request": request,
            "container_id": container.id,
            "container_name": container.name
        })
    except Exception as e:
        return HTMLResponse(f"<h1>Error: {str(e)}</h1>", status_code=500)


@router.get("/databases/{name}/logs", response_class=HTMLResponse)
async def view_db_logs(request: Request, name: str, full: bool = Query(False)):
    """
    View logs for a DB container.
    """
    try:
        container = client.containers.get(f"denodo-db-{name}")
        raw_logs = container.logs().decode("utf-8") if full else container.logs(tail=500).decode("utf-8")
        clean_logs = ANSI_ESCAPE.sub('', raw_logs)

        return templates.TemplateResponse("logs.html", {
            "request": request,
            "container_id": container.id,
            "container_name": container.name,
            "logs": clean_logs,
            "full_logs": full
        })

    except Exception as e:
        return templates.TemplateResponse("logs.html", {
            "request": request,
            "container_id": name,
            "container_name": name,
            "logs": f"[Error fetching logs] {str(e)}",
            "full_logs": full
        })

@router.post("/databases/{key}/start")
def start_db(key: str):
    """
    Start a database container by name.
    """
    configs = load_database_configs()
    spec = configs.get(key)
    if not spec:
        raise HTTPException(status_code=404, detail="Database not found")

    image = spec["image"]
    name = spec["name"]

    try:
        # Check if image exists
        client.images.get(image)
    except ImageNotFound:
        # Pull if not found
        print(f"Image {image} not found — pulling...")
        verbose_pull(image)

    print('yes')
    try:
        try:
            container = client.containers.get(name)
            print(container)
            container.start()
        except Exception:
            print('hmm')
            client.containers.run(
                image=spec["image"],
                name=name,
                environment=spec.get("env", {}),
                ports=spec.get("ports", {}),
                detach=True,
                network="denodo-net",
                command=spec.get("command")
            )
        return RedirectResponse(url="/databases?success=Started+" + key, status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/databases?error={str(e)}", status_code=303)