from app.builder.log_stream import LogStreamRegistry


def test_append_and_snapshot_incremental():
    r = LogStreamRegistry()
    r.open("build:1")
    r.append("build:1", "line a")
    r.append("build:1", "line b")
    new, off, done, status = r.snapshot("build:1", 0)
    assert new == ["line a", "line b"] and off == 2 and not done
    r.append("build:1", "line c")
    new, off, done, _ = r.snapshot("build:1", off)
    assert new == ["line c"] and off == 3


def test_finish_sets_done_status():
    r = LogStreamRegistry()
    r.open("deploy:1")
    r.finish("deploy:1", "completed")
    _, _, done, status = r.snapshot("deploy:1", 0)
    assert done and status == "completed"


def test_secrets_are_masked():
    r = LogStreamRegistry()
    r.open("build:2")
    r.append("build:2", "token ghp_ABCDEFGHIJKLMNOPQRSTUVWX done")
    new, *_ = r.snapshot("build:2", 0)
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWX" not in new[0]


def test_unknown_job_returns_gone():
    r = LogStreamRegistry()
    new, off, done, status = r.snapshot("build:none", 0)
    assert new == [] and done and status == "gone"
