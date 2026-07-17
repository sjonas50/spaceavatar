"""The COPPA logging invariant: conversation content must never reach a log line.

log_pipeline_metrics uses a numeric-allowlist by construction; these tests
prove a hostile event object (carrying transcript-like fields) leaks nothing.
"""

from types import SimpleNamespace

import structlog

from commander_sky.metrics import log_pipeline_metrics

SECRET_UTTERANCE = "my name is emma and i live on oak street"


def _capture_logs() -> tuple[list[dict], object]:
    captured: list[dict] = []

    def sink(logger: object, method: str, event_dict: dict) -> dict:
        captured.append(dict(event_dict))
        return event_dict

    structlog.configure(processors=[sink, structlog.processors.JSONRenderer()])
    return captured, sink


def test_transcript_fields_never_logged() -> None:
    captured, _ = _capture_logs()
    hostile_event = SimpleNamespace(
        metrics=SimpleNamespace(
            ttft=0.21,
            duration=1.3,
            transcript=SECRET_UTTERANCE,
            text=SECRET_UTTERANCE,
            content=SECRET_UTTERANCE,
            request_id="req-123",
        )
    )
    log_pipeline_metrics(hostile_event)

    assert captured, "expected a metrics log line"
    flattened = str(captured)
    assert SECRET_UTTERANCE not in flattened
    assert "emma" not in flattened
    assert captured[0]["ttft"] == 0.21


def test_string_numeric_lookalikes_are_dropped() -> None:
    captured, _ = _capture_logs()
    event = SimpleNamespace(metrics=SimpleNamespace(ttft="not a number", duration=2.0))
    log_pipeline_metrics(event)
    assert "ttft" not in captured[0]
    assert captured[0]["duration"] == 2.0
