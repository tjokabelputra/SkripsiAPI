import shutil
import uuid
import os
import csv
import json
import time
import tempfile
import joblib
import pandas as pd
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from apkAnalyzer import analyze_apk
from pydantic import BaseModel
from typing import List, Optional

RESULT_DIR = "results"
PCA_DIR = "pca"
os.makedirs(RESULT_DIR, exist_ok=True)

app = FastAPI()

# In memory task tracking
task_store = {}

#Schema
class SubmitApkResponse(BaseModel):
    task_id: str
    message: str

class GetAPKExtractionStatusResponse(BaseModel):
    status: str
    json_path: Optional[str] = None
    error: Optional[str] = None
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    apk_name: str

class ExtractionMetadata(BaseModel):
    task_id: str
    apk_name: str
    apk_size_byte: int
    start_time: str
    end_time: str
    duration_seconds: float

class GetAPKExtractionResult(BaseModel):
    metadata: ExtractionMetadata
    extraction_id: str
    pca: List[float]

class DeleteAPKExtractionResult(BaseModel):
    message: str

def iso_now():
    return datetime.utcnow().isoformat() + "Z"

#Load Result from Disk
def load_task_from_disk(task_id):
    json_path = os.path.join(RESULT_DIR, f"extract_{task_id}.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "status": "completed",
            "json_path": json_path,
            "error": None,
            "start_time": data["metadata"].get("start_time"),
            "end_time": data["metadata"].get("end_time"),
            "duration_seconds": data["metadata"].get("duration_seconds"),
            "apk_name": data["metadata"].get("apk_name")
        }

    return None

# Load Features List
def load_feature_cols(csv_path):
    cols = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            col = row["ColumnName"].strip()
            if col:
                cols.append(col)

    return cols

# Create Encoded Features
def encode_features(features: dict, features_columns: list):
    apk_feature_set = set()
    for key in ["permissions", "intents", "api_calls"]:
        apk_feature_set.update(features.get(key, []))

    row = []
    for col in features_columns:
        if col == "API_MIN":
            value = features.get("min_sdk")
            row.append(int(value) if value is not None else 0)

        elif col == "API":
            value = features.get("target_sdk")
            row.append(int(value) if value is not None else 0)

        else:
            row.append(1 if col in apk_feature_set else 0)

    return row

# Save The Encoded Feature into CSV
def save_encoded_csv(task_id, features, feature_csv_path):
    features_cols = load_feature_cols(feature_csv_path)
    encoded_row = encode_features(features, features_cols)

    csv_path = os.path.join(RESULT_DIR, f"extract_{task_id}.csv")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(features_cols)
        writer.writerow(encoded_row)

    return csv_path

# PCA
def pca_feature(input_csv, extraction_id, metadata):
    model_path = os.path.join(PCA_DIR, "pca_model.joblib")
    output_path = os.path.join(RESULT_DIR, f"extract_{extraction_id}.json")

    try:
        model_pca = joblib.load(model_path)

        input_df = pd.read_csv(input_csv)
        input_df.select_dtypes(include=["number"])

        pca_result = model_pca.transform(input_df)
        pca_array = pca_result.iloc[0].tolist()

        pca_json = {
            "metadata": metadata,
            "extraction_id": extraction_id,
            "pca": pca_array
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(pca_json, f)

        return output_path

    except Exception as e:
        raise RuntimeError(f"PCA processing failed: {e}")


# Background Extraction
def background_extract(task_id: str, apk_bytes: bytes, filename_hint: str):
    start_time = time.time()
    start_iso = iso_now()

    task_store[task_id]["status"] = "processing"
    task_store[task_id]["start_time"] = start_iso

    try:
        # Write APK to temporary file for Androguard
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".apk")
        try:
            tmp.write(apk_bytes)
            tmp.close()

            features = analyze_apk(tmp.name)
        finally:
            os.unlink(tmp.name)

        # Time tracking
        end_time = time.time()
        end_iso = iso_now()
        duration = round(end_time - start_time, 2)

        metadata = {
            "task_id": task_id,
            "apk_name": filename_hint,
            "apk_size_bytes": len(apk_bytes),
            "start_time": start_iso,
            "end_time": end_iso,
            "duration_seconds": duration
        }

        #Save CSV
        csv_path = save_encoded_csv(
            task_id=task_id,
            features=features,
            feature_csv_path="features/cols.csv"
        )

        #Save PCA JSON
        json_path = pca_feature(
            input_csv=csv_path,
            extraction_id=task_id,
            metadata=metadata
        )

        # Success state
        task_store[task_id]["status"] = "completed"
        task_store[task_id]["json_path"] = json_path
        task_store[task_id]["end_time"] = end_iso
        task_store[task_id]["duration_seconds"] = duration
        task_store[task_id]["error"] = None

    except Exception as e:
        end_iso = iso_now()
        task_store[task_id]["status"] = "failed"
        task_store[task_id]["json_path"] = None
        task_store[task_id]["error"] = str(e)
        task_store[task_id]["end_time"] = end_iso
        task_store[task_id]["duration_seconds"] = None

@app.post(
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

@app.get(
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

@app.get(
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

@app.delete(
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