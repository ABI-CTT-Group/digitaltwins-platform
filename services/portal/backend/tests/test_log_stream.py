import app.builder.log_stream as ls
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


def test_ring_buffer_eviction_and_stale_offset(monkeypatch):
    """Ring-buffer drop + stale-offset recovery coverage.

    Monkeypatch _MAX_LINES_PER_JOB to 3 so we don't need thousands of lines.
    Because _Job.__init__ reads the module-level name at call time (not at
    class-definition time), a fresh LogStreamRegistry() constructed AFTER the
    patch picks up the small maxlen automatically.
    """
    monkeypatch.setattr(ls, "_MAX_LINES_PER_JOB", 3)
    r = ls.LogStreamRegistry()          # _Job deques will use maxlen=3
    r.open("evict:1")

    # Append 5 lines — the ring buffer cap is 3, so lines 0-1 are evicted.
    for i in range(5):
        r.append("evict:1", f"line {i}")

    # After appending 5 lines with a cap of 3:
    #   dropped = 2  (lines "line 0" and "line 1" were evicted)
    #   lines = deque(["line 2", "line 3", "line 4"], maxlen=3)
    #   total = dropped + len(lines) = 2 + 3 = 5

    # --- stale-offset test (offset=0 is older than the oldest surviving line) ---
    new, next_off, done, status = r.snapshot("evict:1", 0)

    # Should return the 3 surviving lines (oldest surviving first)
    assert new == ["line 2", "line 3", "line 4"], (
        f"Expected surviving lines, got {new!r}"
    )
    # next_offset must equal total (dropped + len)
    assert next_off == 5, f"Expected next_offset=5, got {next_off}"
    # dropped > 0 verifies the eviction branch was exercised
    job = r._jobs["evict:1"]
    assert job.dropped == 2, f"Expected dropped=2, got {job.dropped}"
    # offset < dropped verifies the stale-offset clamp path
    assert 0 < job.dropped, "stale-offset clamp not exercised (offset was not < dropped)"
    assert not done    # not finished yet

    # --- caught-up offset test ---
    new2, next_off2, _, _ = r.snapshot("evict:1", next_off)
    assert new2 == [], f"Expected [] for caught-up offset, got {new2!r}"
    assert next_off2 == next_off, (
        f"Expected next_offset unchanged at {next_off}, got {next_off2}"
    )
