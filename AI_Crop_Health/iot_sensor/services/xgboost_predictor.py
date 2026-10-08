"""
XGBoost Crop Predictor (Proposal-aligned)
------------------------------------------
Replaces / wraps the existing sklearn crop predictor.
Uses XGBoost if installed; falls back to the existing
sklearn model transparently — no breaking changes.

Features used: N, P, K, Temperature, Humidity, pH, Rainfall
(same 7 features as detection/ml_engine/crop/predictor.py)
"""

import logging
import os

logger = logging.getLogger(__name__)

FEATURE_NAMES = ["Nitrogen", "Phosphorus", "Potassium",
                 "Temperature", "Humidity", "pH", "Rainfall"]

# ── Try XGBoost first ─────────────────────────────────────────────────────────
_xgb_model = None
_xgb_classes = None

def _load_xgb():
    global _xgb_model, _xgb_classes
    if _xgb_model is not None:
        return True
    try:
        import xgboost as xgb
        BASE = os.path.dirname(__file__)
        model_path = os.path.join(BASE, '..', 'ml_models', 'xgb_crop_model.json')
        classes_path = os.path.join(BASE, '..', 'ml_models', 'xgb_crop_classes.txt')
        if os.path.exists(model_path) and os.path.exists(classes_path):
            _xgb_model = xgb.XGBClassifier()
            _xgb_model.load_model(model_path)
            with open(classes_path) as f:
                _xgb_classes = [l.strip() for l in f if l.strip()]
            logger.info("XGBoost crop model loaded.")
            return True
    except Exception as e:
        logger.debug("XGBoost not available: %s", e)
    return False


# ── Fall back to existing sklearn model ───────────────────────────────────────
def _sklearn_predict(features):
    """Delegate to existing predictor."""
    from detection.ml_engine.crop.predictor import predict_crop
    return predict_crop(features)


# ── Public API ────────────────────────────────────────────────────────────────

def predict_from_sensor(reading):
    """
    Accept a SensorReading object and return prediction dict.
    Falls back to manual 0-values for missing sensor fields.
    """
    features = [
        reading.nitrogen_ppm   or 0,
        reading.phosphorus_ppm or 0,
        reading.potassium_ppm  or 0,
        reading.temperature_c  or 25,
        reading.humidity_pct   or 60,
        reading.soil_ph        or 6.5,
        reading.rainfall_mm    or 0,
    ]
    return predict_crop(features)


def predict_crop(features: list) -> dict:
    """
    Predict best crop. Returns:
        {
            "crop": str,
            "confidence": float (0-100),
            "top3": [{"crop": str, "confidence": float}, ...],
            "model": "xgboost" | "sklearn",
        }
    """
    if _load_xgb() and _xgb_model is not None:
        import numpy as np
        X = np.array(features, dtype=float).reshape(1, -1)
        proba = _xgb_model.predict_proba(X)[0]
        top3_idx = proba.argsort()[::-1][:3]
        return {
            "crop": _xgb_classes[top3_idx[0]],
            "confidence": round(float(proba[top3_idx[0]]) * 100, 2),
            "top3": [
                {"crop": _xgb_classes[i], "confidence": round(float(proba[i]) * 100, 2)}
                for i in top3_idx
            ],
            "model": "xgboost",
        }

    # Fallback
    try:
        result = _sklearn_predict(features)
        return {
            "crop": result.get("crop", "Unknown"),
            "confidence": result.get("confidence", 0),
            "top3": result.get("top3", []),
            "model": "sklearn",
        }
    except Exception as e:
        logger.error("Crop prediction failed: %s", e)
        return {"crop": "Unknown", "confidence": 0, "top3": [], "model": "error"}
