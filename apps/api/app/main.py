import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, brd, documents, plans, projects, requests, search
from app.core.config import settings

# Structured run/step logging (agent_runner, tools, ingestion) is emitted at INFO - without this,
# it's silently dropped since the root logger defaults to WARNING and uvicorn only configures its
# own "uvicorn.*" loggers, not "app.*".
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="Spectrace AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(requests.router)
app.include_router(plans.router)
app.include_router(brd.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
