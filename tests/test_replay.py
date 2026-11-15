"""Prompt sidecar arguments (dev experiments) and the replay of saved model answers."""
import sys
from pathlib import Path

import pipeline.main as pm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dev"))


def test_sidecar_args_only_when_a_file_exists(tmp_path, monkeypatch):
    (tmp_path / "pipeline" / "prompt").mkdir(parents=True)
    (tmp_path / "pipeline" / "prompt" / "exp.txt.args").write_text("--taxon-groups\n--docs A,B\n")
    monkeypatch.setattr(pm, "ROOT", tmp_path)
    assert pm.sidecar_args("exp.txt") == ["--taxon-groups", "--docs", "A,B"]
    assert pm.sidecar_args("exp") == ["--taxon-groups", "--docs", "A,B"]
    assert pm.sidecar_args("system.txt") == []
    assert pm.sidecar_args("../x") == []


def test_the_shipped_prompt_has_no_sidecar():
    assert pm.sidecar_args("system.txt") == []


def test_replay_client_hands_back_answers_in_order_then_empty():
    from replay import ReplayClient
    c = ReplayClient(["a", "b"])
    assert [c.complete("s", "u").text for _ in range(3)] == ["a", "b", ""]
    assert c.short and c.calls == 3
