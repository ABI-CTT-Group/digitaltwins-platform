"""
Static checks on portal-frontend's nginx template.

nginx resolves a literal `proxy_pass http://builder:8000` once, at
startup. When the builder is recreated with a new IP, portal-frontend keeps
proxying /api/ to the stale address — which Docker may have handed to another
container (it went to the platform API, so every /api/ call 404'd). Every
upstream must therefore go through a `set` variable plus a `resolver`, so the
name is looked up per request (same convention as the platform gateway).

Run from `services/builder/`:
    python -m pytest tests/test_frontend_nginx_template.py
"""
import re
import unittest
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[3] / "services" / "portal" / "frontend" / "nginx.conf.template"


def _directives(name):
    text = re.sub(r"#.*", "", TEMPLATE.read_text())
    return re.findall(rf"^\s*{name}\s+([^;]+);", text, re.MULTILINE)


@unittest.skipUnless(TEMPLATE.exists(), "frontend source not present")
class FrontendNginxTemplateTest(unittest.TestCase):
    def test_resolver_uses_docker_dns(self):
        self.assertTrue(
            any(r.startswith("127.0.0.11") for r in _directives("resolver")),
            "template needs `resolver 127.0.0.11 ...` for per-request lookups",
        )

    def test_only_api_builder_reaches_the_builder(self):
        # /api/ belongs to the platform API (the gateway routes it); the builder serves /api/builder/.
        text = re.sub(r"#.*", "", TEMPLATE.read_text())
        backend = [spec.strip() for spec, body in re.findall(r"location\s+([^{]+)\{([^}]*)\}", text)
                   if "$up_builder" in body]
        self.assertEqual(backend, [
            r"~ ^/api/builder/(tools|workflow)/upload-source$",
            r"~ ^/api/builder/tools/(builds|deploy)/[^/]+/logs/stream$",
            "/api/builder/",
        ])

    def test_the_builder_upstream_is_the_builder_service(self):
        self.assertEqual(set(_directives(r"set\s+\$up_builder")), {"builder"})
        builder = [t for t in _directives("proxy_pass") if "$up_builder" in t]
        self.assertTrue(builder)
        self.assertEqual(set(builder), {"http://$up_builder:${BUILDER_PORT}"})

    def test_every_proxy_pass_goes_through_a_variable(self):
        targets = _directives("proxy_pass")
        self.assertTrue(targets)
        literal = [t for t in targets if not re.match(r"^http://\$\w+", t)]
        self.assertEqual(literal, [], "proxy_pass with a literal host is resolved only at startup")


if __name__ == "__main__":
    unittest.main()
