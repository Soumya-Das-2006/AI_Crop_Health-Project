"""
Ask AI
======
Follow-up conversation about an already-diagnosed photo, answered by Groq.

DESIGN RULE THAT MATTERS MOST
-----------------------------
The chat inherits the diagnosis's reliability verdict. When the diagnosis was
not confident enough to show treatment, the assistant is forbidden from naming
a chemical here too, and every answer produced under that rule is stored with
treatment_gated=True.

Without this, Ask AI would be a trivial way around the confidence gate: the
page would withhold a pesticide and the farmer would simply type "what should
I spray?" and get one anyway, from a model that is guessing on top of a
diagnosis the system already said it did not trust.

ANSWER SHAPE
------------
Answers are authored in markdown and rendered by answer_format.py. The prompt
asks for headings, bold actions and short bullets rather than a wall of prose,
because the reader is standing in a field on a phone, not reading an article.
"""

import logging
import time

from django.conf import settings

from . import answer_format, groq_client
from .ml_engine.plant_disease import abstention

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 12
MAX_QUESTION_CHARS = 500

# Hard ceiling per thread. Each turn costs a model call; without a cap one
# conversation can run up an unbounded bill.
MAX_MESSAGES_PER_CONVERSATION = 40


class AskAIUnavailable(Exception):
    """The upstream call failed - network, rate limit, bad response."""


class AskAINotConfigured(AskAIUnavailable):
    """
    No API key on THIS process.

    Split from AskAIUnavailable because the two need different reactions and
    used to be indistinguishable: an outage is "try again in a minute", a
    missing key is "nothing will ever work until someone fixes the server".
    The common cause is a server started before the key was added to .env -
    load_dotenv() runs once at import, so an already-running process never
    sees a key added afterwards and fails every request silently.
    """


# ----------------------------------------------------------------------------
# Preset questions - the chips shown under the answer area.
# ----------------------------------------------------------------------------
# Written for field crops and smallholders rather than houseplants: "is it
# weedy" and "when does it flower" matter to a gardener, while a farmer looking
# at a diseased leaf wants spread, yield loss, cost and timing.
PRESETS = {
    "care": {
        "label": "Care tips",
        "prompt": "What day-to-day care does this plant need right now, given what you can see in the photo?",
    },
    "growing": {
        "label": "Growing conditions",
        "prompt": "What are the best growing conditions for this crop in terms of watering, light and soil, and is anything here suggesting a problem with them?",
    },
    "treatment": {
        "label": "Disease and pest treatment",
        "prompt": "How should this problem be treated?",
    },
    "spread": {
        "label": "Will it spread?",
        "prompt": "Is this likely to spread to the rest of the field or to nearby crops, and how fast?",
    },
    "yield_loss": {
        "label": "Effect on my yield",
        "prompt": "If this is left untreated, what effect will it have on the harvest?",
    },
    "organic": {
        "label": "Organic / low-cost options",
        "prompt": "What low-cost or organic measures can be taken without buying expensive chemicals?",
    },
    "prevent": {
        "label": "How to prevent next season",
        "prompt": "What should be done before and during next season to stop this happening again?",
    },
    "urgency": {
        "label": "How urgent is this?",
        "prompt": "How urgent is this - does it need action today, this week, or is it minor?",
    },
}


# Insects get their own chips. The first one is the question a farmer actually
# has when they photograph a bug: not "what is it" but "is it hurting my crop".
INSECT_PRESETS = {
    "crop_problem": {
        "label": "What problem does it cause in my crop?",
        "prompt": "What damage does this insect do to crops, and which crops does it attack?",
    },
    "harmful_or_helpful": {
        "label": "Is it harmful or helpful?",
        "prompt": "Is this insect a pest, or is it beneficial - a pollinator or a predator of pests? Be clear about which.",
    },
    "signs": {
        "label": "What damage should I look for?",
        "prompt": "What signs of damage should I look for in my field to tell whether this insect is actually causing a problem here?",
    },
    "control": {
        "label": "How do I control it?",
        "prompt": "If this insect is damaging my crop, how should I manage it?",
    },
    "spread": {
        "label": "Will it spread?",
        "prompt": "Will this insect multiply or spread through my field, and how fast?",
    },
    "natural_enemies": {
        "label": "Natural enemies",
        "prompt": "What natural predators or low-cost non-chemical methods keep this insect in check?",
    },
    "prevent": {
        "label": "How to prevent next season",
        "prompt": "What should I do before and during next season to stop this insect becoming a problem?",
    },
    "urgency": {
        "label": "How urgent is this?",
        "prompt": "How urgent is this - does it need action today, this week, or is it minor?",
    },
}


