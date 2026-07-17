"""Fixed responses for situations where the freeform LLM must never improvise.

These strings ARE the safety behavior for sensitive/distress inputs — treat
edits as launch-blocking changes requiring review (BUILD_PLAN.md §Phase 2).
"""

DISTRESS_DEFAULT = "distress_default"
SENSITIVE_DEFAULT = "sensitive_default"
OUTPUT_FALLBACK = "output_fallback"
SIGN_OFF = "sign_off"

_RESPONSES: dict[str, str] = {
    # A child mentioned being hurt, scared, or unsafe. Compassion, then a
    # trusted grown-up. No questions, no improvisation, no pretending to help.
    DISTRESS_DEFAULT: (
        "I'm really glad you told me that. That sounds like something a grown-up you "
        "trust should hear about — like a parent or a teacher. They care about you and "
        "can help much better than I can from way up here. I'll be right here when you "
        "want to talk about space again."
    ),
    # Personal info, violence, or other sensitive territory. Gentle close, warm pivot.
    SENSITIVE_DEFAULT: (
        "You know, that's a question for a grown-up you trust, not an astronaut like me! "
        "But I know a lot about space. Want to hear what it feels like to float in zero "
        "gravity?"
    ),
    # The output guard rejected a generated response. Safe generic wonder.
    OUTPUT_FALLBACK: (
        "Whoops, my radio crackled there for a second! Here's something amazing though: "
        "on the Moon you could jump six times higher than on Earth. What else would you "
        "like to know about space?"
    ),
    # Session time limit reached.
    SIGN_OFF: (
        "Time for me to go check on the rocket! Thanks for exploring space with me today. "
        "Keep looking up, space explorer — see you next time!"
    ),
}


def get_canned(response_id: str) -> str:
    """Return the canned response for ``response_id``.

    Falls back to the output-guard fallback line for unknown IDs — a wrong ID
    must degrade to something safe, never to an error a child can hear.
    """
    return _RESPONSES.get(response_id, _RESPONSES[OUTPUT_FALLBACK])
