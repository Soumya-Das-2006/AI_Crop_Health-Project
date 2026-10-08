"""
Insect identification service
=============================
Single entry point the views call.

Unlike plant disease, there is no offline tier here: the bundled .h5 knows
nothing about insects, and shipping a 14,000-taxa classifier on-device is not
realistic. When insect.id is unreachable the feature reports that honestly
rather than guessing - a wrong insect name is not a harmless default.
"""

import logging

from django.conf import settings

from . import insect_id

logger = logging.getLogger(__name__)


class InsectServiceUnavailable(Exception):
    """No provider could answer."""


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


def identify(image_file, latitude=None, longitude=None, client=None):
    """
    Identify one insect photo.

    Returns the normalised result dict. Raises InsectServiceUnavailable when
    the provider is not configured or cannot be reached.
    """
    if client is None:
        api_key = getattr(settings, "INSECT_ID_API_KEY", "")
        enabled = getattr(settings, "INSECT_ID_ENABLED", False)

        if not (enabled and api_key):
            raise InsectServiceUnavailable(
                "insect.id is not configured. Set INSECT_ID_API_KEY in .env."
            )

        client = insect_id.InsectIdClient(
            api_key=api_key,
            base_url=getattr(settings, "INSECT_ID_BASE_URL", insect_id.DEFAULT_BASE_URL),
            timeout=getattr(settings, "INSECT_ID_TIMEOUT", 12.0),
            language=getattr(settings, "INSECT_ID_LANGUAGE", "en"),
        )

    try:
        payload = client.identify(
            _read_image_bytes(image_file), latitude=latitude, longitude=longitude
        )
    except insect_id.InsectIdAuthError as exc:
        logger.error("insect.id auth failed: %s", exc)
        raise InsectServiceUnavailable("Insect identification is misconfigured.") from exc
    except insect_id.InsectIdQuotaError as exc:
        logger.error("insect.id out of credits: %s", exc)
        raise InsectServiceUnavailable(
            "Insect identification has run out of credits."
        ) from exc
    except insect_id.InsectIdError as exc:
        logger.warning("insect.id failed: %s", exc)
        raise InsectServiceUnavailable(
            "Insect identification is unavailable right now."
        ) from exc

    return insect_id.normalise(payload)
