"""
Page translation service
========================
Ported from the upstream AI-Powered-Crop-Health-Diagnosis repository.

The front end (static/assets/js/translator.js) walks the DOM, collects visible
text, and POSTs it here in batches. This module turns those strings into the
target language and caches the result, so the second visitor to a page pays
nothing and the same farmer switching back and forth pays nothing.

PROVIDERS, AND A WARNING ABOUT THEM
-----------------------------------
None of these are paid, contracted services, and that has consequences worth
knowing before this goes in front of real users:

- translate.googleapis.com/translate_a/single?client=gtx is Google's INTERNAL
  endpoint used by their own widgets. It is undocumented, not covered by any
  terms you have accepted, and Google can rate-limit or block it without
  notice. It is first in the chain because it is by far the fastest and best
  quality, which is also why the upstream project chose it.
- MyMemory has a daily quota per IP and starts returning a warning string
  instead of a translation once you cross it. That case is detected and
  treated as a failure so the quota message never reaches a farmer.
- ftapi.pythonanywhere.com is a hobby instance that can disappear.
- LibreTranslate public instances mostly require an API key now, so they are
  only tried when TRANSLATION_FAST_MODE is turned off.

The chain exists because each one individually is unreliable. If this becomes
important to the product, buy a real translation API and put it first; the
shape of this module does not need to change to do that.

PRIVACY
-------
Whatever is on the page gets sent to whichever provider answers. That is fine
for navigation and button labels. It is NOT fine for a farmer's diagnosis
result or chat messages, so those regions are marked data-no-translate in the
templates and the DOM walker skips them. The AI features already answer in the
farmer's own language natively, so nothing is lost by excluding them.
"""

import hashlib
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.conf import settings
from django.core.cache import caches

logger = logging.getLogger(__name__)


def _cache():
    """
    The translations cache, falling back to `default` if the alias is missing.

    A dedicated alias keeps these durable strings out of `default`, which holds
    short-lived objects that must not survive a restart or a migration.
    """
    try:
        return caches["translations"]
    except Exception:
        return caches["default"]

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "mr": "Marathi",
    "te": "Telugu",
    "ta": "Tamil",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "or": "Odia",
    "as": "Assamese",
    "ur": "Urdu",
}

# A single request from the DOM walker can carry a lot of short strings.
MAX_TEXTS_PER_REQUEST = 200


class TranslationUnavailable(RuntimeError):
    """Every provider failed. The caller shows the original English."""


def make_cache_key(target_lang, text):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return "translate:{0}:{1}".format(target_lang, digest)


def _libretranslate_endpoints():
    configured = (getattr(settings, "LIBRETRANSLATE_URL", "") or "").strip()
    fallback = [
        "https://libretranslate.de/translate",
        "https://translate.argosopentech.com/translate",
    ]
    if configured:
        return [configured] + [url for url in fallback if url != configured]
    return fallback


def _try_libretranslate(texts, target_lang, source_lang, timeout):
    """Batch provider. Returns a list, or None if no instance answered."""
    payload = {"q": texts, "source": source_lang, "target": target_lang, "format": "text"}

    for endpoint in _libretranslate_endpoints():
        try:
            response = requests.post(endpoint, json=payload, timeout=timeout)
            response.raise_for_status()
            if "application/json" not in response.headers.get("Content-Type", "").lower():
                logger.warning("LibreTranslate returned non-JSON from %s", endpoint)
                continue
            data = response.json()

            if isinstance(data, dict) and "translatedText" in data:
                translated = data["translatedText"]
                values = translated if isinstance(translated, list) else [translated]
                return [_clean_translation(v) for v in values]
            if isinstance(data, list):
                translated = [item.get("translatedText", "") for item in data]
                if translated:
                    return [_clean_translation(v) for v in translated]
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.warning("LibreTranslate failed at %s: %s", endpoint, exc)
    return None


