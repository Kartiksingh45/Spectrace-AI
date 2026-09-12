from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, documents, evaluation, plans, projects, requests, search
from app.core.config import settings

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
app.include_router(evaluation.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
