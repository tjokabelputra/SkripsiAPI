import json
import os
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
import uuid

from starlette.responses import JSONResponse

from app.models.schemas import (
    ResponseMessage,
    SubmitApkData,
    ExtractionMetadata,
    ExtractionStatus,
    ExtractionResultData
)
from app.services.apk_analyzer import background_extract
from app.services.task_manager import task_store, load_task_from_disk

router = APIRouter(prefix="/extract", tags=["APK Extraction"])

@router.post(
    "/submit",
    status_code=201,
    response_model=ResponseMessage,
    summary="Submit APK for analysis",
    description="Upload an APK file to start background feature extraction and PCA processing.",
    responses={
        400:{
            "description": "Bad Request",
            "model": ResponseMessage,
        },
        500:{
            "description": "Internal Server Error",
            "model": ResponseMessage,
        }
    })
async def submit_apk(file: UploadFile = File(...), bg: BackgroundTasks = None):
    if not file.filename.lower().endswith(".apk"):
        return JSONResponse(
            status_code=400,
            content=ResponseMessage(
                code=400,
                status= "failed",
                message= "File is not APK",
            ).model_dump()
        )

    try:
        apk_bytes = await file.read()
    except Exception:
        return JSONResponse(
            status_code=500,
            content=ResponseMessage(
                code=500,
                status="failed",
                message="Failed to read uploaded file",
            ).model_dump()
        )

    # Create unique task ID
    task_id = str(uuid.uuid4())

    # Register task
    task_store[task_id] = {
        "status": "processing",
        "error": None,
        "start_time": None,
        "end_time": None,
        "duration_seconds": None,
        "apk_name": file.filename
    }

    try:
        # Run background extraction
        bg.add_task(background_extract, task_id, apk_bytes, file.filename)
    except Exception:
        return JSONResponse(
            status_code=500,
            content=ResponseMessage(
                code=500,
                status="failed",
                message="Failed to start background processing",
            ).model_dump()
        )

    return ResponseMessage(
        code=201,
        status="success",
        data=SubmitApkData(task_id=task_id),
        message="APK received. Extraction started."
    )

@router.get(
    "/status/{task_id}",
    response_model=ResponseMessage,
    summary="Get APK extraction status",
    description="Get APK extraction status",
    responses={
        404:{
            "description": "Not Found",
            "model": ResponseMessage,
        },
    })
def get_status(task_id: str):
    # Check Memory
    state = task_store.get(task_id)

    #Check Disk
    if state is None:
        state = load_task_from_disk(task_id)

    if state is None:
        return JSONResponse(
            status_code=404,
            content=ResponseMessage(
                code= 404,
                status= "failed",
                message= "Task not found",
            ).model_dump()
        )

    metadata = ExtractionMetadata(
        task_id=task_id,
        apk_name=state.get("apk_name"),
        apk_size_bytes=state.get("apk_size_bytes", 0),
        start_time=state.get("start_time"),
        end_time=state.get("end_time"),
        duration_seconds=state.get("duration_seconds", 0)
    )

    status_data = ExtractionStatus(
        status=state.get("status"),
        error=state.get("error"),
        metadata=metadata
    )

    return ResponseMessage(
        code=200,
        status="success",
        data=status_data
    )

@router.get(
    "/results/{task_id}",
    response_model=ResponseMessage,
    summary="Get APK extraction result",
    description="Get APK extraction result",
    responses={
        400:{
            "description": "Still Extracting",
            "model": ResponseMessage,
        },
        404:{
            "description": "Not Found",
            "model": ResponseMessage,
        },
        500:{
            "description": "File missing from server",
            "model": ResponseMessage
        }
    })
def download_result(task_id: str):
    # running tasks still rely on RAM
    if task_id in task_store and task_store[task_id]["status"] == "processing":
        return JSONResponse(
            status_code=400,
            content=ResponseMessage(
                code=400,
                status="failed",
                message="Still processing"
            )
        )

    # Check disk
    disk_state = load_task_from_disk(task_id)
    if not disk_state or disk_state.get("status") != "completed":
        return JSONResponse(
            status_code=404,
            content=ResponseMessage(
                code=404,
                status="failed",
                message="Result not found",
            ).model_dump()
        )

    json_path = disk_state.get("json_path")
    if not json_path or not os.path.exists(json_path):
        return JSONResponse(
            status_code=500,
            content=ResponseMessage(
                code=500,
                status="failed",
                message="Result file missing",
            ).model_dump()
        )

    with open(json_path, "r") as f:
        result_json = json.load(f)

    pca_values = result_json.get("pca")
    if pca_values is None:
        return JSONResponse(
            status_code=500,
            content=ResponseMessage(
                code=500,
                status="failed",
                message="PCA data missing",
            ).model_dump()
        )

    metadata = ExtractionMetadata(
        task_id=task_id,
        apk_name=disk_state.get("apk_name"),
        apk_size_bytes=disk_state.get("apk_size_bytes"),
        start_time=disk_state.get("start_time"),
        end_time=disk_state.get("end_time"),
        duration_seconds=disk_state.get("duration_seconds")
    )

    result_data = ExtractionResultData(
        metadata=metadata,
        pca=pca_values
    )

    return ResponseMessage(
        code=200,
        status="success",
        data=result_data
    )

@router.delete(
    "/delete/{task_id}",
    response_model=ResponseMessage,
    summary="Delete APK extraction result",
    description="Delete APK extraction result",
    responses={
        400:{
            "description": "Still processing",
            "model": ResponseMessage,
        },
        404:{
            "description": "Task not found",
            "model": ResponseMessage
        },
        500:{
            "description": "File missing",
            "model": ResponseMessage
        }
    })
def delete_extraction(task_id: str):
    # Block deletion while processing
    if task_id in task_store and task_store[task_id]["status"] == "processing":
        return JSONResponse(
            status_code=400,
            content=ResponseMessage(
                code=400,
                status="failed",
                message="Still processing",
            ).model_dump()
        )

    disk_state = load_task_from_disk(task_id)
    if not disk_state:
        return JSONResponse(
            status_code=404,
            content=ResponseMessage(
                code=404,
                status="failed",
                message="Task not found",
            ).model_dump()
        )

    try:
        json_path = disk_state.get("json_path")
        csv_path = json_path.replace(".json", ".csv")

        if json_path and os.path.exists(json_path):
            os.remove(json_path)
        if csv_path and os.path.exists(csv_path):
            os.remove(csv_path)

        task_store.pop(task_id, None)

    except Exception:
        return JSONResponse(
            status_code=500,
            content=ResponseMessage(
                code=500,
                status="failed",
                message="Failed to delete result files",
            ).model_dump()
        )

    return ResponseMessage(
        code=200,
        status="success",
        message="APK extraction deleted successfully",
    )