def preset_choices(kind="plant"):
    """[(id, label)] for the UI chips and for admin filters."""
    presets = INSECT_PRESETS if kind == "insect" else PRESETS
    return [(key, value["label"]) for key, value in presets.items()]


def resolve_question(preset, question, kind="plant"):
    """
    Turn a chip id or a typed question into the text actually asked.

    Returns (question_text, preset_id). Raises ValueError on bad input, so the
    view can answer 400 rather than sending junk upstream.
    """
    presets = INSECT_PRESETS if kind == "insect" else PRESETS

    if preset:
        if preset not in presets:
            raise ValueError("Unknown preset: {0}".format(preset))
        return presets[preset]["prompt"], preset

    question = (question or "").strip()
    if not question:
        raise ValueError("Question cannot be empty")
    if len(question) > MAX_QUESTION_CHARS:
        raise ValueError(
            "Question is too long (max {0} characters)".format(MAX_QUESTION_CHARS)
        )
    return question, ""


# ----------------------------------------------------------------------------
# Prompt construction
# ----------------------------------------------------------------------------

BASE_RULES = """You are an agricultural advisor helping a smallholder farmer in India.
You are looking at a photo the farmer uploaded and at an automated diagnosis of it.

ANSWER FORMAT - follow this exactly:
- Write in markdown.
- Open with one short sentence that answers the question directly. No preamble,
  no restating the question.
- Then use `##` headings to break the answer into 2-4 short sections.
- Under each heading use bullet points, not paragraphs.
- Bold the action word in each bullet, like "**Water at the base** - not overhead."
- Keep every bullet to one line a farmer can act on.
- Where steps have an order or a timing, say when: today, this week, before sowing.
- Finish with a `##` section of 2-4 one-line "do this first" points.
- End with a single short line offering to narrow the advice if the farmer tells
  you their district, season or crop stage.

CONTENT RULES:
- Be concrete and practical. No botanical prose, no filler.
- Reply in the same language the farmer writes in. If they write Hindi, answer in
  Hindi; Bengali, answer in Bengali. Keep the markdown structure either way.
- Never invent prices, brand availability or government scheme details.
- If the question is not about farming or this plant, say so in one line and stop.
- Never claim more certainty than the diagnosis below supports.
- Do not use h1. Start headings at `##`."""

TREATMENT_ALLOWED = """
- The diagnosis is confident. You may describe treatment, including the types of
  active ingredient that work, but tell the farmer to confirm the exact product
  and dose with a licensed dealer or their KVK officer before buying."""

TREATMENT_WITHHELD = """
- IMPORTANT: this diagnosis is NOT confident enough to name a treatment.
  Do NOT name any pesticide, fungicide, insecticide, brand or active ingredient,
  and do NOT give doses or spray schedules, even if the farmer asks directly or
  insists or says it is urgent.
- Instead: describe what to look for to confirm the problem, suggest non-chemical
  steps that are safe whatever the cause (removing affected leaves, improving
  drainage and airflow, field hygiene), and tell the farmer to show the plant to
  their local KVK or agriculture officer before buying anything.
- If asked what to spray, explain plainly that naming a chemical on an uncertain
  diagnosis risks wasting their money and not saving the crop."""


INSECT_RULES_HEAD = """You are an agricultural entomology advisor helping a smallholder
farmer in India. You are looking at a photo of an insect the farmer found, and at an
automated identification of it."""

