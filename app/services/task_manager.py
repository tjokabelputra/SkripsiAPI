import json
from app.core.constants import RESULT_DIR, PREC_DIR

task_store: dict[str, dict] = {}

def load_task_from_disk(task_id: str):
    json_path = RESULT_DIR / f"extract_{task_id}.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "status": "completed",
            "error": None,
            "json_path": str(json_path),
            "apk_name": data["metadata"].get("apk_name"),
            "apk_size_bytes": data["metadata"].get("apk_size_bytes"),
            "start_time": data["metadata"].get("start_time"),
            "end_time": data["metadata"].get("end_time"),
            "duration_seconds": data["metadata"].get("duration_seconds"),
        }

    return None

def load_result_from_disk(task_id: str):
    json_path = PREC_DIR / f"predict_{task_id}.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "json_path": str(json_path),
            "task_id": data["task_id"],
            "prediction": data["prediction"],
            "malware_probability_percent": data["malware_probability_percent"],
            "benign_probability_percent": data["benign_probability_percent"]
        }

    return None