import os
import sys
import unittest
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as app_module  # noqa: E402
from career_integrator.service import run_integration  # noqa: E402


def wsgi_call(method, path, body=b"", extra_env=None):
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": BytesIO(body),
    }
    if extra_env:
        environ.update(extra_env)
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    chunks = app_module.app(environ, start_response)
    return captured["status"], captured["headers"], b"".join(chunks)


class StaticRoutingTest(unittest.TestCase):
    def test_index(self):
        status, headers, body = wsgi_call("GET", "/")
        self.assertTrue(status.startswith("200"))
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"<title>", body)

    def test_sample_txt(self):
        status, headers, body = wsgi_call("GET", "/samples/tenmei_report.txt")
        self.assertTrue(status.startswith("200"))
        self.assertIn("text/plain", headers["Content-Type"])
        self.assertIn("天命レポート".encode("utf-8"), body)

    def test_unknown_path_404(self):
        status, _, _ = wsgi_call("GET", "/does-not-exist")
        self.assertTrue(status.startswith("404"))

    def test_path_traversal_blocked(self):
        status, _, _ = wsgi_call("GET", "/../pyproject.toml")
        self.assertTrue(status.startswith("404"))


class ApiRoutingTest(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY")}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_options_preflight(self):
        status, headers, _ = wsgi_call("OPTIONS", "/api/integrate")
        self.assertTrue(status.startswith("204"))
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")

    def test_get_not_allowed(self):
        os.environ["GEMINI_API_KEY"] = "dummy"
        status, _, _ = wsgi_call("GET", "/api/integrate")
        self.assertTrue(status.startswith("405"))

    def test_missing_api_key(self):
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GOOGLE_API_KEY", None)
        body = b'{"interest":"x","tenmei":"y"}'
        status, _, out = wsgi_call("POST", "/api/integrate", body)
        self.assertTrue(status.startswith("500"))
        self.assertIn("GEMINI_API_KEY", out.decode("utf-8"))

    def test_validation_error_is_400(self):
        os.environ["GEMINI_API_KEY"] = "dummy"  # 検証で弾かれるので API は呼ばれない
        body = b'{"interest":"","tenmei":""}'
        status, _, out = wsgi_call("POST", "/api/integrate", body)
        self.assertTrue(status.startswith("400"))
        self.assertIn("両方を入力".encode("utf-8"), out)

    def test_bad_json_is_400(self):
        os.environ["GEMINI_API_KEY"] = "dummy"
        status, _, _ = wsgi_call("POST", "/api/integrate", b"not json{")
        self.assertTrue(status.startswith("400"))


class ServiceValidationTest(unittest.TestCase):
    def test_requires_both_reports(self):
        with self.assertRaises(ValueError):
            run_integration({"interest": "x", "tenmei": ""})

    def test_rejects_oversize_input(self):
        big = "あ" * 60_001
        with self.assertRaises(ValueError):
            run_integration({"interest": big, "tenmei": "y"})


if __name__ == "__main__":
    unittest.main()
