from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from docker import from_env
import logging
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
client = from_env()

def load_database_configs(path=Path(__file__).parent.parent.parent / "databases" / "databases.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def start_db_container(name, image, ports, env):
    try:
        if not any(c.name == name for c in client.containers.list(all=True)):
            client.containers.run(
                image=image,
                name=name,
                environment=env,
                ports=ports,
                detach=True,
                network="denodo-net"
            )
            logger.info(f"Started container: {name}")
    except Exception as e:
        logger.error(f"Error starting {name}: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting default database containers...")

    db_configs = load_database_configs()
    for key, spec in db_configs.items():
        if spec.get("autostart"):
            start_db_container(
                spec["name"],
                spec["image"],
                spec.get("ports", {}),
                spec.get("env", {})
            )

    yield

    logger.info("Shutting down lifespan context.")
