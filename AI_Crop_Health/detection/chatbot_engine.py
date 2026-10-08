"""
AgriBot - the open agriculture chatbot
======================================
Answers any farming question, in the farmer's own language, using two
independent providers so one outage does not take the feature down.

WHY IT WAS REBUILT
------------------
The previous chatbot was a rigid state machine: it demanded a crop, then an
intent, then showed a four-option menu, and only then answered. A farmer
asking "my wheat is yellowing at the tips, what is it" had to walk through a
form before getting a word of help.

Worse, it never reached a model at all. It called
`client.generate_content(...)` on a google-genai Client, which has no such
method; the AttributeError was swallowed and every single conversation fell
through to canned fallback text. The bot people were talking to was a lookup
table pretending to be an AI.

This module replaces both problems: open-ended conversation, and a real model
call with a real second provider behind it.

PROVIDERS
---------
Groq answers first - it is fast, which matters on a phone on rural data.
Gemini is the backup, used when Groq is rate limited, down, or not configured.
Which one answered is recorded on every message, so a silent degradation (Groq
quietly failing and Gemini carrying everything) shows up in the admin rather
than hiding in a log nobody reads.
"""

import logging
import time
import unicodedata

from django.conf import settings

from . import answer_format, groq_client

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 14
MAX_MESSAGE_CHARS = 1000
MAX_MESSAGES_PER_SESSION = 120


class ChatbotUnavailable(Exception):
    """Both providers failed or neither is configured."""


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
# Script detection, not language detection. It cannot tell Hindi from Marathi
# (both Devanagari), and that is fine: the model is told to mirror the user's
# language, and the script is only a hint that strengthens the instruction. It
# exists because "reply in the same language" alone is unreliable for short
# messages like "dhan me keeda", which is Hindi written in Latin script.
_SCRIPT_LANGUAGES = [
    ("DEVANAGARI", "Hindi, Marathi or Nepali (Devanagari script)"),
    ("BENGALI", "Bengali or Assamese (Bengali script)"),
    ("GURMUKHI", "Punjabi (Gurmukhi script)"),
    ("GUJARATI", "Gujarati"),
    ("ORIYA", "Odia"),
    ("TAMIL", "Tamil"),
    ("TELUGU", "Telugu"),
    ("KANNADA", "Kannada"),
    ("MALAYALAM", "Malayalam"),
    ("ARABIC", "Urdu (Arabic script)"),
]

# Words that show up constantly in Hinglish/Banglish farming questions. A
# farmer typing "mere dhan me keeda lag gaya" wants a Hindi answer, not an
# English one, even though every character is ASCII.
_ROMANISED_HINTS = {
    "hindi": [
        "fasal", "kheti", "khet", "paudha", "patta", "keeda", "keede", "dawa",
        "khad", "beej", "sinchai", "pani", "mitti", "rog", "bimari", "upaj",
        "kaise", "kya", "mera", "meri", "hai", "kaun", "kitna", "nahi",
    ],
    "bengali": [
        "fasal", "chash", "gach", "pata", "poka", "sar", "bij", "jol", "mati",
        "rog", "kemon", "kothay", "amar", "ache", "kivabe", "koto",
    ],
}


def detect_language(text):
    """
    Best guess at the language of one message.

    Returns a human-readable description for the prompt, plus a short tag to
    store. Never raises; unknown is a perfectly acceptable answer and simply
    means the model falls back to mirroring whatever it sees.
    """
    if not text or not text.strip():
        return "unknown", "unknown"

    counts = {}
    for char in text:
        if not char.isalpha():
            continue
        try:
            name = unicodedata.name(char)
        except ValueError:
            continue
        for script, label in _SCRIPT_LANGUAGES:
            if name.startswith(script):
                counts[label] = counts.get(label, 0) + 1
                break

    if counts:
        label = max(counts, key=counts.get)
        tag = label.split(",")[0].split(" ")[0].lower()
        return label, tag

    lowered = text.lower()
    words = set(lowered.replace("?", " ").replace(",", " ").split())
    for tag, hints in _ROMANISED_HINTS.items():
        if len(words & set(hints)) >= 2:
            return (
                "{0} written in Latin letters (Romanised). Reply in {0} using "
                "Latin letters too, the way the farmer wrote".format(tag.title()),
                "romanised-" + tag,
            )

    return "English", "english"


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are AgriBot, an experienced agricultural advisor for farmers in India.

SCOPE - you can help with anything farming related:
- Crop selection, varieties, sowing time, spacing, crop rotation
- Soil health, testing, pH, organic matter, land preparation
- Fertiliser and nutrients: NPK, micronutrients, organic manure, dosage timing
- Irrigation, water management, drainage, drip and sprinkler systems
- Pests, diseases, weeds: identifying them and managing them
- Weather, season planning, monsoon, drought and flood response
- Harvesting, storage, post-harvest loss, grading
- Market prices, mandi, MSP, selling and bargaining
- Government schemes, subsidies, crop insurance, KCC, PM-KISAN
- Livestock, poultry, fisheries, beekeeping as they relate to a farm
- Farm machinery, tools, and what is worth renting vs buying
- Organic and natural farming, certification
- Farm economics: cost of cultivation, margins, which crop pays

ANSWER STYLE:
- Answer the question directly in the first sentence. No greeting, no preamble,
  no restating the question.
- Use markdown: `##` headings when the answer has parts, short bullets, and
  **bold** on the action word in each bullet.
- Keep it practical and specific to small Indian farms. Short sentences.
- Give quantities and timing where they matter (per acre, per bigha, days after
  sowing, before or after monsoon).
