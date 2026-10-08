"""
Shared abstention policy
========================
One place decides whether a diagnosis is safe to act on. Every provider routes
through this, so the bundled model and the crop.health API cannot drift into
disagreeing about what "confident" means.

WHY THIS EXISTS
---------------
On real farmer photos the honest top-1 accuracy of the best available options
sits between 48% and 85%. A single confident-looking answer is therefore wrong
often enough that printing a pesticide recommendation beside it causes real
harm: the farmer buys and sprays the wrong chemical, loses the money, and
still loses the crop.

Two mitigations, both encoded here:

  1. Always return three candidates. For crop.health, top-3 lifts the odds the
     correct answer is on screen from 48% to 66% on in-the-wild images. That is
     the single largest accuracy gain available to this app and it costs
     nothing.
  2. Only unlock treatment advice on a "reliable" verdict. Below that the user
     gets symptoms and candidates, and is pointed at a human.

Thresholds are deliberately conservative and env-tunable; raise them, never
lower them, without a measured validation split to justify it.
"""

import math
from dataclasses import dataclass

# Verdicts. Ordered worst to best.
UNRELIABLE = "unreliable"
CAUTION = "caution"
RELIABLE = "reliable"

# Returned when the image is not a plant at all.
NOT_A_PLANT = "not_a_plant"


@dataclass(frozen=True)
class Thresholds:
    """
    Confidence gates, all on a 0-100 scale except the entropy ceiling.

    reliable_min  - top-1 confidence at or above this may show treatment advice
    caution_min   - below this the result is 'unreliable' and shows candidates only
    min_margin    - required gap between the top two candidates, 0-1
    max_entropy   - normalised Shannon entropy ceiling, 0 = certain, 1 = uniform
    """
    reliable_min: float
    caution_min: float
    min_margin: float = 0.15
    max_entropy: float = 0.75


# crop.health probabilities are calibrated against real field imagery and are
# nowhere near as peaked as a PlantVillage softmax, so the gates sit lower than
# the local model's. 65 / 40 keeps roughly the top third of calls actionable.
CROP_HEALTH_THRESHOLDS = Thresholds(reliable_min=65.0, caution_min=40.0)


def normalised_entropy(probabilities):
    """
    Shannon entropy of a probability vector, scaled to 0-1.

    Accepts an unnormalised vector - API suggestion lists do not sum to 1,
    because low-ranked candidates are truncated - and renormalises first.
    Returns None when there is nothing to measure.
    """
    values = [float(p) for p in probabilities if p is not None and float(p) > 0.0]
    if len(values) < 2:
        return None

    total = sum(values)
    if total <= 0.0:
        return None

    values = [v / total for v in values]
    entropy = -sum(v * math.log(v) for v in values)
    ceiling = math.log(len(values))
    if ceiling <= 0.0:
        return None
    return entropy / ceiling


def classify(confidence, thresholds, margin=None, entropy=None):
    """
    Turn a confidence into a verdict.

    confidence - top-1 confidence, 0-100
    margin     - top1 minus top2 probability, 0-1, optional
    entropy    - normalised entropy from normalised_entropy(), optional

    A high top-1 that is crowded by its runner-up, or that sits on a flat
    distribution, is downgraded rather than trusted: both patterns mean the
    model is picking between lookalikes, which is exactly when a wrong
    treatment gets recommended.
    """
    if confidence < thresholds.caution_min:
        return UNRELIABLE

    if confidence < thresholds.reliable_min:
        return CAUTION

    ambiguous = (
        (margin is not None and margin < thresholds.min_margin)
        or (entropy is not None and entropy > thresholds.max_entropy)
    )
    return CAUTION if ambiguous else RELIABLE


def may_show_treatment(status):
    """
    Treatment advice - named chemicals, doses, 'apply X' - is gated to a
    reliable verdict. Everything else gets symptoms, candidates and a referral.
    """
    return status == RELIABLE


def referral_message(status, crop_name=None):
    """Plain wording for what the farmer should do about an uncertain result."""
    if status == NOT_A_PLANT:
        return (
            "This photo does not look like a plant. Take a clear photo of a "
            "single affected leaf, filling most of the frame, in daylight."
        )
    if status == RELIABLE:
        return "Confident result. Follow the treatment steps below."
    if status == CAUTION:
        subject = f"this {crop_name}" if crop_name else "this plant"
        return (
            f"Not fully certain about {subject}. The three possibilities below "
            "are ranked. Confirm with your local KVK or agriculture officer "
            "before buying any chemical."
        )
    return (
        "Not confident enough to name the disease. Possible matches are listed "
        "below for reference only. Show the plant to your local KVK or "
        "agriculture officer, or upload a sharper close-up of the affected leaf."
    )
