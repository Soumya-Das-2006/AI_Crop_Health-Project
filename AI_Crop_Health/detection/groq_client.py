"""
Groq client
===========
Chat completions against Groq's OpenAI-compatible endpoint, using `requests`
rather than a vendor SDK so there is one HTTP dependency in this project and
one place where timeouts and error mapping are decided.

A NOTE ON VISION
----------------
As of October 2026 Groq lists no *production* model that accepts images. The
only image-capable model in their docs, qwen/qwen3.8-27b, sits under "Preview
models ... intended for evaluation purposes only and should not be used in
production environments". Everything in Groq's production tier
(llama-3.3-70b-versatile, openai/gpt-oss-120b, llama-3.1-8b-instant) is
text-only, and the Llama 4 Scout/Maverick models that used to serve vision
were deprecated in 2026.

So this client is built to degrade: it tries the vision model with the photo,
and if that model rejects the request or has been withdrawn, it retries
text-only against a production model using the structured diagnosis alone.
The answer is weaker without the image, but the feature does not disappear
the day a preview model is pulled. Both model ids are settings, so swapping
to a production vision model later is a config change, not a code change.
"""

import base64
import logging

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
CHAT_PATH = "/chat/completions"

# Preview tier, image-capable. Override with GROQ_VISION_MODEL.
DEFAULT_VISION_MODEL = "qwen/qwen3.8-27b"
# Text-only fallback. Verified present on this project's Groq key - the
# previous default, llama-3.3-70b-versatile, is not served to this account and
# returned "model_not_found" on every call.
DEFAULT_TEXT_MODEL = "openai/gpt-oss-120b"

# Groq rejects images above 20MB with a 400. Stored diagnosis photos are
# compressed to ~84KB on upload, so this is a guard, not a usual path.
MAX_IMAGE_BYTES = 20 * 1024 * 1024


class GroqError(Exception):
    """Base class for every Groq failure."""


class GroqAuthError(GroqError):
    """Rejected API key. A configuration bug, not an outage."""


class GroqRateLimited(GroqError):
    """429. Retryable after a wait."""


class GroqModelUnavailable(GroqError):
    """
    The requested model was rejected - decommissioned, renamed, or not
    entitled to this key. This is the signal to fall back to text-only.
    """


class GroqUnavailable(GroqError):
    """Network, timeout or 5xx. Retryable."""


class GroqClient:
    """One call, one answer. No streaming, no retries beyond the vision fallback."""

    def __init__(
        self,
        api_key,
        base_url=DEFAULT_BASE_URL,
        timeout=30.0,
        vision_model=DEFAULT_VISION_MODEL,
        text_model=DEFAULT_TEXT_MODEL,
    ):
        if not api_key:
            raise ValueError("Groq API key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        self.vision_model = vision_model
        self.text_model = text_model

    # ------------------------------------------------------------------ HTTP

    def _post(self, body):
        url = "{0}{1}".format(self.base_url, CHAT_PATH)
        try:
            response = requests.post(
                url,
                json=body,
                headers={
                    "Authorization": "Bearer {0}".format(self.api_key),
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise GroqUnavailable("Groq timed out after {0}s".format(self.timeout)) from exc
        except requests.RequestException as exc:
            raise GroqUnavailable("Groq unreachable: {0}".format(exc)) from exc

        if response.status_code == 401:
            raise GroqAuthError("Groq rejected the API key (401)")
        if response.status_code == 429:
            raise GroqRateLimited("Groq rate limit reached (429)")
        if response.status_code in (400, 404):
            # Groq answers 400/404 for a decommissioned or unknown model, which
            # is exactly the preview-model-withdrawn case this client exists to
            # survive. Anything else with these codes is a genuine bad request,
            # but retrying text-only is harmless either way.
            raise GroqModelUnavailable(
                "Groq rejected the request ({0}): {1}".format(
                    response.status_code, response.text[:300]
                )
            )
        if response.status_code >= 500:
            raise GroqUnavailable("Groq server error {0}".format(response.status_code))
        if response.status_code != 200:
            raise GroqError(
                "Groq returned {0}: {1}".format(response.status_code, response.text[:300])
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise GroqError("Groq returned a non-JSON body") from exc

        try:
            return (payload["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise GroqError("Groq response had no message content") from exc

    # ----------------------------------------------------------------- public

    @staticmethod
    def image_data_url(image_bytes, mime_type="image/jpeg"):
        """Encode bytes as the data URL Groq's multimodal content array expects."""
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise ValueError("Image exceeds Groq's 20MB limit")
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return "data:{0};base64,{1}".format(mime_type, encoded)

    def complete(
        self,
        system_prompt,
        user_prompt,
        image_bytes=None,
        mime_type="image/jpeg",
        temperature=0.4,
        max_tokens=1200,
        json_mode=False,
    ):
        """
        Ask once, preferring the image-capable model.

        Returns (answer_text, model_used, had_image). Falls back to text-only
        when the vision model is unavailable, so a withdrawn preview model
        degrades the answer instead of breaking the feature.
        """
        if image_bytes:
            try:
                content = [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": self.image_data_url(image_bytes, mime_type)},
                    },
                ]
                answer = self._post({
                    "model": self.vision_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                })
                return answer, self.vision_model, True
            except (GroqModelUnavailable, ValueError) as exc:
                logger.warning(
                    "Groq vision model %s unavailable, retrying text-only: %s",
                    self.vision_model, exc,
                )

        request_body = {
            "model": self.text_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            request_body["response_format"] = {"type": "json_object"}
        answer = self._post(request_body)
        return answer, self.text_model, False
