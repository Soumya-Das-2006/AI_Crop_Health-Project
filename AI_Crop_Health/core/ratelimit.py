"""
Simple per-IP rate limiting for public endpoints.

Uses Django's cache. With the default locmem backend the counters are per
process, which is enough to stop casual abuse but resets on restart and is not
shared between Gunicorn workers. For real protection across workers, configure a
shared cache (Redis or Memcached) in production.
"""

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)


def client_ip(request):
    """
    Best-effort client IP.

    Behind a proxy, REMOTE_ADDR is the proxy, so X-Forwarded-For is used when
    present. That header is client-controllable, so this is suitable for rate
    limiting but NOT for access control or audit evidence.
    """
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or 'unknown'


def is_rate_limited(request, action, limit=5, window_seconds=3600):
    """
    Record one hit and report whether the caller is over the limit.

    Returns True when the request should be refused. Fails open: if the cache
    backend is unavailable the request is allowed rather than blocking every
    visitor.
    """
    key = f'ratelimit:{action}:{client_ip(request)}'
    try:
        # add() only sets the key when absent, so the window starts at the first
        # hit and is not extended by later ones.
        cache.add(key, 0, window_seconds)
        try:
            count = cache.incr(key)
        except ValueError:
            # The key expired between add() and incr().
            cache.set(key, 1, window_seconds)
            count = 1
    except Exception:
        logger.exception('Rate limit check failed for action=%s; allowing', action)
        return False

    if count > limit:
        logger.warning(
            'Rate limit exceeded: action=%s ip=%s count=%s limit=%s',
            action, client_ip(request), count, limit,
        )
        return True
    return False
