"""Fixed responses for situations where the freeform LLM must never improvise.

These strings ARE the safety behavior for sensitive/distress inputs — treat
edits as launch-blocking changes requiring review (BUILD_PLAN.md §Phase 2).
Audience: general public (owner decision 2026-07-17).
"""

DISTRESS_DEFAULT = "distress_default"
SENSITIVE_DEFAULT = "sensitive_default"
OUTPUT_FALLBACK = "output_fallback"
SIGN_OFF = "sign_off"

_RESPONSES: dict[str, str] = {
    # The user may be in real distress. Brief, human, no improvised counseling.
    DISTRESS_DEFAULT: (
        "That sounds genuinely heavy, and I'm glad you said it out loud. Please talk to "
        "someone you trust about it — a friend, family, or a professional who can actually "
        "be there for you. I'll be right here whenever you want to look at the stars again."
    ),
    # Explicit content, harassment, PII, rule-breaking attempts. Light close, pivot.
    SENSITIVE_DEFAULT: (
        "Ha — that one's outside my flight plan. Up here I stick to space. Want to hear "
        "what riding a Saturn V off the pad actually felt like?"
    ),
    # The output guard rejected a generated response. Safe generic wonder.
    OUTPUT_FALLBACK: (
        "Whoops — my radio crackled there for a second. Here's one for you though: on the "
        "Moon you could jump six times higher than on Earth. What else can I tell you "
        "about space?"
    ),
    # Session time limit reached.
    SIGN_OFF: (
        "That's all the time mission control gives me today. Thanks for flying with me — "
        "keep looking up, and come find me again soon."
    ),
}


def get_canned(response_id: str) -> str:
    """Return the canned response for ``response_id``.

    Falls back to the output-guard fallback line for unknown IDs — a wrong ID
    must degrade to something safe, never to an audible error.
    """
    return _RESPONSES.get(response_id, _RESPONSES[OUTPUT_FALLBACK])