def _from_gtx(text, source_lang, target_lang, timeout):
    """Google's internal endpoint. Fastest and best, but undocumented."""
    response = requests.get(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": source_lang, "tl": target_lang, "dt": "t", "q": text},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list) and data and isinstance(data[0], list):
        parts = [chunk[0] for chunk in data[0] if isinstance(chunk, list) and chunk]
        joined = "".join(parts).strip()
        if joined:
            return joined
    raise TranslationUnavailable("gtx returned nothing usable")


def _from_ftapi(text, source_lang, target_lang, timeout):
    response = requests.get(
        "https://ftapi.pythonanywhere.com/translate",
        params={"sl": source_lang, "dl": target_lang, "text": text},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    translated = data.get("destination-text") if isinstance(data, dict) else None
    if translated:
        return translated
    raise TranslationUnavailable("ftapi returned nothing usable")


def _from_mymemory(text, source_lang, target_lang, timeout):
    response = requests.get(
        "https://api.mymemory.translated.net/get",
        params={"q": text, "langpair": "{0}|{1}".format(source_lang, target_lang)},
        headers={"User-Agent": "AI-Crop-Health-Translator/1.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    translated = (data.get("responseData") or {}).get("translatedText") if isinstance(data, dict) else None
    # Over quota, MyMemory returns a warning string in place of a translation.
    # Showing that to a farmer would be worse than showing English.
    if translated and "MYMEMORY WARNING" not in translated.upper():
        return translated
    raise TranslationUnavailable("MyMemory quota exceeded or empty")


# MyMemory in particular returns translation-memory markup inside the text,
# e.g. '<g id="1">बाज़ार मूल्य</g>।' for "Market Price". Left alone that either
# renders as visible junk or, if any caller ever switches to innerHTML, becomes
# an injection vector. Providers return text; anything tag-shaped is not ours.
_PROVIDER_MARKUP = re.compile(r"</?[a-zA-Z][^>]*>")


def _clean_translation(text):
    """Strip provider markup and tidy whitespace. Never returns None."""
    if not text:
        return ""
    cleaned = _PROVIDER_MARKUP.sub("", text)
    return " ".join(cleaned.split()).strip()


PROVIDER_CHAIN = (_from_gtx, _from_ftapi, _from_mymemory)


def translate_batch(texts, target_lang, source_lang="en"):
    """
    Translate a list of strings, preserving order.

    Raises TranslationUnavailable only when every provider failed for every
    string - a partial failure returns the original English for the strings
    that could not be translated, which degrades the page rather than breaking
    it.
    """
    if not texts:
        return []

    timeout = getattr(settings, "LIBRETRANSLATE_TIMEOUT", 12)
    workers = max(1, getattr(settings, "TRANSLATION_FALLBACK_WORKERS", 8))

    if not getattr(settings, "TRANSLATION_FAST_MODE", True):
        batched = _try_libretranslate(texts, target_lang, source_lang, timeout)
        if batched and len(batched) == len(texts):
            return batched

    def _one(index, text):
        if not text.strip():
            return index, text
        last_error = None
        for provider in PROVIDER_CHAIN:
            try:
                raw = provider(text, source_lang, target_lang, timeout)
                cleaned = _clean_translation(raw)
                if not cleaned:
                    raise TranslationUnavailable("provider returned only markup")
                return index, cleaned
            except (requests.RequestException, ValueError, KeyError,
                    TranslationUnavailable, RuntimeError) as exc:
                last_error = exc
        raise last_error or TranslationUnavailable("no provider answered")

    translated = [""] * len(texts)
    succeeded = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_one, i, t): i for i, t in enumerate(texts)}
        for future in as_completed(futures):
            index = futures[future]
            try:
                resolved, value = future.result()
                translated[resolved] = value
                succeeded += 1
            except Exception as exc:
                logger.warning("Translation failed for index %s: %s", index, exc)
                translated[index] = texts[index]

    if succeeded == 0:
        # Everything failed at once, which usually means a burst got throttled
        # rather than every provider being down. One slow sequential pass is
        # worth trying before giving up on the whole page.
        time.sleep(0.25)
        for index, text in enumerate(texts):
            try:
                _, value = _one(index, text)
                translated[index] = value
                succeeded += 1
            except Exception:
                translated[index] = text

    if succeeded == 0:
        raise TranslationUnavailable("All translation providers failed")

    return translated


def translate_with_cache(texts, target_lang):
    """
    Translate, reading and writing the shared cache.

    Returns (translations, from_cache, fallback). Duplicate strings - and a
    page is full of them - are translated once and fanned back out.
    """
    cache_ttl = getattr(settings, "TRANSLATION_CACHE_TIMEOUT", 60 * 60 * 24)
    output = [""] * len(texts)
    uncached = {}

    for index, original in enumerate(texts):
        if not original.strip():
            output[index] = original
            continue
        cached = _cache().get(make_cache_key(target_lang, original))
        if cached is not None:
            output[index] = cached
        else:
            uncached.setdefault(original, []).append(index)

    if not uncached:
        return output, True, False

    try:
        unique_texts = list(uncached.keys())
        results = translate_batch(unique_texts, target_lang)
        if len(results) != len(unique_texts):
            raise TranslationUnavailable("provider returned the wrong number of strings")

        for source_text, value in zip(unique_texts, results):
            for position in uncached[source_text]:
                output[position] = value
            _cache().set(make_cache_key(target_lang, source_text), value, cache_ttl)
        return output, False, False

    except TranslationUnavailable:
        # Fall back to the original English rather than a blank page.
        return list(texts), False, True
