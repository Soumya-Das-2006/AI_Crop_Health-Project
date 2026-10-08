"""
insect.id provider
==================
Kindwise insect.id client and normaliser.

Covers more than 14,000 taxa of insects and other terrestrial invertebrates
(spiders, mites, snails), with a published "over nine in ten queries accurately
ranked within the top three results" - about 92% top-3. Note that is top-3, not
top-1, which is the whole reason three candidates are always returned.

THE RULE THAT MATTERS HERE
--------------------------
Identifying an insect is NOT the same as deciding it is a pest, and this module
never pretends otherwise. A large share of the insects in a field are
beneficial - pollinators, ladybirds, spiders, parasitoid wasps - and telling a
farmer to spray one is worse than saying nothing: it costs money, kills the
predators that were controlling the actual pest, and makes next season worse.

So the result carries an explicit `pest_status` of "unknown" unless the API's
own taxonomy details say otherwise, and treatment advice is never generated
here. The UI says what the insect is and tells the farmer to confirm with their
KVK officer before treating anything.

API contract: https://insect.kindwise.com/api/v1/openapi.yaml
Keys: https://admin.kindwise.com
"""

import base64
import logging

import requests

from ..plant_disease import abstention

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://insect.kindwise.com"
IDENTIFICATION_PATH = "/api/v1/identification"

# insect.id is a 14,000-taxa fine-grained classifier, so top-1 probabilities sit
# far lower than a 38-class disease head. Gating at disease thresholds would
# mark almost everything unreliable, so these are tuned to the published
# top-3-strong / top-1-weaker shape of the model.
INSECT_THRESHOLDS = abstention.Thresholds(
    reliable_min=55.0,
    caution_min=25.0,
    min_margin=0.12,
    max_entropy=0.80,
)

# Returned when the photo contains no insect at all.
NOT_AN_INSECT = "not_an_insect"


class InsectIdError(Exception):
    """Base class for every insect.id failure."""


class InsectIdAuthError(InsectIdError):
    """Rejected API key. A configuration bug, not an outage."""


class InsectIdQuotaError(InsectIdError):
    """Out of credits."""


class InsectIdUnavailable(InsectIdError):
    """Network, timeout or 5xx. Retryable."""


