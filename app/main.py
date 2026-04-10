from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}