- If the question is vague, give the most useful general answer AND ask one
  short follow-up question at the end. Never refuse to answer just because
  details are missing.
- End with one short line inviting the next question, only when it helps.

HONESTY RULES:
- Never invent prices, mandi rates, subsidy amounts, scheme deadlines or
  eligibility numbers. If asked, explain how to check (local mandi, agmarknet,
  the scheme's own portal, the KVK) rather than guessing a figure.
- For pesticides and chemicals: you may name categories and active ingredients,
  but always tell the farmer to confirm the product, dose and waiting period
  with a licensed dealer or their KVK officer before buying or spraying.
- Never recommend a chemical for a problem you cannot identify from the
  description. Ask what they can see instead.
- If a question is outside farming, say so in one line and offer to help with a
  farming question instead.
- If you are not sure, say you are not sure and say who can confirm it locally.

SAFETY:
- If someone describes pesticide poisoning or a medical emergency, tell them to
  get to a doctor or call emergency services immediately, before anything else.
"""


def build_prompt(message, history, language_label):
    """
    Assemble the instruction block for one turn.

    The language instruction is repeated at the end as well as the top: with a
    long system prompt in English, a model drifts back into English by the time
    it starts writing unless the requirement is the last thing it reads.
    """
    language_rule = (
        "\nLANGUAGE - this matters:\n"
        "- The farmer is writing in: {0}.\n"
        "- Reply ENTIRELY in that same language and the same script they used.\n"
        "- Keep the markdown structure whatever the language.\n"
        "- Technical terms may stay in English where no common local word "
        "exists, but the sentences around them must be in the farmer's "
        "language.\n"
    ).format(language_label)

    parts = [SYSTEM_PROMPT + language_rule]

    if history:
        lines = [
            "{0}: {1}".format("Farmer" if role == "user" else "AgriBot", content)
            for role, content in history[-MAX_HISTORY_TURNS:]
        ]
        parts.append("Conversation so far:\n" + "\n".join(lines))

    parts.append(
        "Farmer's message: {0}\n\nReply now, in {1}.".format(message, language_label)
    )
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

def _groq_answer(prompt, language_label):
    api_key = getattr(settings, "GROQ_API_KEY", "")
    if not api_key:
        raise groq_client.GroqError("GROQ_API_KEY is empty in this process")

    client = groq_client.GroqClient(
        api_key=api_key,
        base_url=getattr(settings, "GROQ_BASE_URL", groq_client.DEFAULT_BASE_URL),
        timeout=getattr(settings, "GROQ_TIMEOUT", 30.0),
        vision_model=getattr(settings, "GROQ_VISION_MODEL", groq_client.DEFAULT_VISION_MODEL),
        text_model=getattr(settings, "GROQ_TEXT_MODEL", groq_client.DEFAULT_TEXT_MODEL),
    )
    # No image in a chat turn, so this goes straight to the text model.
    answer, model_used, _ = client.complete(
        system_prompt=prompt,
        user_prompt="Reply in {0}.".format(language_label),
        temperature=0.5,
        max_tokens=1200,
    )
    return answer, model_used


def _gemini_answer(prompt):
    """
    Backup provider.

    Calls client.models.generate_content - NOT client.generate_content, which
    is the bug that made the old chatbot silently useless.
    """
    from . import views

    client = getattr(views, "gemini_model", None)
    if client is None:
        raise RuntimeError("Gemini is not configured")

    model_name = getattr(settings, "GEMINI_CHAT_MODEL", "gemini-1.5-flash-8b")

    if getattr(views, "GEMINI_NEW_API", False):
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config={"temperature": 0.5, "max_output_tokens": 1200},
        )
    else:
        response = client.generate_content(prompt)

    return (getattr(response, "text", "") or "").strip(), model_name


def answer(message, history=None, groq_fn=None, gemini_fn=None):
    """
    Answer one chatbot message.

    Returns (text, html, metadata). Raises ChatbotUnavailable only when BOTH
    providers fail - at which point an honest error is the right output, not a
    canned reply dressed up as an answer.
    """
    message = (message or "").strip()
    if not message:
        raise ValueError("Message cannot be empty")
    if len(message) > MAX_MESSAGE_CHARS:
        raise ValueError(
            "Message is too long (max {0} characters)".format(MAX_MESSAGE_CHARS)
        )

    language_label, language_tag = detect_language(message)
    prompt = build_prompt(message, history or [], language_label)

    groq_fn = groq_fn or _groq_answer
    gemini_fn = gemini_fn or _gemini_answer

    started = time.time()
    used_fallback = False
    provider = ""
    model_used = ""
    text = ""
    primary_error = None

    try:
        text, model_used = groq_fn(prompt, language_label)
        provider = "groq"
    except Exception as exc:
        primary_error = exc
        logger.warning("Chatbot: Groq failed, trying Gemini: %s", exc)
        try:
            text, model_used = gemini_fn(prompt)
            provider = "gemini"
            used_fallback = True
        except Exception as exc2:
            logger.error("Chatbot: both providers failed. Groq=%s Gemini=%s", exc, exc2)
            raise ChatbotUnavailable(
                "Groq: {0} | Gemini: {1}".format(exc, exc2)
            ) from exc2

    if not text or not text.strip():
        raise ChatbotUnavailable("{0} returned an empty answer".format(provider))

    return text, answer_format.render_markdown(text), {
        "provider": provider,
        "model_name": model_used,
        "latency_ms": int((time.time() - started) * 1000),
        "used_fallback": used_fallback,
        "language": language_tag,
        "language_label": language_label,
        "primary_error": str(primary_error) if primary_error else "",
    }
