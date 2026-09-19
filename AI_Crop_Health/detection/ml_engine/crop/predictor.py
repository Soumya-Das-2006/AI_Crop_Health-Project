import joblib
import os
import numpy as np
import logging

# Configure logging
logger = logging.getLogger(__name__)

# ---------------- PATH SETUP ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "crop_model_py312.pkl"
)

FEATURE_NAMES = [
    "Nitrogen", "Phosphorus", "Potassium",
    "Temperature", "Humidity", "pH", "Rainfall"
]

# ---------------- LAZY MODEL LOADING ----------------
# Singleton model instance - loaded only when needed
_model = None


def _load_model():
    """
    Lazily load the model with proper error handling.
    This function loads the model only when first called.
    
    Returns:
        model: The loaded sklearn model
        
    Raises:
        FileNotFoundError: If model file doesn't exist
        Exception: If model fails to load
    """
    global _model
    
    if _model is not None:
        return _model
    
    # Check if model file exists first
    if not os.path.exists(MODEL_PATH):
        logger.error(f"Model file not found at: {MODEL_PATH}")
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}")
    
    try:
        logger.info(f"Loading crop recommendation model from: {MODEL_PATH}")
        _model = joblib.load(MODEL_PATH)
        logger.info("Crop recommendation model loaded successfully")
        return _model
    except Exception as e:
        logger.error(f"Failed to load crop recommendation model: {str(e)}")
        raise


def get_model():
    """
    Public function to get the model instance.
    Use this to access the model safely.
    
    Returns:
        model: The loaded sklearn model or None if failed
    """
    try:
        return _load_model()
    except Exception as e:
        logger.error(f"Error getting model: {str(e)}")
        return None


def is_model_available():
    """
    Check if model is available and loaded.
    
    Returns:
        bool: True if model is available, False otherwise
    """
    global _model
    if _model is not None:
        return True
    
    # Try to load and check
    try:
        _load_model()
        return True
    except Exception:
        return False


# ---------------- PREDICTION ----------------
def predict_crop(features):
    """
    Predict the best crop based on input features.
    Uses lazy loading - model is loaded only when this function is called.
    
    features = [N, P, K, temperature, humidity, ph, rainfall]

    Returns:
      best_crop (str)
      confidence (float)
      suitability (dict: high / medium / low)
      feature_importance (list of dict)
      
    Raises:
      ValueError: If features are invalid
      RuntimeError: If model fails to load
    """
    # -------- Load model lazily --------
    try:
        model = _load_model()
    except Exception as e:
        logger.error(f"Cannot predict - model loading failed: {str(e)}")
        raise RuntimeError(f"ML model is not available: {str(e)}")
    
    if model is None:
        logger.error("Model is None after loading")
        raise RuntimeError("ML model failed to load")

    # -------- Validation --------
    if not isinstance(features, (list, tuple)):
        raise ValueError("features must be a list or tuple of numeric values")
    
    if len(features) != 7:
        raise ValueError("features must be a list of 7 numeric values")
    
    # Validate all values are numeric
    try:
        features = [float(f) for f in features]
    except (TypeError, ValueError) as e:
        raise ValueError(f"All features must be numeric: {str(e)}")

    X = np.array(features, dtype=float).reshape(1, -1)

    # -------- Model prediction --------
    try:
        probs = model.predict_proba(X)[0]
        classes = model.classes_
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}")
        raise RuntimeError(f"Prediction failed: {str(e)}")

    best_idx = int(np.argmax(probs))
    best_crop = classes[best_idx].capitalize()
    confidence = round(float(probs[best_idx]) * 100, 2)

    # -------- Suitability buckets --------
    suitability = {
        "high": [],
        "medium": [],
        "low": []
    }

    for crop, prob in zip(classes, probs):
        score = round(float(prob) * 100, 2)

        if score >= 20:
            suitability["high"].append((crop.capitalize(), score))
        elif score >= 5:
            suitability["medium"].append((crop.capitalize(), score))
        else:
            suitability["low"].append((crop.capitalize(), score))

    # Sort each bucket
    for key in suitability:
        suitability[key].sort(key=lambda x: x[1], reverse=True)

    # -------- Feature importance (for charts) --------
    feature_importance = [
        {
            "feature": name,
            "importance": round(val * 100, 2)
        }
        for name, val in zip(FEATURE_NAMES, model.feature_importances_)
    ]
    feature_importance.sort(key=lambda x: x["importance"], reverse=True)

    logger.info(f"Prediction successful: {best_crop} with {confidence}% confidence")
    
    return best_crop, confidence, suitability, feature_importance
