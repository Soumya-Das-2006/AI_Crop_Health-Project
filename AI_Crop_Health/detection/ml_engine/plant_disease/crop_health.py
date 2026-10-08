"""
crop.health provider
====================
Kindwise crop.health client, normalised onto the exact result contract that
PlantDiseasePredictor.predict() returns, so views and templates need no change.

WHY THIS EXISTS
---------------
The bundled .h5 is a 38-class PlantVillage model covering apple, grape, cherry,
peach, berries, orange, squash, soybean, tomato, potato, maize, bell pepper.
It has no rice, no wheat, no cotton, no sugarcane, no chilli, no banana and no
pulses. For most Indian farmers it cannot be right - it can only be
confidently wrong, because softmax always sums to 1 over the classes it does
have. crop.health covers 23 major crops and roughly 300 health issues, and is
trained on field photographs rather than lab plates.

Vendor's published accuracy, both figures: 85% top-1 / 93% top-3 on their own
validation set, falling to 48% top-1 / 66% top-3 on independent in-the-wild
images. Assume the wild numbers. That is why every result from here goes
through abstention.py.

API contract: https://crop.kindwise.com/api/v1/openapi.yaml
Keys: https://admin.kindwise.com   Cost: roughly EUR 0.01-0.05 per call.
"""

import base64
import logging

import requests

from . import abstention

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://crop.kindwise.com"
IDENTIFICATION_PATH = "/api/v1/identification"


class CropHealthError(Exception):
    """Base class for every crop.health failure."""


class CropHealthAuthError(CropHealthError):
    """Rejected API key. Not retryable, and a configuration bug, not an outage."""


class CropHealthQuotaError(CropHealthError):
    """Out of credits. Retryable only after topping up."""


class CropHealthUnavailable(CropHealthError):
    """Network, timeout or 5xx. Retryable, and safe to fall back from."""


