from __future__ import annotations

from tikitaka.ingest.websocket import build_subscription


def test_subscription_has_correct_keys() -> None:
    """Regression test for pselamy issue #89 — `assets_ids` (plural) + `type: 'market'`.

    Verifies the subscription payload uses the exact keys the Polymarket CLOB
    server expects. A wrong key silently yields no data.
    """
    payload = build_subscription(["tok-a", "tok-b"])
    assert set(payload.keys()) == {"assets_ids", "type"}
    assert payload["type"] == "market"
    assert payload["assets_ids"] == ["tok-a", "tok-b"]


def test_subscription_preserves_order_and_accepts_iterable() -> None:
    ids = (x for x in ["x", "y", "z"])
    payload = build_subscription(ids)
    assert payload["assets_ids"] == ["x", "y", "z"]
