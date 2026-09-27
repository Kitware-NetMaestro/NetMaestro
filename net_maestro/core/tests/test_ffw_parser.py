"""Tests for decoding FFW model-stats payloads."""

from __future__ import annotations

from net_maestro.core.parsers.ffw_file import FFW_TERMINAL_MODEL, _decode_ffw_terminal_model


def test_negative_counter_deltas_decode_as_negative() -> None:
    """After an optimistic rollback a counter delta is negative; it must not wrap to 2**64 - 1."""
    payload = FFW_TERMINAL_MODEL.pack(7, 0, 0, 0, 0, *([0.0] * 6), 0, 0, 0, -1)

    row = _decode_ffw_terminal_model(payload)

    assert row["terminal_id"] == 7
    assert row["rate_updates_received"] == -1