INSECT_CONTROL_ALLOWED = """
- The identification is confident enough to discuss this insect specifically.
- Say plainly and early whether it is a PEST, a BENEFICIAL insect (pollinator or
  predator of pests), or usually harmless. This is the single most important thing
  the farmer needs to know.
- If it is beneficial, say clearly that it should NOT be killed, and explain what
  it is doing for the crop.
- If it is a pest, describe the damage, the crops affected, and management -
  starting with cultural and biological methods. You may mention categories of
  treatment, but tell the farmer to confirm the exact product and dose with a
  licensed dealer or their KVK officer before buying."""

INSECT_CONTROL_WITHHELD = """
- IMPORTANT: this identification is NOT confident. Do NOT name any insecticide,
  brand, active ingredient or dose, and do not state definitively that this insect
  is a pest - you may be looking at a beneficial species.
- Explain what to check to confirm the identification and whether real damage is
  present, and tell the farmer to show the insect to their local KVK or agriculture
  officer before treating anything.
- Say plainly that spraying on an uncertain insect identification risks killing the
  predators and pollinators that are protecting the crop, which makes the problem
  worse."""


def build_insect_system_prompt(insect_log, control_allowed):
    """
    Instruction block for an insect thread.

    The standing rule from the insect module carries through here: naming a
    species is not the same as declaring it a pest, and most field insects are
    not pests. The prompt makes the model state which it is before anything
    else, because that is what decides whether the farmer reaches for a sprayer.
    """
    # Same formatting and content rules as the plant side - one answer style
    # across the app - with insect-specific control rules swapped in.
    rules = INSECT_RULES_HEAD + "\n\n" + BASE_RULES + (
        INSECT_CONTROL_ALLOWED if control_allowed else INSECT_CONTROL_WITHHELD
    )

    confidence = insect_log.confidence or 0
    facts = [
        "Automated identification of the attached photo:",
        "- Most likely: {0}".format(insect_log.common_name or "unknown"),
        "- Scientific name: {0}".format(insect_log.scientific_name or "unknown"),
        "- Confidence: {0:.0f}%".format(confidence),
        "- Reliability verdict: {0}".format(insect_log.identification_status),
        "- Source: insect.id, a 14,000-taxon classifier (about 92% top-3 accuracy,"
        " so the top-1 answer is often wrong on its own)",
    ]

    others = [
        c.get("name") for c in (insect_log.top_predictions or [])[1:] if c.get("name")
    ]
    if others:
        facts.append("- Other candidates: {0}".format(", ".join(others)))

    if confidence and confidence < 40:
        facts.append(
            "- Confidence is low. Say so in your opening sentence and cover the "
            "candidates rather than committing to one species."
        )

    return rules + "\n\n" + "\n".join(facts)


def build_system_prompt(diagnosis_log, treatment_allowed):
    """Assemble the instruction block, including this diagnosis's facts."""
    rules = BASE_RULES + (TREATMENT_ALLOWED if treatment_allowed else TREATMENT_WITHHELD)

    confidence = diagnosis_log.calibrated_confidence or 0

    facts = [
        "Automated diagnosis of the attached photo:",
        "- Crop: {0}".format(diagnosis_log.predicted_crop or "unknown"),
        "- Suspected problem: {0}".format(diagnosis_log.predicted_disease or "unknown"),
        "- Confidence: {0:.0f}%".format(confidence),
        "- Reliability verdict: {0}".format(diagnosis_log.diagnosis_status),
        "- Source: {0}".format(
            "field-trained crop.health model"
            if diagnosis_log.provider == "crop.health"
            else "offline model limited to 14 crops, may be wrong about the crop itself"
        ),
    ]

    if diagnosis_log.provider != "crop.health":
        facts.append(
            "- WARNING: the offline model does not know rice, wheat, cotton, "
            "sugarcane, chilli, banana or pulses. If the photo looks like one "
            "of those, say the crop identification is unreliable."
        )

    if confidence and confidence < 50:
        facts.append(
            "- The confidence is low. Say so in your opening sentence and give "
            "guidance that holds for the likely candidates rather than "
            "committing to one."
        )

    return rules + "\n\n" + "\n".join(facts)


