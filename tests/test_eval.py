"""Evaluation tests. Owner: Smaran (BR)."""
from pitwall.eval.batch import evaluate
from pitwall.eval.metrics import paired, stats


def test_small_evaluation_and_stats():
    df = evaluate("monza", "f1", n=2, workers=1, n_futures=30, save=False)
    assert len(df) == 8
    s = stats(paired(df))
    assert s["n_races"] == 2 and "pirelli" in s["gain_vs"]
