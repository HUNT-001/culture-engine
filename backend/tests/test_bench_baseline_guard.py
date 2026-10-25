"""The stale-base guard, and the facts that v1 got wrong.

Provenance: production-function (the guard inspects the live ``app`` object).
"""
from __future__ import annotations

import pytest

from bench import baseline_guard as BG
from bench.testing import no_network  # noqa: F401

pytestmark = pytest.mark.usefixtures("no_network")


def test_head_descends_from_the_required_checkpoint():
    a = BG.ancestry()
    if not a["checked"]:
        pytest.skip("not a git checkout")
    assert a["checkpoint_object_present"], "checkpoint commit missing from this clone"
    assert a["head_descends_from_checkpoint"], "benchmark is running on a stale base"


def test_all_required_routes_are_registered_on_the_live_app():
    feats = BG.production_features()
    missing = [p for p, ok in feats["routes_registered"].items() if not ok]
    assert not missing, missing


def test_all_required_production_features_exist():
    bad = [k for k, ok in BG.production_features()["symbols"].items() if not ok]
    assert not bad, bad


def test_verify_reports_ok():
    result = BG.verify(require_git=False)
    assert result["ok"], result["problems"]


def test_guard_flags_a_stale_base(monkeypatch):
    monkeypatch.setattr(BG, "ancestry", lambda: {
        "checked": True, "required_checkpoint": BG.REQUIRED_CHECKPOINT,
        "checkpoint_object_present": False, "head_descends_from_checkpoint": False})
    result = BG.verify()
    assert not result["ok"]
    assert any("checkpoint" in p for p in result["problems"])


def test_guard_flags_a_head_that_does_not_descend(monkeypatch):
    monkeypatch.setattr(BG, "ancestry", lambda: {
        "checked": True, "required_checkpoint": BG.REQUIRED_CHECKPOINT,
        "checkpoint_object_present": True, "head_descends_from_checkpoint": False})
    assert any("does not descend" in p for p in BG.verify()["problems"])


def test_guard_refuses_to_pass_silently_without_git():
    # When ancestry cannot be checked the strict default must fail, not pass.
    import bench.baseline_guard as g
    original = g.ancestry
    g.ancestry = lambda: {"checked": False, "reason": "not a git checkout"}
    try:
        assert not g.verify()["ok"]
        assert g.verify(require_git=False)["ok"]
    finally:
        g.ancestry = original
