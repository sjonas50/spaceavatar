"""Canned response registry tests — including that canned text passes its own guard."""

import pytest

from commander_sky import canned
from commander_sky.safety import OutputGuard

ALL_IDS = [
    canned.DISTRESS_DEFAULT,
    canned.SENSITIVE_DEFAULT,
    canned.OUTPUT_FALLBACK,
    canned.SIGN_OFF,
]


@pytest.mark.parametrize("response_id", ALL_IDS)
def test_all_ids_resolve(response_id: str) -> None:
    assert len(canned.get_canned(response_id)) > 20


def test_unknown_id_degrades_safely() -> None:
    assert canned.get_canned("nope") == canned.get_canned(canned.OUTPUT_FALLBACK)


def test_distress_points_to_trusted_person() -> None:
    assert "someone you trust" in canned.get_canned(canned.DISTRESS_DEFAULT)


@pytest.mark.parametrize("response_id", ALL_IDS)
def test_canned_responses_pass_output_guard(response_id: str) -> None:
    """The fixed responses must satisfy the same rules as generated ones."""
    assert OutputGuard().violations(canned.get_canned(response_id)) == []
