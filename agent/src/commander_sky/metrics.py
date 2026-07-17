"""Latency observability for the voice pipeline.

COPPA constraint: everything emitted here is numbers and enum-like labels.
No transcripts, no utterances, no child-identifying data — ever.
"""

from typing import Any

from commander_sky.logging import get_logger

log = get_logger("pipeline.metrics")

# Attributes we allow into log lines. Anything else on a metrics event
# (e.g. transcript text) is dropped by construction.
_NUMERIC_FIELDS = (
    "ttft",
    "ttfb",
    "duration",
    "audio_duration",
    "end_of_utterance_delay",
    "transcription_delay",
    "tokens_per_second",
    "input_tokens",
    "output_tokens",
    "characters_count",
)


def log_pipeline_metrics(event: Any) -> None:
    """Log the numeric fields of a livekit-agents metrics event, content-free.

    Args:
        event: A ``MetricsCollectedEvent`` (or any object with a ``metrics`` attr).
    """
    metrics = getattr(event, "metrics", event)
    fields: dict[str, float] = {}
    for name in _NUMERIC_FIELDS:
        value = getattr(metrics, name, None)
        if isinstance(value, int | float):
            fields[name] = round(float(value), 4)
    log.info("pipeline_metrics", stage=type(metrics).__name__, **fields)
