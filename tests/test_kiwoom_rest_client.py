#!/usr/bin/env python3
"""Unit tests for the Kiwoom REST client."""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.kiwoom_rest_client import KiwoomRestClient, KiwoomRestError, KiwoomSettings


class FakeTransport:
    """Capture JSON POST calls and return queued responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, body, headers, timeout):
        self.calls.append({
            "url": url,
            "body": body,
            "headers": headers,
            "timeout": timeout,
        })
        if not self.responses:
            raise AssertionError("Unexpected Kiwoom transport call")
        return self.responses.pop(0)


class KiwoomRestClientTests(unittest.TestCase):
    def test_issues_access_token_with_client_credentials(self):
        transport = FakeTransport([
            {"token": "issued-token", "token_type": "bearer", "expires_dt": "20260608090000", "return_code": 0}
        ])
        settings = KiwoomSettings(
            app_key="app-key",
            app_secret="app-secret",
            base_url="https://mockapi.kiwoom.com/",
            timeout=7,
        )

        client = KiwoomRestClient(settings, transport=transport)

        self.assertEqual(client.get_access_token(), "issued-token")
        self.assertEqual(transport.calls[0]["url"], "https://mockapi.kiwoom.com/oauth2/token")
        self.assertEqual(transport.calls[0]["body"], {
            "grant_type": "client_credentials",
            "appkey": "app-key",
            "secretkey": "app-secret",
        })
        self.assertEqual(transport.calls[0]["timeout"], 7)

    def test_posts_api_request_with_bearer_token_and_api_id(self):
        transport = FakeTransport([
            {"return_code": 0, "items": [{"stk_cd": "005930"}]},
        ])
        settings = KiwoomSettings(access_token="cached-token", base_url="https://api.kiwoom.com")
        client = KiwoomRestClient(settings, transport=transport)

        response = client.post_api("ka10034", "/api/dostk/rkinfo", {"mrkt_tp": "000"})

        self.assertEqual(response["items"][0]["stk_cd"], "005930")
        self.assertEqual(transport.calls[0]["headers"]["authorization"], "Bearer cached-token")
        self.assertEqual(transport.calls[0]["headers"]["api-id"], "ka10034")
        self.assertEqual(transport.calls[0]["url"], "https://api.kiwoom.com/api/dostk/rkinfo")

    def test_raises_clear_error_when_api_returns_failure(self):
        transport = FakeTransport([
            {"return_code": 99, "return_msg": "invalid request"},
        ])
        settings = KiwoomSettings(access_token="cached-token")
        client = KiwoomRestClient(settings, transport=transport)

        with self.assertRaisesRegex(KiwoomRestError, "invalid request"):
            client.post_api("ka10034", "/api/dostk/rkinfo", {})

    def test_loads_settings_from_environment(self):
        original = {key: os.environ.get(key) for key in [
            "KIWOOM_APP_KEY",
            "KIWOOM_APP_SECRET",
            "KIWOOM_ACCESS_TOKEN",
            "KIWOOM_BASE_URL",
        ]}
        try:
            os.environ["KIWOOM_APP_KEY"] = "env-app"
            os.environ["KIWOOM_APP_SECRET"] = "env-secret"
            os.environ["KIWOOM_ACCESS_TOKEN"] = "env-token"
            os.environ["KIWOOM_BASE_URL"] = "https://mockapi.kiwoom.com"

            settings = KiwoomSettings.from_env()

            self.assertEqual(settings.app_key, "env-app")
            self.assertEqual(settings.app_secret, "env-secret")
            self.assertEqual(settings.access_token, "env-token")
            self.assertEqual(settings.base_url, "https://mockapi.kiwoom.com")
        finally:
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
