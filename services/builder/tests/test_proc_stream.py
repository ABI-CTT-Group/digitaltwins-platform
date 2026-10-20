"""
Captured process output is persisted as build logs, and Postgres text columns
cannot hold NUL, so NUL bytes (e.g. Rollup's "\\0commonjsHelpers.js" virtual ids
in vite output) must be dropped from every emitted line.

Run from `services/builder/`:
    python -m pytest tests/test_proc_stream.py
"""
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.engine.proc_stream import stream_process  # noqa: E402


class StreamProcessNulTest(unittest.TestCase):
    def test_nul_bytes_are_dropped_from_lines(self):
        lines = []
        rc = stream_process([sys.executable, "-c", "import sys; sys.stdout.write('a\\x00b\\n')"], on_line=lines.append)
        self.assertEqual(rc, 0)
        self.assertEqual(lines, ["ab"])


if __name__ == "__main__":
    unittest.main()
