"""JupyterHub as the ``api`` service: start a user's server and write into its workspace.

The service token holds the hub's admin role (services/jupyterhub/jupyterhub_config.py), so it
can create users, spawn their default server and use that server's contents API.
"""
import base64
import os
import time
from typing import Iterable, Iterator, Optional, Set
from urllib.parse import quote

import requests

DEFAULT_URL = "http://digitaltwins-platform-jupyterhub:8000/jupyter"
PART_SIZE = 8 * 1024 * 1024
# Appended while a file is being written, so a path that exists is always complete. Not a
# dot-prefix: jupyter_server refuses hidden paths unless allow_hidden is set.
STAGING_SUFFIX = ".staging"


class HubError(RuntimeError):
    """JupyterHub or the user's server refused a call."""


class HubTimeout(HubError):
    """The user's server did not become ready in time."""


class JupyterHub:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None,
                 session=None, start_timeout: float = 120.0, poll_interval: float = 1.0):
        self.base_url = (base_url or os.getenv("JUPYTERHUB_INTERNAL_URL", DEFAULT_URL)).rstrip("/")
        # No default: the hub would accept it, and a default would be public.
        self.headers = {"Authorization": f"token {token or os.environ['JUPYTERHUB_API_TOKEN']}"}
        self.session = session or requests.Session()
        # Matches DockerSpawner.start_timeout.
        self.start_timeout = start_timeout
        self.poll_interval = poll_interval
        self.part_size = PART_SIZE

    def _call(self, method: str, url: str, ok=(200, 201, 202, 204), **kwargs):
        res = self.session.request(method, url, headers=self.headers, timeout=60, **kwargs)
        if res.status_code not in ok:
            raise HubError(f"{method} {url} returned {res.status_code}: {res.text}")
        return res

    def _user_url(self, username: str) -> str:
        return f"{self.base_url}/hub/api/users/{quote(username)}"

    def _contents_url(self, username: str, path: str) -> str:
        return f"{self.base_url}/user/{quote(username)}/api/contents/{quote(path)}"

    def ensure_server(self, username: str) -> None:
        """Create the hub user if needed and start their default server; return once it is ready."""
        res = self._call("GET", self._user_url(username), ok=(200, 404))
        if res.status_code == 404:
            self._call("POST", self._user_url(username), ok=(201,))
            server = None
        else:
            server = (res.json().get("servers") or {}).get("")
        if server is None:
            self._call("POST", f"{self._user_url(username)}/server", ok=(201, 202))
        deadline = time.monotonic() + self.start_timeout
        while not (server or {}).get("ready"):
            if time.monotonic() > deadline:
                raise HubTimeout(f"Jupyter server for {username} did not start within {self.start_timeout:.0f}s")
            time.sleep(self.poll_interval)
            server = (self._call("GET", self._user_url(username)).json().get("servers") or {}).get("")
            if server is None:
                raise HubError(f"Jupyter server for {username} failed to start")

    def list_paths(self, username: str, root: str) -> Set[str]:
        """Every file and folder under ``root``, ``root`` included; empty when ``root`` is missing."""
        res = self._call("GET", self._contents_url(username, root), ok=(200, 404), params={"content": 1})
        if res.status_code == 404:
            return set()
        paths = {root}
        for item in res.json().get("content") or []:
            if item["type"] == "directory":
                paths |= self.list_paths(username, item["path"])
            else:
                paths.add(item["path"])
        return paths

    def mkdir(self, username: str, path: str) -> None:
        """Create one folder; its parent must exist."""
        self._call("PUT", self._contents_url(username, path), json={"type": "directory"})

    def put_file(self, username: str, path: str, chunks: Iterable[bytes]) -> None:
        """Write ``chunks`` to ``path`` under a staging name, then rename it into place.

        Files larger than one part use the contents API's chunked save (parts 1..n, the last -1).
        """
        url = self._contents_url(username, path + STAGING_SUFFIX)
        previous, sent = None, 0
        for part in _parts(chunks, self.part_size):
            if previous is not None:
                sent += 1
                self._save(url, previous, sent)
            previous = part
        self._save(url, previous or b"", -1 if sent else None)
        self._call("PATCH", url, json={"path": path})

    def _save(self, url: str, data: bytes, chunk: Optional[int]) -> None:
        body = {"type": "file", "format": "base64", "content": base64.b64encode(data).decode()}
        if chunk is not None:
            body["chunk"] = chunk
        self._call("PUT", url, json=body)


def _parts(chunks: Iterable[bytes], size: int) -> Iterator[bytes]:
    """Re-cut a byte stream into parts of ``size`` bytes (the last may be shorter)."""
    buf = bytearray()
    for chunk in chunks:
        buf += chunk
        while len(buf) >= size:
            yield bytes(buf[:size])
            del buf[:size]
    if buf:
        yield bytes(buf)