class InsectIdClient:
    """Thin HTTP client. Interpretation lives in normalise()."""

    def __init__(self, api_key, base_url=DEFAULT_BASE_URL, timeout=12.0, language="en"):
        if not api_key:
            raise ValueError("insect.id API key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        self.language = language

    def identify(self, image_bytes, latitude=None, longitude=None, similar_images=False):
        """
        POST one image and return the parsed payload.

        Location is worth sending: insect.id uses it as a prior, and the same
        photo means different things in Kerala and in Punjab.
        """
        body = {"images": [base64.b64encode(image_bytes).decode("ascii")]}
        if latitude is not None and longitude is not None:
            body["latitude"] = float(latitude)
            body["longitude"] = float(longitude)
        if similar_images:
            body["similar_images"] = True

        url = "{0}{1}".format(self.base_url, IDENTIFICATION_PATH)
        # common_names is the one that matters for a farmer: the bare `name`
        # field is the scientific binomial and means nothing to most people.
        params = {
            "language": self.language,
            "details": "common_names,description,url,image,taxonomy,rank",
        }

        try:
            response = requests.post(
                url,
                json=body,
                params=params,
                headers={"Api-Key": self.api_key, "Content-Type": "application/json"},
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise InsectIdUnavailable(
                "insect.id timed out after {0}s".format(self.timeout)
            ) from exc
        except requests.RequestException as exc:
            raise InsectIdUnavailable("insect.id unreachable: {0}".format(exc)) from exc

        if response.status_code == 401:
            raise InsectIdAuthError("insect.id rejected the API key (401)")
        if response.status_code == 429:
            raise InsectIdQuotaError("insect.id credits exhausted (429)")
        if response.status_code >= 500:
            raise InsectIdUnavailable(
                "insect.id server error {0}".format(response.status_code)
            )
        if response.status_code not in (200, 201):
            raise InsectIdError(
                "insect.id returned {0}: {1}".format(
                    response.status_code, response.text[:300]
                )
            )

        try:
            return response.json()
        except ValueError as exc:
            raise InsectIdError("insect.id returned a non-JSON body") from exc


def _suggestions(payload):
    result = (payload or {}).get("result") or {}
    classification = result.get("classification") or {}
    return [s for s in (classification.get("suggestions") or []) if s]


def _display_names(suggestion):
    """
    (common_name, scientific_name) for one suggestion.

    insect.id has no scientific_name field: the bare `name` IS the binomial,
    and human-readable names arrive under details.common_names. A farmer should
    see "Seven-spotted ladybird", not "Coccinella septempunctata", so the common
    name leads where one exists and the binomial is shown underneath.
    """
    scientific = (suggestion.get("name") or "").strip()
    details = suggestion.get("details") or {}
    common_names = details.get("common_names") or []
    common = (common_names[0] or "").strip() if common_names else ""
    return (common or scientific), scientific


def normalise(payload, thresholds=None):
    """
    Map an insect.id payload onto a result dict for the view and template.

    Deliberately does NOT produce treatment advice. Identification is not a
    pest verdict - see the module docstring.
    """
    thresholds = thresholds or INSECT_THRESHOLDS

    result = (payload or {}).get("result") or {}
    is_insect = result.get("is_insect") or {}
    suggestions = _suggestions(payload)

    top_predictions = []
    for suggestion in suggestions[:3]:
        probability = float(suggestion.get("probability") or 0.0)
        common, scientific = _display_names(suggestion)
        details = suggestion.get("details") or {}
        top_predictions.append({
            "name": common,
            "scientific_name": scientific,
            "confidence": round(probability * 100, 2),
            "id": suggestion.get("id"),
            "description": ((details.get("description") or {}) or {}).get("value", "")
            if isinstance(details.get("description"), dict)
            else (details.get("description") or ""),
            "url": details.get("url", ""),
            "rank": details.get("rank", ""),
            "image": ((details.get("image") or {}) or {}).get("value", "")
            if isinstance(details.get("image"), dict)
            else (details.get("image") or ""),
        })

    probabilities = [float(s.get("probability") or 0.0) for s in suggestions]
    confidence = round(probabilities[0] * 100, 2) if probabilities else 0.0
    margin = round(probabilities[0] - probabilities[1], 4) if len(probabilities) >= 2 else None
    entropy = abstention.normalised_entropy(probabilities)

    if is_insect.get("binary") is False:
        status = NOT_AN_INSECT
    elif not suggestions:
        status = abstention.UNRELIABLE
    else:
        status = abstention.classify(
            confidence, thresholds, margin=margin, entropy=entropy
        )

    name = top_predictions[0]["name"] if top_predictions else "Unknown"
    scientific_name = top_predictions[0]["scientific_name"] if top_predictions else ""

    return {
        "name": name,
        "scientific_name": scientific_name,
        "confidence": confidence,
        "confidence_bar": int(confidence),
        "top_predictions": top_predictions,

        "identification_status": status,
        "confidence_threshold": thresholds.reliable_min,
        "margin": margin,
        "entropy_score": round(entropy, 4) if entropy is not None else None,
        "meets_threshold": status == abstention.RELIABLE,

        # Identification only. Whether this insect is a problem is a separate
        # question that this API does not reliably answer, so the app does not
        # answer it either.
        "pest_status": "unknown",
        "is_insect_probability": (
            round(float(is_insect.get("probability")), 4)
            if is_insect.get("probability") is not None
            else None
        ),

        "status_message": _status_message(status, name, confidence),
        "recommendation": _recommendation(status),
        "status_badge": _status_badge(status),

        "provider": "insect.id",
        "model_version": (payload or {}).get("model_version", ""),
        "access_token": (payload or {}).get("access_token", ""),
    }


def _status_message(status, name, confidence):
    if status == NOT_AN_INSECT:
        return "No insect found in this photo."
    if status == abstention.RELIABLE:
        return "Most likely {0} ({1:.0f}% confidence).".format(name, confidence)
    if status == abstention.CAUTION:
        return "Possibly {0} ({1:.0f}% confidence) - please confirm.".format(name, confidence)
    return "Could not identify this insect with enough confidence."


def _recommendation(status):
    """
    Never a spray instruction. Many field insects are beneficial, and killing a
    predator or pollinator because an app named it is a worse outcome than not
    identifying it at all.
    """
    if status == NOT_AN_INSECT:
        return (
            "Take a clear, close photo of a single insect in daylight, filling "
            "most of the frame."
        )
    if status == abstention.RELIABLE:
        return (
            "Identification only - this does not mean the insect is a pest. "
            "Many field insects are helpful. Confirm with your KVK or "
            "agriculture officer before treating anything."
        )
    if status == abstention.CAUTION:
        return (
            "Not certain. Check all three possibilities below against the "
            "insect, and confirm with your KVK officer before treating."
        )
    return (
        "Not confident enough to name this insect. Try a sharper close-up, or "
        "show it to your local KVK or agriculture officer."
    )


def _status_badge(status):
    return {
        abstention.RELIABLE: {"label": "Confident", "class": "badge-success"},
        abstention.CAUTION: {"label": "Needs confirmation", "class": "badge-warning"},
        abstention.UNRELIABLE: {"label": "Not confident", "class": "badge-danger"},
        NOT_AN_INSECT: {"label": "No insect detected", "class": "badge-secondary"},
    }.get(status, {"label": "Unknown", "class": "badge-secondary"})
