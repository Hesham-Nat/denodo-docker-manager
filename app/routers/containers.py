# app/routers/containers.py

from fastapi import APIRouter, Request, Form, UploadFile, File, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, JSONResponse, FileResponse
from app.utils.docker_utils import run_container, verbose_load, validate_volume_paths, container_exists
from app.utils.helper import find_license_file, ANSI_ESCAPE
from app.utils.schemas import CopyRequest
from fastapi.templating import Jinja2Templates
import os, json, shutil, tempfile, asyncio
from docker import from_env

router = APIRouter()
client = from_env()
templates = Jinja2Templates(directory="app/templates")

@router.get("/launch", response_class=HTMLResponse)
async def launch_form(request: Request, tag: str, group: str = Query(...)):
    """
    Show form for launching a Denodo or Solution Manager container.
    """
    is_sm = (group == "solution_manager")
    version = (
        "denodo9" if tag.startswith("9") else
        "denodo8" if tag.startswith("8") else
        "denodo7" if tag.startswith("7") else "unknown"
    )

    license_mount = find_license_file(version, is_sm)
    default_volumes = [license_mount] if license_mount else []

    if is_sm:
        default_ports = ["10091:10091", "10090:10090", "19090:19090"]
        default_env = [
            'DENODO_SM_DATABASE_PROVIDER=SQL_SERVER',
            'DENODO_SM_DATABASE_URI=jdbc:sqlserver://Natrophilite.lan:1433;databaseName=Denodo9DockerDB;schema=solution_mgr;TrustServerCertificate=true',
            'DENODO_SM_DATABASE_DRIVER=com.microsoft.sqlserver.jdbc.SQLServerDriver',
            f"DENODO_SM_DATABASE_USER={os.getenv('DENODO_SM_DATABASE_USER')}",
            f"DENODO_SM_DATABASE_PASSWORD={os.getenv('DENODO_SM_DATABASE_PASSWORD')}",
            'DENODO_SM_DATABASE_PASSWORD_ENCRYPTED=false',
            'DENODO_SM_COPY_JDBC_DRIVERS=mssql-jdbc-10.x'
        ]
        default_volumes.extend([
            r"C:\Users\HeshamNatouf\Desktop\denodo_container_manager\JDBC-Drivers\solution-manager\mssql-jdbc-10.2.0.jre8.jar:/opt/denodo/lib/solution-manager-extensions/mssql-jdbc-10.2.0.jre8.jar",
            r"C:\Users\HeshamNatouf\Desktop\denodo_container_manager\JDBC-Drivers\solution-manager\mysql-connector-j-8.3.0.jar:/opt/denodo/lib/solution-manager-extensions/mysql-connector-j-8.3.0.jar"
        ])
        default_command = "--smserver --smadmin --lmserver" 
    else:
        default_ports = ["9999:9999", "9997:9997", "9996:9996", "9995:9995", "9090:9090"]
        default_env = [
            'DENODO_DATABASE_PROVIDER=sqlserver',
            'DENODO_DATABASE_PROVIDER_VERSION=2019',
            'DENODO_DATABASE_URI=jdbc:sqlserver://Natrophilite.lan:1433;databaseName=Denodo9DockerDB;schema=vdp_admin;encrypt=true;trustServerCertificate=true',
            'DENODO_DATABASE_DRIVER=com.microsoft.sqlserver.jdbc.SQLServerDriver',
            'DENODO_DATABASE_CLASSPATH=mssql-jdbc-10.x',
            f"DENODO_DATABASE_USER={os.getenv('DENODO_DATABASE_USER')}",
            f"DENODO_DATABASE_PASSWORD={os.getenv('DENODO_DATABASE_PASSWORD')}",
        ]
        default_volumes.extend([
            r"C:\Users\HeshamNatouf\Desktop\denodo_container_manager\JDBC-Drivers\data-catalog\mysql-connector-j-8.3.0.jar:/opt/denodo/lib/data-catalog-extensions/mysql-connector-j-8.3.0.jar",
            r"C:\Users\HeshamNatouf\Desktop\denodo_container_manager\JDBC-Drivers\data-catalog\mssql-jdbc-10.2.0.jre8.jar:/opt/denodo/lib/data-catalog-extensions/mssql-jdbc-10.2.0.jre8.jar",
            r"C:\Users\HeshamNatouf\Desktop\denodo_container_manager\JDBC-Drivers\scheduler\mysql-connector-j-8.3.0.jar:/opt/denodo/lib/scheduler-extensions/mysql-connector-j-8.3.0.jar",
            r"C:\Users\HeshamNatouf\Desktop\denodo_container_manager\JDBC-Drivers\scheduler\mssql-jdbc-10.2.0.jre8.jar:/opt/denodo/lib/scheduler-extensions/mssql-jdbc-10.2.0.jre8.jar"
        ])
        default_command = "--vdpserver --designstudio --schserver --schadmin --datacatalog --dmt --monitor"

    return templates.TemplateResponse("launch.html", {
        "request": request,
        "tag": tag,
        "group": group,
        "default_ports": default_ports,
        "default_env": default_env,
        "default_command": default_command,
        "default_volumes": default_volumes,
        "default_hostname": "Natrophilite"
    })


