import json

import pytest

import run_study
from data_io import build_panel, synthetic


@pytest.fixture
def env(tmp_path, monkeypatch):
    man = tmp_path / "evaluations.json"
    man.write_text(json.dumps({"evaluations": [{"period": "val", "variant": "primary", "spec_hash": "x", "date": "2026-11-04"}]}))
    monkeypatch.setattr(run_study, "MANIFEST", man)
    monkeypatch.setattr(run_study, "ROOT", tmp_path)
    s, e = synthetic(seed=2, n=4200, start="2006-01-02")
    monkeypatch.setattr(run_study, "load_panel", lambda: build_panel(s, e))
    monkeypatch.chdir(tmp_path)
    return man


def test_recorded_evaluation_cannot_be_rerun_as_fresh(env):
    with pytest.raises(SystemExit, match="already evaluated"):
        run_study.main(["--period", "val"])


def test_holdout_needs_the_spec_hash_and_primary_only(env):
    with pytest.raises(SystemExit, match="--confirm"):
        run_study.main(["--period", "holdout"])
    with pytest.raises(SystemExit, match="primary"):
        run_study.main(["--period", "holdout", "--variant", "hold1"])


def test_first_run_is_recorded_and_reproduction_is_labelled(env):
    run_study.main(["--period", "val", "--variant", "hold1"])
    assert any(e["variant"] == "hold1" for e in json.loads(env.read_text())["evaluations"])
    run_study.main(["--period", "val", "--variant", "hold1", "--reproduce", "--out", "rr"])
    assert "REPRODUCTION" in (env.parent / "rr" / "val_hold1" / "summary.txt").read_text()
