import os
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
import uuid
from app.models.schemas import (
    SubmitApkResponse,
    GetAPKExtractionStatusResponse,
    GetAPKExtractionResult,
    DeleteAPKExtractionResult,
)
from app.services.apk_analyzer import background_extract
from app.services.task_manager import task_store, load_task_from_disk

router = APIRouter(prefix="/extract", tags=["APK Extraction"])

@router.post(
    "/submit",
    response_model=SubmitApkResponse,
    summary="Submit APK for analysis",
    description="Upload an APK file to start background feature extraction and PCA processing.")
async def submit_apk(file: UploadFile = File(...), bg: BackgroundTasks = None):

    if not file.filename.lower().endswith(".apk"):
        raise HTTPException(status_code=400, detail="Only APK files are allowed")

    apk_bytes = await file.read()

    # Create unique task ID
    task_id = str(uuid.uuid4())

    # Register task
    task_store[task_id] = {
        "status": "processing",
        "json_path": None,
        "error": None,
        "start_time": None,
        "end_time": None,
        "duration_seconds": None,
        "apk_name": file.filename
    }

    # Run background extraction
    bg.add_task(background_extract, task_id, apk_bytes, file.filename)

    return {
        "task_id": task_id,
        "message": "APK received. Extraction started."
    }

@router.get(
    "/status/{task_id}",
    response_model=GetAPKExtractionStatusResponse,
    summary="Get APK extraction status",
    description="Get APK extraction status")
def get_status(task_id: str):

    # First check memory (running tasks)
    if task_id in task_store:
        return task_store[task_id]

    # If not found, check disk (completed tasks)
    disk_state = load_task_from_disk(task_id)
    if disk_state:
        return disk_state

    raise HTTPException(status_code=404, detail="Task not found")

@router.get(
    "/results/{task_id}",
    response_model=GetAPKExtractionResult,
    summary="Get APK extraction result",
    description="Get APK extraction result")
def download_result(task_id: str):

    # running tasks still rely on RAM
    if task_id in task_store and task_store[task_id]["status"] == "processing":
        raise HTTPException(400, "Still processing")

    # Check disk
    disk_state = load_task_from_disk(task_id)
    if disk_state and disk_state["status"] == "completed":
        json_path = disk_state["json_path"]
        return FileResponse(json_path, media_type="text/json", filename=f"extract_{task_id}.json")

    raise HTTPException(404, "Result not found")

@router.delete(
    "/delete/{task_id}",
    response_model=DeleteAPKExtractionResult,
    summary="Delete APK extraction result",
    description="Delete APK extraction result")
def delete_extraction(task_id: str):
    # Block deletion while processing
    if task_id in task_store and task_store[task_id]["status"] == "processing":
        raise HTTPException(status_code=400, detail="Still processing")

    disk_state = load_task_from_disk(task_id)
    if disk_state and disk_state["status"] == "completed":
        json_path = disk_state["json_path"]
        csv_path = json_path.replace(".json", ".csv")

        if os.path.exists(json_path):
            os.remove(json_path)

        if os.path.exists(csv_path):
            os.remove(csv_path)

        # Optional: clean RAM entry
        task_store.pop(task_id, None)

        return {"message": "Extraction result deleted"}

    raise HTTPException(status_code=404, detail="Result not found")