@router.post("/launch")
async def launch_container(
    request: Request,
    tag: str = Form(...),
    group: str = Form(...),
    container_name: str = Form(...),
    hostname: str = Form(...),
    volumes: str = Form(...),
    ports: str = Form(...),
    env_vars: str = Form(...),
    command: str = Form(...)
):
    """
    Launch a container with given configuration.
    """
    try:
        ports_list = [p.strip() for p in ports.splitlines() if p.strip()]
        env_list = [e.strip() for e in env_vars.splitlines() if e.strip()]
        volumes_list = [v.strip() for v in volumes.splitlines() if v.strip()]

        container_id, error_msg = run_container(tag, group, container_name, hostname, volumes_list, ports_list, env_list, command)

        if container_id:
            return RedirectResponse(url="/containers?success=Container+Started+Successfully", status_code=303)
        else:
            return RedirectResponse(url=f"/containers?error={error_msg.replace(' ', '+')}", status_code=303)

    except Exception as e:
        return RedirectResponse(url=f"/containers?error={str(e).replace(' ', '+')}", status_code=303)


@router.get("/containers", response_class=HTMLResponse)
async def list_containers(request: Request):
    """
    List all managed Denodo containers.
    """
    containers = client.containers.list(all=True)
    denodo_containers = []

    for c in containers:
        labels = c.labels or {}
        # Skip containers managed by docker-compose groups
        if "com.docker.compose.project" in labels:
            continue
        # Filter Denodo containers by image tag
        if any("gcr.io/denodo-container/" in t for t in c.image.tags):
            denodo_containers.append({
                "id": c.id[:12],
                "name": c.name,
                "image": c.image.tags[0] if c.image.tags else "unknown",
                "status": c.status
            })

    return templates.TemplateResponse("containers.html", {"request": request, "containers": denodo_containers})


@router.post("/containers/{container_id}/start")
def start_container(container_id: str, request: Request):
    referer = request.headers.get("referer", "/containers")
    try:
        client.containers.get(container_id).start()
        return RedirectResponse(referer, status_code=302)
    except Exception as e:
        return RedirectResponse(f"{referer}?error={str(e)}", status_code=302)

@router.post("/containers/{container_id}/stop")
def stop_container(container_id: str, request: Request):
    referer = request.headers.get("referer", "/containers")
    try:
        client.containers.get(container_id).stop()
        return RedirectResponse(referer, status_code=302)
    except Exception as e:
        return RedirectResponse(f"{referer}?error={str(e)}", status_code=302)

@router.post("/containers/{container_id}/delete")
def delete_container(container_id: str, request: Request):
    referer = request.headers.get("referer", "/containers")
    try:
        container = client.containers.get(container_id)
        container_name = container.name
        container.remove(force=True)

        for path in [f"volumes/denodo_shared/{container_name}", f"volumes/denodo_logs/{container_name}"]:
            if os.path.exists(path):
                shutil.rmtree(path)

        config_path = f"denodo-container-configuration/{container_name}-config.json"
        if os.path.exists(config_path):
            os.remove(config_path)

        return RedirectResponse(referer, status_code=302)

    except Exception as e:
        return RedirectResponse(f"{referer}?error={str(e)}", status_code=302)


