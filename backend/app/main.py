import os

from fastapi import FastAPI, HTTPException

from .data import SeedRepository, load_seed
from .models import ApplicationDetail, ApplicationSummary, Enterprise

app = FastAPI(title="小微企业授信智能预审系统 F2")
repository = SeedRepository(load_seed())


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": os.getenv("APP_ENV", "development")}


@app.get("/api/enterprises", response_model=list[Enterprise])
def list_enterprises() -> list[Enterprise]:
    return repository.data.enterprises


@app.get("/api/applications", response_model=list[ApplicationSummary])
def list_applications() -> list[ApplicationSummary]:
    return repository.list_applications()


@app.get("/api/applications/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: str) -> ApplicationDetail:
    detail = repository.get_application(application_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="申请不存在")
    return detail