class CropHealthClient:
    """
    Thin HTTP client. Does no interpretation - see normalise() for that.

    Kept separate from the normaliser so the wire format can be tested against
    recorded payloads without touching the network.
    """

    def __init__(self, api_key, base_url=DEFAULT_BASE_URL, timeout=12.0, language="en"):
        if not api_key:
            raise ValueError("crop.health API key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        self.language = language

    def identify(self, image_bytes, latitude=None, longitude=None, similar_images=False):
        """
        POST one image for identification and return the parsed payload.

        latitude/longitude are optional but worth sending: crop.health uses
        location as a prior, and a Maharashtra cotton field and an Italian
        vineyard have very different disease base rates.
        """
        body = {"images": [base64.b64encode(image_bytes).decode("ascii")]}
        if latitude is not None and longitude is not None:
            body["latitude"] = float(latitude)
            body["longitude"] = float(longitude)
        if similar_images:
            body["similar_images"] = True

        url = "{0}{1}".format(self.base_url, IDENTIFICATION_PATH)
        params = {"language": self.language, "details": "description,treatment,common_names"}

        try:
            response = requests.post(
                url,
                json=body,
                params=params,
                headers={"Api-Key": self.api_key, "Content-Type": "application/json"},
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise CropHealthUnavailable(
                "crop.health timed out after {0}s".format(self.timeout)
            ) from exc
        except requests.RequestException as exc:
            raise CropHealthUnavailable("crop.health unreachable: {0}".format(exc)) from exc

        if response.status_code == 401:
            raise CropHealthAuthError("crop.health rejected the API key (401)")
        if response.status_code == 429:
            raise CropHealthQuotaError("crop.health credits exhausted (429)")
        if response.status_code >= 500:
            raise CropHealthUnavailable(
                "crop.health server error {0}".format(response.status_code)
            )
        if response.status_code not in (200, 201):
            raise CropHealthError(
                "crop.health returned {0}: {1}".format(
                    response.status_code, response.text[:300]
                )
            )

        try:
            return response.json()
        except ValueError as exc:
            raise CropHealthError("crop.health returned a non-JSON body") from exc


def _clean(name):
    """Human-readable name, leaving scientific binomials alone."""
    return (name or "").strip()


def _slug(name):
    """Crop___Disease form, matching the label shape the local model emits."""
    return (name or "Unknown").replace(" ", "_")


def _suggestions(payload, key):
    result = (payload or {}).get("result") or {}
    section = result.get(key) or {}
    return [s for s in (section.get("suggestions") or []) if s]


def normalise(payload, thresholds=None, advice_lookup=None):
    """
    Map a crop.health payload onto the PlantDiseasePredictor.predict() contract.

    advice_lookup is an optional callable (disease_name, crop_name) -> dict with
    cause/symptoms/solutions/prevention. Pass the local predictor's
    _get_disease_info so the agronomy text already written for this app is
    reused rather than duplicated; omit it to get neutral placeholder advice.

    Treatment advice is stripped unless the verdict is "reliable". That gating
    is applied here, at the only point where provider output becomes a
    user-facing answer.
    """
    thresholds = thresholds or abstention.CROP_HEALTH_THRESHOLDS

    is_plant = ((payload or {}).get("result") or {}).get("is_plant") or {}
    crop_suggestions = _suggestions(payload, "crop")
    disease_suggestions = _suggestions(payload, "disease")

    crop_name = _clean(crop_suggestions[0].get("name")) if crop_suggestions else "Unknown"
    crop_confidence = (
        round(float(crop_suggestions[0].get("probability") or 0.0) * 100, 2)
        if crop_suggestions
        else 0.0
    )

    # Three candidates, always. See abstention.py for why this is not optional.
    top_predictions = []
    for suggestion in disease_suggestions[:3]:
        probability = float(suggestion.get("probability") or 0.0)
        name = _clean(suggestion.get("name"))
        top_predictions.append(
            {
                # Keys the existing template already reads.
                "class_name": "{0}___{1}".format(_slug(crop_name), _slug(name)),
                "confidence": round(probability * 100, 2),
                # Richer fields the API gives us that the local model cannot.
                "name": name,
                "scientific_name": _clean(suggestion.get("scientific_name")),
                "id": suggestion.get("id"),
            }
        )

    probabilities = [float(s.get("probability") or 0.0) for s in disease_suggestions]
    confidence = round(probabilities[0] * 100, 2) if probabilities else 0.0
    margin = round(probabilities[0] - probabilities[1], 4) if len(probabilities) >= 2 else None
    entropy = abstention.normalised_entropy(probabilities)

    # Not a plant at all: refuse before naming any disease.
    if is_plant.get("binary") is False:
        status = abstention.NOT_A_PLANT
    elif not disease_suggestions:
        status = abstention.UNRELIABLE
    else:
        status = abstention.classify(confidence, thresholds, margin=margin, entropy=entropy)

    disease_name = top_predictions[0]["name"] if top_predictions else "Unknown"
    scientific_name = top_predictions[0]["scientific_name"] if top_predictions else ""

    if advice_lookup is not None and disease_name != "Unknown":
        advice = advice_lookup(disease_name, crop_name)
    else:
        advice = {
            "cause": (
                "{0} reported on {1}.".format(disease_name, crop_name)
                if disease_name != "Unknown"
                else "No disease could be identified from this photo."
            ),
            "symptoms": [],
            "solutions": [],
            "prevention": [],
        }

    show_treatment = abstention.may_show_treatment(status)

    return {
        # Core prediction
        "crop": crop_name,
        "disease": disease_name,
        "scientific_name": scientific_name,
        "confidence": confidence,
        "confidence_bar": int(confidence),
        # The API has no fixed class ordering, so there is no index to report.
        "class_index": -1,
        "class_name": "{0}___{1}".format(_slug(crop_name), _slug(disease_name)),
        "class_label": "{0}___{1}".format(_slug(crop_name), _slug(disease_name)),
        "top_predictions": top_predictions,
        "crop_confidence": crop_confidence,

        # Reliability
        "diagnosis_status": status,
        "confidence_threshold": thresholds.reliable_min,
        "accuracy_threshold": thresholds.reliable_min,
        "raw_confidence": confidence,
        "calibrated_confidence": confidence,
        # Vendor-calibrated against field imagery; we apply no temperature.
        "is_calibrated": True,
        "margin": margin,
        "entropy_score": round(entropy, 4) if entropy is not None else None,
        "meets_threshold": status == abstention.RELIABLE,

        # Advice. Treatment is withheld on anything short of a reliable verdict.
        "cause": advice.get("cause", ""),
        "symptoms": advice.get("symptoms", []),
        "solutions": advice.get("solutions", []) if show_treatment else [],
        "prevention": advice.get("prevention", []),
        "treatment_withheld": not show_treatment,

        # Messaging
        "status_message": _status_message(status, confidence),
        "recommendation": abstention.referral_message(status, crop_name),
        "status_badge": _status_badge(status),

        # Provenance - persisted so a later retrain knows which tier answered.
        "provider": "crop.health",
        "model_version": (payload or {}).get("model_version", ""),
        "access_token": (payload or {}).get("access_token", ""),
        "is_plant_probability": (
            round(float(is_plant.get("probability")), 4)
            if is_plant.get("probability") is not None
            else None
        ),
    }


def _status_message(status, confidence):
    if status == abstention.NOT_A_PLANT:
        return "No plant detected in this photo."
    if status == abstention.RELIABLE:
        return "Likely diagnosis identified ({0:.0f}% confidence).".format(confidence)
    if status == abstention.CAUTION:
        return "Possible diagnosis ({0:.0f}% confidence) - please confirm.".format(confidence)
    return "Could not identify the disease with enough confidence."


def _status_badge(status):
    return {
        abstention.RELIABLE: {"label": "Reliable", "class": "badge-success"},
        abstention.CAUTION: {"label": "Needs confirmation", "class": "badge-warning"},
        abstention.UNRELIABLE: {"label": "Not confident", "class": "badge-danger"},
        abstention.NOT_A_PLANT: {"label": "Not a plant", "class": "badge-secondary"},
    }.get(status, {"label": "Unknown", "class": "badge-secondary"})
