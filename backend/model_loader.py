from pathlib import Path
import joblib


# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Model paths
MODEL_DIR = BASE_DIR / "models"

XGB_MODEL_PATH = MODEL_DIR / "xgboost.pkl"
SCALER_PATH = MODEL_DIR / "scaler.pkl"


# Load XGBoost model
xgb_model = joblib.load(XGB_MODEL_PATH)

# Load scaler
scaler = joblib.load(SCALER_PATH)


print("XGBoost model loaded successfully.")
print("Scaler loaded successfully.")