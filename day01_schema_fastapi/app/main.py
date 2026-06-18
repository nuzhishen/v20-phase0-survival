from fastapi import FastAPI

from app.routes import router

app = FastAPI(
    title="TMS Agent Phase 0 Runtime",
    description="Day 1 FastAPI and Pydantic validation foundation.",
    version="0.1.0",
)
app.include_router(router)