@router.get("/containers/{container_id}/logs", response_class=HTMLResponse)
def view_logs(request: Request, container_id: str, full: bool = Query(False)):
    try:
        container = client.containers.get(container_id)
        raw_logs = container.logs().decode("utf-8") if full else container.logs(tail=500).decode("utf-8")
        clean_logs = ANSI_ESCAPE.sub('', raw_logs)
        return templates.TemplateResponse("logs.html", {
            "request": request,
            "container_id": container_id,
            "container_name": container.name,
            "logs": clean_logs,
            "full_logs": full
        })
    except Exception as e:
        return templates.TemplateResponse("logs.html", {
            "request": request,
            "container_id": container_id,
            "container_name": container_id,
            "logs": f"[Error fetching logs] {str(e)}",
            "full_logs": full
        })


@router.get("/containers/{container_id}/logs/raw", response_class=PlainTextResponse)
def get_container_logs_raw(container_id: str, full: bool = Query(False)):
    try:
        container = client.containers.get(container_id)
        raw_logs = container.logs().decode("utf-8") if full else container.logs(tail=500).decode("utf-8")
        return ANSI_ESCAPE.sub('', raw_logs)
    except Exception as e:
        return f"[Error fetching logs] {str(e)}"


@router.get("/containers/{container_id}/logs/download")
def download_container_logs(container_id: str):
    try:
        container = client.containers.get(container_id)
        clean_logs = ANSI_ESCAPE.sub('', container.logs().decode("utf-8"))

        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt") as tmp:
            tmp.write(clean_logs)
            tmp.flush()
            return FileResponse(tmp.name, filename=f"{container.name}_logs.txt", media_type="text/plain")
    except Exception as e:
        return PlainTextResponse(f"[Error downloading logs] {str(e)}", status_code=500)


@router.websocket("/ws/terminal/{container_id}")
async def websocket_terminal(websocket: WebSocket, container_id: str):
    await websocket.accept()
    try:
        container = client.containers.get(container_id)
        exec_instance = client.api.exec_create(container.id, cmd="/bin/bash", tty=True, stdin=True, user="root")
        sock = client.api.exec_start(exec_instance['Id'], tty=True, socket=True)

        loop = asyncio.get_event_loop()

        async def read_from_docker():
            while True:
                try:
                    output = await loop.run_in_executor(None, sock.read, 1024)
                    if not output:
                        break
                    await websocket.send_text(output.decode(errors='ignore'))
                except Exception:
                    break

        async def read_from_websocket():
            while True:
                try:
                    data = await websocket.receive_text()
                    if data:
                        sock._sock.send(data.encode())
                except WebSocketDisconnect:
                    break
                except Exception:
                    break

        await asyncio.wait(
            [asyncio.create_task(read_from_docker()), asyncio.create_task(read_from_websocket())],
            return_when=asyncio.FIRST_COMPLETED
        )

    finally:
        await websocket.close()
        try:
            sock._sock.close()
        except Exception:
            pass


@router.get("/containers/{container_id}/terminal", response_class=HTMLResponse)
async def terminal_page(request: Request, container_id: str):
    try:
        container_name = client.containers.get(container_id).name
    except Exception:
        container_name = container_id
    return templates.TemplateResponse("terminal.html", {
        "request": request,
        "container_id": container_id,
        "container_name": container_name
    })

@router.post("/containers/import-config")
async def import_config(json_file: UploadFile = File(...)):
    """
    Import container config from a JSON file and launch a container.
    """
    try:
        contents = await json_file.read()
        config_data = json.loads(contents)

        volumes = config_data['volumes']
        ports = config_data['ports']
        env_vars = config_data['env_vars']
        tag = config_data['tag']
        container_name = config_data['container_name']
        hostname = config_data['hostname']
        command = config_data['command']
        group = config_data.get('group', 'default')

        volumes_list = [v.strip() for v in volumes]
        ports_list = [p.strip() for p in ports]
        env_list = [e.strip() for e in env_vars]

        validate_volume_paths(volumes_list)

        container_id, error_msg = run_container(
            tag=tag,
            group=group,
            container_name=container_name,
            hostname=hostname,
            volumes_list=volumes_list,
            ports_list=ports_list,
            env_list=env_list,
            command=command
        )

        if container_id:
            return RedirectResponse(url="/containers?success=Config+imported+successfully", status_code=303)
        else:
            return RedirectResponse(url=f"/containers?error={error_msg.replace(' ', '+')}", status_code=303)

    except Exception as e:
        return RedirectResponse(url=f"/containers?error=Failed+to+import+config:+{str(e).replace(' ', '+')}", status_code=303)


