import json
import os
import joblib
import numpy as np
import pandas as pd
from fastapi import HTTPException
from app.core.constants import PCA_DIR, RESULT_DIR
from app.services.task_manager import task_store, load_task_from_disk

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

def load_pca_np(task_id: str):
    if task_id in task_store and task_store[task_id]["status"] == "processing":
        raise HTTPException(400, "Still processing")

    disk_state = load_task_from_disk(task_id)
    if not disk_state or disk_state["status"] != "completed":
        raise HTTPException(404, "Result not found")

    json_path = disk_state["json_path"]

    with open(json_path, "r") as f:
        data = json.load(f)

    pca = data.get("pca")
    if not pca:
        raise HTTPException(422, "PCA data not found in JSON")

    pca_np = np.array(pca).reshape(1, -1)
    return pca_np