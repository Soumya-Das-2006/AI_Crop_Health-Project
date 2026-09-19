import logging
import os

import requests

logger = logging.getLogger(__name__)


def geocode_location(location):
    """Resolve a human location to coordinates without breaking form submission."""
    if not location:
        return None

    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={'q': location, 'format': 'jsonv2', 'limit': 1},
            headers={'User-Agent': os.getenv('GEOCODING_USER_AGENT', 'AI-Crop-Health/1.0')},
            timeout=4,
        )
        response.raise_for_status()
        result = response.json()
        if result:
            return float(result[0]['lat']), float(result[0]['lon'])
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        logger.warning('Could not geocode %r: %s', location, exc)
    return None