@router.post("/containers/{container_id}/copy")
async def copy_in_container(container_id: str, request: CopyRequest):
    """
    Copy a file or directory inside the container from one path to another.
    """
    source = request.source_path.strip()
    target = request.target_path.strip()

    if not source or not target:
        return JSONResponse({"success": False, "message": "Both source and target paths are required."}, status_code=400)

    try:
        container = client.containers.get(container_id)

        # Ensure source path exists
        exec_test = container.exec_run(cmd=["bash", "-c", f'test -e "{source}" && echo "exists" || echo "missing"'])
        if exec_test.exit_code != 0 or exec_test.output.decode().strip() != "exists":
            return JSONResponse({"success": False, "message": f"Source path '{source}' does not exist in the container."}, status_code=400)

        cp_cmd = f'cp -r "{source}" "{target}"'
        exec_cp = container.exec_run(cmd=["bash", "-c", cp_cmd])

        if exec_cp.exit_code != 0:
            return JSONResponse({"success": False, "message": f"Copy command failed: {exec_cp.output.decode().strip()}"}, status_code=500)

        return {"success": True, "message": f"Copied from '{source}' to '{target}' successfully."}

    except Exception as e:
        return JSONResponse({"success": False, "message": f"Error: {str(e)}"}, status_code=500)


@router.get("/containers/{container_id}/rebuild", response_class=HTMLResponse)
async def rebuild_container_form(request: Request, container_id: str):
    """
    Show a form to rebuild a container using a saved config file.
    """
    try:
        container = client.containers.get(container_id)
        container_name = container.name
        config_path = os.path.join("denodo-container-configuration", f"{container_name}-config.json")

        if not os.path.isfile(config_path):
            raise FileNotFoundError(f"Config file not found for container {container_name}.")

        with open(config_path, "r") as f:
            config = json.load(f)

        return templates.TemplateResponse("rebuild.html", {
            "request": request,
            "container_id": container_name,
            **config
        })

    except Exception as e:
        return PlainTextResponse(f"Error: {e}", status_code=303)


@router.post("/containers/{container_id}/rebuild")
async def rebuild_container(
    request: Request,
    container_id: str,
    container_name: str = Form(...),
    hostname: str = Form(...),
    volumes: str = Form(""),
    ports: str = Form(""),
    env_vars: str = Form(""),
    command: str = Form(""),
    tag: str = Form(...),
    group: str = Form(...)
):
    """
    Stop and remove a container and recreate it using new or saved config.
    """
    try:
        old = client.containers.get(container_id)
        old.stop()
        old.remove()

        volumes_list = [v.strip() for v in volumes.strip().splitlines() if v.strip()]
        ports_list = [p.strip() for p in ports.strip().splitlines() if p.strip()]
        env_list = [e.strip() for e in env_vars.strip().splitlines() if e.strip()]

        new_id, error_msg = run_container(
            tag=tag,
            group=group,
            container_name=container_name,
            hostname=hostname,
            volumes_list=volumes_list,
            ports_list=ports_list,
            env_list=env_list,
            command=command
        )

        if new_id:
            return RedirectResponse(url="/containers?success=Container+Started+Successfully", status_code=303)
        else:
            return RedirectResponse(url=f"/containers?error={error_msg.replace(' ', '+')}", status_code=303)

    except Exception as e:
        return RedirectResponse(url=f"/containers?error={str(e).replace(' ', '+')}", status_code=303)

@router.get("/containers/list-all", response_class=HTMLResponse)
async def list_all_containers(request: Request):
    """
    List all containers (running and stopped), with control buttons.
    """
    containers_raw = client.containers.list(all=True)
    containers = []

    for c in containers_raw:
        containers.append({
            "id": c.short_id,
            "name": c.name,
            "image": c.image.tags[0] if c.image.tags else "unknown",
            "status": c.status,
        })

    return templates.TemplateResponse("containers_list_all.html", {
        "request": request,
        "containers": containers
    })