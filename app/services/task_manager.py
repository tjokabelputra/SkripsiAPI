import json
from app.core.constants import RESULT_DIR

task_store: dict[str, dict] = {}

def load_task_from_disk(task_id: str):
    json_path = RESULT_DIR / f"extract_{task_id}.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {
            "status": "completed",
            "json_path": str(json_path),
            "error": None,
            "start_time": data["metadata"].get("start_time"),
            "end_time": data["metadata"].get("end_time"),
            "duration_seconds": data["metadata"].get("duration_seconds"),
            "apk_name": data["metadata"].get("apk_name"),
        }

    return None