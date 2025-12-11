import csv
import uuid
import os
import glob
import json
import time
import tempfile
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from apkAnalyzer import analyze_apk


RESULT_DIR = "results"
os.makedirs(RESULT_DIR, exist_ok=True)

app = FastAPI()

# In memory task tracking
task_store = {}

def iso_now():
    return datetime.utcnow().isoformat() + "Z"

#Load Result from Disk
def load_task_from_disk(task_id):
    # check for JSON (authoritative)
    json_path = os.path.join(RESULT_DIR, f"extract_{task_id}.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "status": "completed",
            "csv_path": os.path.join(RESULT_DIR, f"extract_{task_id}.csv"),
            "json_path": json_path,
            "error": None,
            "start_time": data["metadata"].get("start_time"),
            "end_time": data["metadata"].get("end_time"),
            "duration_seconds": data["metadata"].get("duration_seconds"),
            "apk_name": data["metadata"].get("apk_name")
        }

    # fallback: CSV only (rare)
    csv_path = os.path.join(RESULT_DIR, f"extract_{task_id}.csv")
    if os.path.exists(csv_path):
        return {
            "status": "completed",
            "csv_path": csv_path,
            "json_path": None,
            "error": None,
            "start_time": None,
            "end_time": None,
            "duration_seconds": None,
            "apk_name": None
        }

    return None

# Save result to CSV
def save_to_csv(uid_str, metadata, features):
    csv_path = os.path.join(RESULT_DIR, f"extract_{uid_str}.csv")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Write metadata
        writer.writerow(["_meta_key", "_meta_value"])
        for k, v in metadata.items():
            writer.writerow([k, v])

        writer.writerow([])

        # Write extracted features in model format (1 = present)
        writer.writerow(["feature", "value"])

        # Write min/target SDK
        writer.writerow(["min_sdk", features["min_sdk"]])
        writer.writerow(["target_sdk", features["target_sdk"]])

        # Each permission gets a row
        for p in features["permissions"]:
            writer.writerow([p, 1])

        # Each intent gets a row
        for i in features["intents"]:
            writer.writerow([i, 1])

        # Each API call gets a row
        for api in features["api_calls"]:
            writer.writerow([api, 1])

    return csv_path

# Save to JSON
def save_debug_json(uid_str, features, metadata):
    json_path = os.path.join(RESULT_DIR, f"extract_{uid_str}.json")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "metadata": metadata,
                "features": features
            },
            f,
            indent=4,
            ensure_ascii=False
        )

    return json_path

# Background Extraction
def background_extract(task_id: str, apk_bytes: bytes, filename_hint: str):
    start_time = time.time()
    start_iso = iso_now()

    task_store[task_id]["status"] = "processing"
    task_store[task_id]["start_time"] = start_iso

    try:
        # Write APK to temporary file for Androguard
        with tempfile.NamedTemporaryFile(delete=True, suffix=".apk") as tmp:
            tmp.write(apk_bytes)
            tmp.flush()

            # Run APK analysis
            features = analyze_apk(tmp.name)

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

        #Save to JSON
        debug_json_path = save_debug_json(task_id, features, metadata)

        #Save to CSV
        csv_path = save_to_csv(task_id, metadata, features)

        # Success state
        task_store[task_id]["status"] = "completed"
        task_store[task_id]["json_path"] = debug_json_path
        task_store[task_id]["csv_path"] = csv_path
        task_store[task_id]["duration_seconds"] = duration
        task_store[task_id]["error"] = None

    except Exception as e:
        end_iso = iso_now()
        task_store[task_id]["status"] = "failed"
        task_store[task_id]["json_path"] = None
        task_store[task_id]["csv_path"] = None
        task_store[task_id]["error"] = str(e)
        task_store[task_id]["end_time"] = end_iso
        task_store[task_id]["duration_seconds"] = None

@app.post("/submit")
async def submit_apk(file: UploadFile = File(...), bg: BackgroundTasks = None):

    if not file.filename.lower().endswith(".apk"):
        raise HTTPException(status_code=400, detail="Only APK files are allowed")

    apk_bytes = await file.read()

    # Create unique task ID
    task_id = str(uuid.uuid4())

    # Register task
    task_store[task_id] = {
        "status": "processing",
        "csv_path": None,
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

@app.get("/status/{task_id}")
def get_status(task_id: str):

    # First check memory (running tasks)
    if task_id in task_store:
        return task_store[task_id]

    # If not found, check disk (completed tasks)
    disk_state = load_task_from_disk(task_id)
    if disk_state:
        return disk_state

    raise HTTPException(status_code=404, detail="Task not found")

@app.get("/results/{task_id}")
def download_result(task_id: str):

    # running tasks still rely on RAM
    if task_id in task_store and task_store[task_id]["status"] == "processing":
        raise HTTPException(400, "Still processing")

    # Check disk
    disk_state = load_task_from_disk(task_id)
    if disk_state and disk_state["status"] == "completed":
        csv_path = disk_state["csv_path"]
        return FileResponse(csv_path, media_type="text/csv", filename=f"extract_{task_id}.csv")

    raise HTTPException(404, "Result not found")