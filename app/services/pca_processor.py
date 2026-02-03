import json
import os
import joblib
import pandas as pd
from app.core.constants import PCA_DIR, RESULT_DIR


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