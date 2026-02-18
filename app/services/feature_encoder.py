import os
import csv
from app.core.constants import RESULT_DIR

def load_feature_cols(csv_path):
    cols = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            col = row["ColumnName"].strip()
            if col:
                cols.append(col)

    return cols

def encode_features(features: dict, features_columns: list):
    apk_feature_set = set()
    for key in ["permissions", "intents"]:
        apk_feature_set.update(features.get(key, []))

    row = []
    for col in features_columns:
        row.append(1 if col in apk_feature_set else 0)

    return row

def save_encoded_csv(task_id, features, feature_csv_path):
    features_cols = load_feature_cols(feature_csv_path)
    encoded_row = encode_features(features, features_cols)

    csv_path = os.path.join(RESULT_DIR, f"extract_{task_id}.csv")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(features_cols)
        writer.writerow(encoded_row)

    return csv_path