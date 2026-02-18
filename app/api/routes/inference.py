"""
import json
import os
import tensorflow as tf
import numpy as np
from fastapi import APIRouter
from starlette.responses import JSONResponse
from app.core.constants import MODEL_DIR, ANN_DIR, ENS_DIR
from app.models.schemas import ResponseMessage
from app.services.task_manager import load_result_from_disk

ensemble_names = ["ANN1.keras", "ANN2.keras", "ANN3.keras", "ANN4.keras", "ANN5.keras"]

ann = tf.keras.models.load_model(os.path.join(MODEL_DIR, 'ann_smote.keras'))
anns = [
    tf.keras.models.load_model(os.path.join(MODEL_DIR, name))
    for name in ensemble_names
]
label_mapping = {0: "Benign", 1: "Malware"}

router = APIRouter(prefix="/inference", tags=["Model Inference"])

@router.post(
    "/ann",
    status_code=201,
    response_model=ResponseMessage,
    summary="Ann inference",
    description="Get Inference Result From ANN",
    responses={
        500:{
            "description": "Internal Server Error",
            "model": ResponseMessage
        }
    })
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

        predict_path = os.path.join(ANN_DIR, f"predict_{task_id}.json")

        with open(predict_path, "w") as f:
            json.dump(prediction_result, f, indent=4)

        return ResponseMessage(
            code=201,
            status="success",
            data=prediction_result
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ResponseMessage(
                code=500,
                status="failed",
                message="Internal Server Error",
            ).model_dump()
        )

@router.post(
    "/ensemble",
    status_code=201,
    response_model=ResponseMessage,
    summary="Ensemble inference",
    description="Get Inference Result From ANN Ensemble",
    responses={
        500:{
            "description": "Internal Server Error",
            "model": ResponseMessage
        }
    })
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

        predict_path = os.path.join(ENS_DIR, f"predict_{task_id}.json")

        with open(predict_path, "w") as f:
            json.dump(prediction_result, f, indent=4)

        return ResponseMessage(
            code=201,
            status="success",
            data=prediction_result
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=ResponseMessage(
                code=500,
                status="failed",
                message="Internal Server Error",
            ).model_dump()
        )

@router.get(
    "/get/{task_id}",
    response_model=ResponseMessage,
    summary="Get Inference Result",
    description="Get Inference Result from ANN or Ensemble",
    responses={
        400: {
            "description": "Invalid inference type",
            "model": ResponseMessage
        },
        404: {
            "description": "Result not found",
            "model": ResponseMessage
        },
    },
)
def get_prediction(task_id: str, type: str):
    try:
        result = load_result_from_disk(task_id, type)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content=ResponseMessage(
                code=400,
                status="failed",
                message="Invalid inference type",
            ).model_dump()
        )

    if result is None:
        return JSONResponse(
            status_code=404,
            content=ResponseMessage(
                code=404,
                status="failed",
                message="Result not found",
            ).model_dump()
        )

    final_res = dict(result)
    final_res.pop("json_path", None)

    return ResponseMessage(
        code=200,
        status="success",
        data=final_res,
    )

@router.delete(
    "/delete/{task_id}",
    response_model=ResponseMessage,
    summary="Delete Inference Result",
    description="Delete Inference Result from ANN or Ensemble",
    responses={
        404:{
            "description": "Result not found",
            "model": ResponseMessage
        }
    })
def delete_prediction(task_id: str, type: str):
    result = load_result_from_disk(task_id, type)
    if result is None:
        return JSONResponse(
            status_code=404,
            content=ResponseMessage(
                code=404,
                status="failed",
                message="Result not found",
            ).model_dump()
        )

    os.remove(result.get("json_path"))
    return ResponseMessage(
        code=200,
        status="success",
        message="Result successfully deleted"
    )
"""