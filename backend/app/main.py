from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import close_mongo_connection, connect_to_mongo, ensure_indexes
from app.routers import trips


@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_to_mongo()
    await ensure_indexes()
    yield
    close_mongo_connection()


app = FastAPI(title="AI Trip Planner API", version="1.0.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trips.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
