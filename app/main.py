# app/main.py
from fastapi import FastAPI
from dotenv import load_dotenv
from app.routers import home, containers, databases, images, compose, about
from fastapi.staticfiles import StaticFiles
from app.utils.lifespan import lifespan
import logging

# Load environment variables
load_dotenv()

# Logging config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI with lifespan (DB containers)
app = FastAPI(lifespan=lifespan)


# Mount all route modules
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(home.router)
app.include_router(containers.router)
app.include_router(databases.router)
app.include_router(images.router)
app.include_router(compose.router)
app.include_router(about.router) 
