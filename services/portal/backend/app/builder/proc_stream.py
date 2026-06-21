"""Stream a child process's combined output line-by-line, in real time.

The portal builds plugins with `npm`/`vite` and deploys them with
`docker compose`. When those tools detect their stdout is a plain pipe (not a
TTY) they switch to block buffering and suppress progress output, so the live
log console saw long silent gaps followed by a burst. Running the child under a
pseudo-terminal (PTY) makes it behave as if attached to a real terminal:
line-buffered, progress shown. We collapse carriage-return progress frames to
the final state of each line so an in-place-updated progress bar doesn't flood
the append-only console.

POSIX (the Linux backend container) uses the PTY path; Windows dev — or any PTY
failure — falls back to a normal pipe.
"""
import os
import shlex
import subprocess
from typing import Callable, Optional, Sequence, Union

OnLine = Optional[Callable[[str], None]]


def _emit(on_line: OnLine, raw: str) -> None:
    """Deliver one logical line. `raw` has no trailing newline but may carry a
    trailing CR (from \\r\\n translation) and/or in-place progress frames
    separated by CR — collapse to the final frame."""
    line = raw.rstrip("\r")
    if "\r" in line:
        line = line.split("\r")[-1]
    if on_line:
        try:
            on_line(line)
        except Exception:
            # Never let a logging/sink callback abort the read loop.
            pass


def stream_process(
    args: Union[str, Sequence[str]],
    cwd=None,
    env=None,
    on_line: OnLine = None,
) -> int:
    """Run a child process, delivering each output line to `on_line` as soon as
    it is flushed, and return the process exit code.

    Raises FileNotFoundError if the executable is missing (same contract as
    subprocess), so callers can report a clear error.
    """
    if isinstance(args, str):
        args = shlex.split(args)
    else:
        args = list(args)

    if os.name == "posix":
        try:
            return _stream_pty(args, cwd, env, on_line)
        except FileNotFoundError:
            raise
        except Exception:
            # Any PTY-specific failure → fall back to the portable pipe path.
            pass
    return _stream_pipe(args, cwd, env, on_line)


def _stream_pipe(args, cwd, env, on_line) -> int:
    with subprocess.Popen(
        args, cwd=cwd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    ) as proc:
        # iter(readline, "") avoids Python's iterator read-ahead so each line
        # surfaces as soon as the child flushes it.
        for line in iter(proc.stdout.readline, ""):
            _emit(on_line, line.rstrip("\n"))
        return proc.wait()


def _stream_pty(args, cwd, env, on_line) -> int:
    import pty
    import select

    master_fd, slave_fd = pty.openpty()

    # Give the PTY a sane size so tools don't wrap at 0 columns.
    try:
        import fcntl
        import struct
        import termios
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 200, 0, 0))
    except Exception:
        pass

    try:
        proc = subprocess.Popen(
            args, cwd=cwd, env=env,
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            close_fds=True,
        )
    except Exception:
        os.close(master_fd)
        os.close(slave_fd)
        raise

    os.close(slave_fd)  # parent only reads the master end
    buf = b""
    try:
        while True:
            try:
                rlist, _, _ = select.select([master_fd], [], [], 0.2)
            except (OSError, ValueError):
                break
            if rlist:
                try:
                    data = os.read(master_fd, 8192)
                except OSError:
                    break  # EIO is raised on the master when the child exits
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    head, buf = buf.split(b"\n", 1)
                    _emit(on_line, head.decode("utf-8", "replace"))
            elif proc.poll() is not None:
                break  # child gone and nothing left to read
        if buf:
            _emit(on_line, buf.decode("utf-8", "replace"))
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass
    return proc.wait()
