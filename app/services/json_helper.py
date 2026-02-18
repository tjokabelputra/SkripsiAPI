import os
import json
import pandas as pd
from app.core.constants import RESULT_DIR

def csv_to_json(input_csv, extraction_id, metadata):
    output_path = os.path.join(RESULT_DIR, f"extract_{extraction_id}.json")

    try:
        # Read CSV
        input_df = pd.read_csv(input_csv)

        # Convert dataframe to list of lists (each row = feature vector)
        data_array = input_df.values.tolist()[0]

        output_json = {
            "metadata": metadata,
            "extraction_id": extraction_id,
            "features": data_array
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_json, f, indent=4)

        return output_path

    except Exception as e:
        raise RuntimeError(f"CSV to JSON processing failed: {e}")