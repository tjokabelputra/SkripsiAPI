from fastapi import FastAPI
from app.api.routes.extract import router as extraction_router
from app.api.routes.inference import router as inference_router

app = FastAPI(title="APK Feature Extraction API")

app.include_router(extraction_router, prefix="/v1")
app.include_router(inference_router, prefix="/v1")