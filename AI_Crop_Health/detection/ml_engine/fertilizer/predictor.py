import os
import joblib
import numpy as np

# ==================================================
# PATH SETUP
# ==================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "fertilizer_model_py312.pkl"
)

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"Fertilizer model not found at: {MODEL_PATH}")

# ==================================================
# LOAD MODEL BUNDLE (LOAD ONCE)
# ==================================================
bundle = joblib.load(MODEL_PATH)

REQUIRED_KEYS = {
    "model",
    "soil_encoder",
    "crop_encoder",
    "fertilizer_encoder",
}

missing = REQUIRED_KEYS - bundle.keys()
if missing:
    raise KeyError(f"Missing keys in model bundle: {missing}")

model = bundle["model"]
soil_encoder = bundle["soil_encoder"]
crop_encoder = bundle["crop_encoder"]
fertilizer_encoder = bundle["fertilizer_encoder"]

if not hasattr(model, "predict_proba"):
    raise TypeError("Loaded model does not support predict_proba()")

EXPECTED_FEATURES = model.n_features_in_

# ==================================================
# DROPDOWN DATA (FOR DJANGO FORMS)
# ==================================================
def get_dropdown_data():
    """
    Returns:
        soil_choices, crop_choices
        [(0, 'Sandy'), (1, 'Clay'), ...]
    """
    soil_choices = list(enumerate(soil_encoder.classes_))
    crop_choices = list(enumerate(crop_encoder.classes_))
    return soil_choices, crop_choices


# ==================================================
# ENCODER HELPERS (SAFE)
# ==================================================
def encode_soil(soil_name: str) -> int:
    if soil_name not in soil_encoder.classes_:
        raise ValueError(f"Unknown soil type: {soil_name}")
    return int(soil_encoder.transform([soil_name])[0])


def encode_crop(crop_name: str) -> int:
    if crop_name not in crop_encoder.classes_:
        raise ValueError(f"Unknown crop type: {crop_name}")
    return int(crop_encoder.transform([crop_name])[0])


# ==================================================
# CONFIDENCE LABEL
# ==================================================
def confidence_label(confidence: float) -> str:
    if confidence >= 85:
        return "High"
    elif confidence >= 60:
        return "Medium"
    return "Low"


# ==================================================
# FERTILIZER PREDICTION
# ==================================================
def predict_fertilizer(features: list):
    """
    Expected feature order (MUST match training):
    [
        temperature,
        humidity,
        soil_encoded,
        crop_encoded,
        nitrogen,
        phosphorus,
        potassium
    ]

    Returns:
    {
        best: str,
        confidence: float,
        accuracy_level: str,
        top_3: [(fertilizer, confidence)]
    }
    """

    # ---------------- VALIDATION ----------------
    if not isinstance(features, (list, tuple)):
        raise ValueError("features must be a list or tuple")

    if len(features) != EXPECTED_FEATURES:
        raise ValueError(
            f"Expected {EXPECTED_FEATURES} features, got {len(features)}"
        )

    # Convert to numpy
    X = np.array(features, dtype=float).reshape(1, -1)

    # ---------------- PREDICTION ----------------
    probs = model.predict_proba(X)[0]

    # Top-3 indices
    top_indices = np.argsort(probs)[::-1][:3]

    # Normalize top-3 probabilities (UI-friendly)
    raw_top = [(idx, probs[idx]) for idx in top_indices]
    total_prob = sum(p for _, p in raw_top)

    top_3 = []
    for idx, prob in raw_top:
        fertilizer = fertilizer_encoder.inverse_transform([idx])[0]
        confidence = round((prob / total_prob) * 100, 2)
        top_3.append((fertilizer, confidence))

    best_fertilizer, best_confidence = top_3[0]

    return {
        "best": best_fertilizer,
        "confidence": best_confidence,
        "accuracy_level": confidence_label(best_confidence),
        "top_3": top_3,
    }
