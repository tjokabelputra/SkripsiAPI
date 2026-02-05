import json
import os
import tensorflow as tf
import numpy as np
from fastapi import APIRouter, HTTPException
from app.core.constants import MODEL_DIR, PREC_DIR
from app.services.pca_processor import load_pca_np
from app.services.task_manager import load_result_from_disk

ensemble_names = ["ANN1.keras", "ANN2.keras", "ANN3.keras", "ANN4.keras", "ANN5.keras"]

ann = tf.keras.models.load_model(os.path.join(MODEL_DIR, 'ann_smote.keras'))
anns = [
    tf.keras.models.load_model(os.path.join(MODEL_DIR, name))
    for name in ensemble_names
]
label_mapping = {0: "Benign", 1: "Malware"}

router = APIRouter(prefix="/inference", tags=["Model Inference"])

@router.post("/ann")
def predict_ann_smote(task_id: str):
    pca_np = load_pca_np(task_id)

    try:
        pred_ann = ann.predict(pca_np)
        prob = float(pred_ann[0][0])
        pred_label = 1 if prob >= 0.5 else 0
        result = label_mapping[pred_label]

        malware_percent = round(prob * 100, 2)
        benign_percent = round((1 - prob) * 100, 2)

        prediction_result = {
            "task_id": task_id,
            "prediction": result,
            "malware_probability_percent": malware_percent,
            "benign_probability_percent": benign_percent
        }

        predict_path = os.path.join(PREC_DIR, f"predict_{task_id}.json")

        with open(predict_path, "w") as f:
            json.dump(prediction_result, f, indent=4)

        return prediction_result
    except Exception as e:
        raise HTTPException(500, "Internal Server Error")

@router.post("/ensemble")
def predict_ann_ensemble(task_id: str):
    pca_np = load_pca_np(task_id)

    try:
        votes = []
        probs = []
        for model in anns:
            pred = model.predict(pca_np)
            prob = float(pred[0][0])
            probs.append(prob)

            vote = 1 if prob >= 0.5 else 0
            votes.append(vote)

        malware_votes = sum(votes)
        benign_votes = len(votes) - malware_votes

        final_label = 1 if malware_votes > benign_votes else 0
        result = label_mapping[final_label]

        avg_prob = float(np.mean(probs))
        malware_percent = round(avg_prob * 100, 2)
        benign_percent = round((1 - avg_prob) * 100, 2)

        prediction_result = {
            "task_id": task_id,
            "prediction": result,
            "voting": {
                "malware_votes": malware_votes,
                "benign_votes": benign_votes,
                "total_models": len(votes)
            },
            "malware_probability_percent": malware_percent,
            "benign_probability_percent": benign_percent
        }

        predict_path = os.path.join(PREC_DIR, f"predict_{task_id}.json")

        with open(predict_path, "w") as f:
            json.dump(prediction_result, f, indent=4)

        return prediction_result

    except Exception as e:
        raise HTTPException(500, "Internal Server Error")

@router.get("/get/{task_id}")
def get_prediction(task_id: str):
    result = load_result_from_disk(task_id)
    if result is None:
        raise HTTPException(404, "Result not found")

    result.pop("json_path")
    return result

@router.delete("/delete/{task_id}")
def delete_prediction(task_id: str):
    result = load_result_from_disk(task_id)
    if result is None:
        raise HTTPException(404, "Result not found")

    os.remove(result.get("json_path"))
    return {"status": "deleted", "task_id": task_id}