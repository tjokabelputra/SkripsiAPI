import os
import tempfile
import time
from app.apkAnalyzer import analyze_apk, FEATURE_CSV
from app.services.feature_encoder import save_encoded_csv
from app.services.pca_processor import pca_feature
from app.services.task_manager import task_store
from app.utils.datetime_utils import iso_now

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
            feature_csv_path=FEATURE_CSV
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