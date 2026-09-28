from sandbench.bench import percentile
from sandbench.runner import classify


def test_percentile_empty() -> None:
    assert percentile([], 50) == 0.0


def test_percentile_p50() -> None:
    assert percentile([1, 2, 3, 4, 5], 50) == 3


def test_classify() -> None:
    assert classify(0, False) == "ok"
    assert classify(1, False) == "error"
    assert classify(137, False) == "oom"
    assert classify(None, True) == "timeout"
