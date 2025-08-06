from docker.errors import ImageNotFound, APIError
from app.utils.helper import *
import docker 
import os

client = docker.from_env()

def ensure_network(network_name="denodo-net"):
    try:
        return client.networks.get(network_name)
    except docker.errors.NotFound:
        print(f"[!] Network '{network_name}' not found. Creating...")
        return client.networks.create(network_name, driver="bridge")
    

def container_exists(container_id):
    try:
        client.containers.get(container_id)
        return True
    except:
        return False
    
def run_container(tag, group, container_name, hostname, volumes_list, ports_list, env_list, command):
    is_sm = (group == "solution_manager")
    if is_sm:
        image_name = f"gcr.io/denodo-container/solution-manager:{tag}"
    else:
        image_name = f"gcr.io/denodo-container/denodo-platform:{tag}"

    try:
        # ✅ Check if image exists
        try:
            client.images.get(image_name)
            print(f"[✓] Image {image_name} found locally")
        except ImageNotFound:
            print(f"[⟳] Image {image_name} not found locally. Pulling from registry...")
            # client.images.pull(image_name)
            verbose_pull(image_name)
            print(f"[✓] Pulled image {image_name} successfully")

        # Parse ports
        port_bindings = {}
        for port_mapping in ports_list:
            host_port, container_port = port_mapping.split(":")
            port_bindings[int(container_port)] = int(host_port)

        shared_path = create_mount_folders(container_name)
        print(f"{convert_windows_path_to_docker(os.path.abspath(shared_path))}")
        volume_bindings = {
            f"{convert_windows_path_to_docker(os.path.abspath(shared_path))}": {'bind': '/opt/denodo/shared/', 'mode': 'rw'},
        }
        for volume in volumes_list:
            volume = volume.strip()
            if not volume:
                continue
            # split on last colon to preserve Windows drive letters
            volume_parts = volume.rsplit(":", 1)
            if len(volume_parts) != 2:
                raise ValueError(f"Invalid volume format: '{volume}'. Use host_path:container_path")
            
            host_path = convert_windows_path_to_docker(volume_parts[0].strip())
            container_path = volume_parts[1].strip()

            volume_bindings[host_path] = {"bind": container_path, "mode": "rw"}
        
        # Parse environment variables
        env_dict = dict(var.split("=", 1) for var in env_list)
        
        network = ensure_network("denodo-net")
        # Run container
        container = client.containers.run(
            image=image_name,
            name=container_name,
            hostname=hostname,
            volumes=volume_bindings,
            ports=port_bindings,
            environment=env_dict,
            command=command,
            detach=True,
            tty=True,
            network="denodo-net"
        )
 
        # create folder inside the container
        create_folder_in_container(container, "/opt/denodo/shared")

        save_config_on_host(container_name, {
            "tag": tag,
            "group": group,
            "container_name": container_name,
            "hostname": hostname,
            "volumes": volumes_list,
            "ports": ports_list,
            "env_vars": env_list,
            "command": command,
            
        })

        return container.id, None

    except ImageNotFound:
        error_msg = f"[✗] Failed to pull image {image_name}"
        print(error_msg)
        return None, error_msg
    except APIError as e:
        error_msg = f"[✗] Docker API error: {str(e)}"
        print(error_msg)
        return None, error_msg
    except Exception as e:
        error_msg = f"[✗] Unexpected error: {str(e)}"
        print(error_msg)
        return None, error_msg
