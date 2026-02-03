from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FEATURE_CSV = BASE_DIR / "data" / "features" / "cols.csv"
RESULT_DIR = BASE_DIR / "data" / "results"
PCA_DIR = BASE_DIR / "data" / "pca"
RESULT_DIR.mkdir(parents=True, exist_ok=True)