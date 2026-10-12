from sandbench.bench import percentile
from sandbench.runner import IsolationSpec, build_run_args, classify


def test_percentile_empty() -> None:
    assert percentile([], 50) == 0.0


def test_percentile_p50() -> None:
    assert percentile([1, 2, 3, 4, 5], 50) == 3


def test_classify() -> None:
    assert classify(0, False) == "ok"
    assert classify(1, False) == "error"
    assert classify(137, False) == "oom"
    assert classify(137, True) == "timeout"
    assert classify(139, False) == "error"
    assert classify(None, True) == "timeout"


def test_run_args_lock_down_defaults() -> None:
    args = build_run_args("sandbench-test", IsolationSpec(), ["echo", "ok"])
    assert args[:2] == ["run", "-d"]
    assert "--rm" not in args
    assert "--network" in args and args[args.index("--network") + 1] == "none"
    assert "--cap-drop" in args and "ALL" in args
    assert "--memory" in args and args[args.index("--memory") + 1] == "64m"
    assert "--memory-swap" in args and args[args.index("--memory-swap") + 1] == "64m"
    assert args[-2:] == ["echo", "ok"]
