"""
Diagnosis service
=================
Single entry point the views call. Picks a provider, applies one abstention
policy to whatever answers, and never lets a provider failure take the feature
down.

TIERS
-----
1. crop.health (online, primary)  - 23 major crops, ~300 issues, field-trained.
2. Bundled .h5  (offline, fallback) - 38 PlantVillage classes, lab-trained.

Tier 2 is a genuine asset where there is no network, which is most of rural
India on most days. It is also a liability if used silently: its 38 classes
contain no rice, wheat, cotton, sugarcane, chilli, banana or pulses, so a
photo of any of those still produces a confident answer drawn from the wrong
crop entirely. Results from tier 2 therefore carry limited_coverage=True and
a named crop list, so the UI can say what it does and does not know.

Both tiers return the same dict, so views.py and the templates are unchanged.
"""

import logging

from django.conf import settings

from . import abstention, crop_health

logger = logging.getLogger(__name__)

# Crops the bundled PlantVillage model can speak about at all.
LOCAL_MODEL_CROPS = (
    "Apple", "Blueberry", "Cherry", "Corn (maize)", "Grape", "Orange", "Peach",
    "Bell pepper", "Potato", "Raspberry", "Soybean", "Squash", "Strawberry",
    "Tomato",
)


def _setting(name, default=None):
    return getattr(settings, name, default)


def _read_image_bytes(image_file):
    """
    Bytes to send to the provider, with all metadata removed.

    Scrubbing happens here rather than at the call sites so that nothing can
    reach a third party un-sanitised by forgetting a step. Phone photos embed
    GPS coordinates in EXIF; those used to be stripped from our own stored copy
    but forwarded intact to the API. The privacy policy states that location
    metadata is removed before sending, and this is what makes that true.
    """
    from core.imaging import to_sanitised_bytes

    return to_sanitised_bytes(image_file)


def _local_advice_lookup():
    """
    The agronomy text already written for this app, reused by the API tier.

    Returns None when the local model cannot load (no TensorFlow, missing
    weights), in which case crop.health still answers - just with neutral
    advice text instead of the hand-written knowledge base.
    """
    try:
        from .predictor import plant_disease_predictor
    except Exception as exc:
        logger.warning("Local advice unavailable: %s", exc)
        return None

    if plant_disease_predictor is None:
        return None
    return plant_disease_predictor._get_disease_info


def _annotate_local(result):
    """
    Put a local-model result under the same policy as the API tier.

    The bundled predictor has its own 97% gate, which is a gate on an
    uncalibrated PlantVillage softmax and so is not comparable to crop.health's
    probabilities. The verdict it produces is kept, but treatment advice is
    re-gated here so there is exactly one rule in the codebase about when a
    chemical may be named.
    """
    status = result.get("diagnosis_status", abstention.UNRELIABLE)

    if not abstention.may_show_treatment(status):
        result["solutions"] = []
        result["treatment_withheld"] = True
    else:
        result["treatment_withheld"] = False

    result["provider"] = "local"
    result["limited_coverage"] = True
    result["supported_crops"] = list(LOCAL_MODEL_CROPS)
    result["recommendation"] = abstention.referral_message(status, result.get("crop"))
    return result


def diagnose(image_file, latitude=None, longitude=None):
    """
    Diagnose one uploaded image.

    Returns the PlantDiseasePredictor.predict() contract, plus:
      provider           - "crop.health" or "local"
      treatment_withheld - True when advice was gated by low confidence
      limited_coverage   - True when answered by the 38-class local model
      fallback_reason    - why the primary tier was skipped, if it was

    Raises RuntimeError only when no tier could answer at all.
    """
    api_key = _setting("CROP_HEALTH_API_KEY", "")
    enabled = _setting("CROP_HEALTH_ENABLED", False)
    fallback_reason = None

    if enabled and api_key:
        try:
            client = crop_health.CropHealthClient(
                api_key=api_key,
                base_url=_setting("CROP_HEALTH_BASE_URL", crop_health.DEFAULT_BASE_URL),
                timeout=_setting("CROP_HEALTH_TIMEOUT", 12.0),
                language=_setting("CROP_HEALTH_LANGUAGE", "en"),
            )
            payload = client.identify(
                _read_image_bytes(image_file),
                latitude=latitude,
                longitude=longitude,
            )
            result = crop_health.normalise(
                payload,
                thresholds=abstention.CROP_HEALTH_THRESHOLDS,
                advice_lookup=_local_advice_lookup(),
            )
            result["limited_coverage"] = False
            result["fallback_reason"] = None
            return result

        except crop_health.CropHealthAuthError as exc:
            # Misconfiguration, not an outage. Loud, because every call from
            # here on is silently degrading to the 38-class model.
            logger.error("crop.health auth failed, falling back to local model: %s", exc)
            fallback_reason = "api_auth_failed"
        except crop_health.CropHealthQuotaError as exc:
            logger.error("crop.health out of credits, falling back: %s", exc)
            fallback_reason = "api_quota_exhausted"
        except crop_health.CropHealthUnavailable as exc:
            logger.warning("crop.health unavailable, falling back: %s", exc)
            fallback_reason = "api_unavailable"
        except crop_health.CropHealthError as exc:
            logger.error("crop.health error, falling back: %s", exc)
            fallback_reason = "api_error"
    else:
        fallback_reason = "api_not_configured"

    try:
        from .predictor import plant_disease_predictor
    except Exception as exc:
        raise RuntimeError(
            "No diagnosis provider available: crop.health was skipped "
            "({0}) and the local model failed to load ({1})".format(fallback_reason, exc)
        ) from exc

    if plant_disease_predictor is None:
        raise RuntimeError(
            "No diagnosis provider available: crop.health was skipped "
            "({0}) and the local model is not loaded".format(fallback_reason)
        )

    result = _annotate_local(plant_disease_predictor.predict(image_file))
    result["fallback_reason"] = fallback_reason
    return result
