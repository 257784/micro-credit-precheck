from fastapi import FastAPI

app = FastAPI(title="小微企业授信智能预审系统 F2")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
