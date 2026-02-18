import json
from app.core.constants import RESULT_DIR, ANN_DIR, ENS_DIR

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

def load_result_from_disk(task_id: str, type: str):
    if type == "ANN":
        json_path = ANN_DIR / f"predict_{task_id}.json"
    elif type == "Ensemble":
        json_path = ENS_DIR / f"predict_{task_id}.json"
    else:
        raise ValueError("Invalid inference type")

    if not json_path.exists():
        return None

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if type == "ANN":
        return {
            "json_path": str(json_path),
            "task_id": data["task_id"],
            "prediction": data["prediction"],
            "malware_probability_percent": data["malware_probability_percent"],
            "benign_probability_percent": data["benign_probability_percent"],
        }

    voting = data.get("voting", {})
    return {
        "json_path": str(json_path),
        "task_id": data["task_id"],
        "prediction": data["prediction"],
        "voting": {
            "malware_votes": voting.get("malware_votes", 0),
            "benign_votes": voting.get("benign_votes", 0),
            "total_models": voting.get("total_models", 0),
        },
        "malware_probability_percent": data["malware_probability_percent"],
        "benign_probability_percent": data["benign_probability_percent"],
    }