def build_user_prompt(conversation, question_text):
    """The farmer's question, preceded by any earlier turns in this thread."""
    messages = list(conversation.messages.order_by("created_at", "id"))
    history = [
        "{0}: {1}".format("Farmer" if m.role == "user" else "Advisor", m.content)
        for m in messages[-MAX_HISTORY_TURNS:]
        if m.content
    ]

    parts = []
    if history:
        parts.append("Conversation so far:\n" + "\n".join(history))
    parts.append("Farmer's question: {0}".format(question_text))
    return "\n\n".join(parts)


def _load_image_bytes(diagnosis_log):
    """
    Read the stored photo for the vision call.

    Returns (bytes, mime_type) or (None, None). A missing file degrades the
    answer rather than failing it: losing the whole feature because one upload
    was cleaned up is worse than answering from the diagnosis facts alone.
    """
    image_field = diagnosis_log.uploaded_image
    if not image_field:
        return None, None
    try:
        from core.imaging import to_sanitised_bytes

        image_field.open("rb")
        # Stored copies are already EXIF-free, but this is the only guarantee
        # that holds if the storage path ever stops stripping metadata.
        data = to_sanitised_bytes(image_field)
        image_field.close()
    except Exception as exc:
        logger.warning(
            "Ask AI could not load image for diagnosis %s: %s", diagnosis_log.pk, exc
        )
        return None, None

    name = (getattr(image_field, "name", "") or "").lower()
    mime = "image/png" if name.endswith(".png") else "image/jpeg"
    return data, mime


def _build_client():
    api_key = getattr(settings, "GROQ_API_KEY", "")
    if not api_key:
        raise AskAINotConfigured(
            "GROQ_API_KEY is empty in this process. If you have just added it to "
            ".env, restart the server - python-dotenv is read once at startup."
        )
    return groq_client.GroqClient(
        api_key=api_key,
        base_url=getattr(settings, "GROQ_BASE_URL", groq_client.DEFAULT_BASE_URL),
        timeout=getattr(settings, "GROQ_TIMEOUT", 30.0),
        vision_model=getattr(settings, "GROQ_VISION_MODEL", groq_client.DEFAULT_VISION_MODEL),
        text_model=getattr(settings, "GROQ_TEXT_MODEL", groq_client.DEFAULT_TEXT_MODEL),
    )


def ask(conversation, question_text, client=None):
    """
    Ask one question about a diagnosed photo.

    Returns (answer_markdown, answer_html, metadata). Raises AskAIUnavailable
    when no model is configured or the call fails, so the view can answer 503
    and the farmer sees an honest error rather than a fabricated answer.
    """
    subject = conversation.subject
    if subject is None:
        raise AskAIUnavailable("Conversation has no subject to answer about")

    if conversation.kind == conversation.SUBJECT_INSECT:
        # An uncertain insect ID is as dangerous as an uncertain disease one:
        # spraying a misidentified beneficial kills the predators holding the
        # real pest down. Same gate, different vocabulary.
        gated = not abstention.may_show_treatment(subject.identification_status)
        system_prompt = build_insect_system_prompt(subject, not gated)
    else:
        gated = not abstention.may_show_treatment(subject.diagnosis_status)
        system_prompt = build_system_prompt(subject, not gated)

    if client is None:
        client = _build_client()

    user_prompt = build_user_prompt(conversation, question_text)
    image_bytes, mime_type = _load_image_bytes(subject)

    started = time.time()
    try:
        answer, model_used, had_image = client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            image_bytes=image_bytes,
            mime_type=mime_type or "image/jpeg",
        )
    except groq_client.GroqError as exc:
        logger.error("Ask AI call failed: %s", exc)
        raise AskAIUnavailable(str(exc)) from exc

    latency_ms = int((time.time() - started) * 1000)

    if not answer or not answer.strip():
        raise AskAIUnavailable("Model returned an empty answer")

    return answer, answer_format.render_markdown(answer), {
        "model_name": model_used,
        "latency_ms": latency_ms,
        "treatment_gated": gated,
        "had_image": had_image,
    }
