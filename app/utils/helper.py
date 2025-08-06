from docker import APIClient
import json
import tempfile
import tarfile
import io
import re
import os
import glob
import yaml
import subprocess

ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def find_license_file(version: str, is_solution_manager: bool):
    folder = f"mount/{version}/license"
    if not os.path.isdir(folder):
        return None

    pattern = "SOL" if is_solution_manager else "SA"
    for file_path in glob.glob(os.path.join(folder, "*.lic")):
        if pattern in os.path.basename(file_path):
            return f"{os.path.abspath(file_path)}:/opt/denodo/conf/denodo.lic"
    return None

def validate_volume_paths(volumes_list):
    for vol in volumes_list:
        try:
            host_path, container_path = vol.split(":", 1)
        except ValueError:
            raise ValueError(f"Invalid volume format: '{vol}'")

        # Normalize Windows paths if needed (optional depending on your setup)
        host_path = os.path.normpath(host_path.strip())

        if not os.path.exists(host_path):
            raise FileNotFoundError(f"Volume path does not exist: {host_path}")

        # If the container path looks like a file, enforce the host path is a file
        if '.' in os.path.basename(container_path.strip()):
            if not os.path.isfile(host_path):
                raise ValueError(f"Expected a file at: {host_path}, but it's missing or not a file")

def make_tarfile(filename, real_path):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w') as tar:
        tar.add(real_path, arcname=filename)
    data.seek(0)
    return data.read()


def create_mount_folders(container_name):
    base_shared = os.path.join("volumes", "denodo_shared", container_name)

    os.makedirs(base_shared, exist_ok=True)

    return base_shared

def create_folder_in_container(container, path):
    """Creates a directory inside the container at the specified path"""
    exit_code, output = container.exec_run(f"mkdir -p {path}")
    if exit_code != 0:
        raise Exception(f"Failed to create folder: {output.decode()}")

def convert_windows_path_to_docker(path):
    if os.name == "nt" and re.match(r"^[A-Za-z]:\\", path):
        drive = path[0]
        rest = path[2:].lstrip("\\").replace("\\", "/")  # <- strip leading slashes
        return f"/mnt/{drive.lower()}/{rest}"
    return path

def verbose_pull(image_name):
    api_client = APIClient(base_url='tcp://localhost:2375')
    for line in api_client.pull(image_name, stream=True, decode=True):
        status = line.get("status", "")
        progress = line.get("progress", "")
        id_ = line.get("id", "")
        if id_:
            print(f"{id_}: {status} {progress}")
        else:
            print(f"{status}")

def verbose_load(fobj):
    api_client = APIClient(base_url='tcp://localhost:2375')
    for raw in api_client.load_image(fobj):
        try:
            # Decode bytes if needed
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")

            # Sometimes Docker SDK gives dict directly
            if isinstance(raw, dict):
                info = raw
            else:
                info = json.loads(raw)

            # Safely extract log info
            message = info.get("stream") or info.get("status") or info.get("error")
            if message:
                for line in str(message).splitlines():
                    print(">>", line.strip())
        except json.JSONDecodeError:
            continue

def save_config_in_container(container, config_dict):
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
        json.dump(config_dict, tmp, indent=2)
        tmp_path = tmp.name

    container.put_archive("/opt/denodo/", make_tarfile("config.json", tmp_path))
    os.unlink(tmp_path)

def save_config_on_host(container_name, config_dict, filename="config.json", output_dir="denodo-container-configuration/"):
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Full path on host
    file_path = os.path.join(output_dir, f"{container_name}-{filename}")

    # Write config to that path
    with open(file_path, "w") as f:
        json.dump(config_dict, f, indent=2)

    return file_path

def mask_env_vars(env_vars):
    masked = []
    for var in env_vars:
        if "PASSWORD=" in var:
            key = var.split("=")[0]
            masked.append(f"{key}=********")
        else:
            masked.append(var)
    return masked


def extract_services_from_compose(path):
    with open(path, "r") as f:
        content = yaml.safe_load(f)
    return content.get("services", {}).keys()

def run_command(command):
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        output_lines = []
        for line in process.stdout:
            print(line.strip())  # You can also write this to a log file
            output_lines.append(line)
        process.wait()
        return process.returncode == 0, ''.join(output_lines)
    except Exception as e:
        return False, str(e)