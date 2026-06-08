#!/usr/bin/env python3
"""Small Kiwoom REST API client shared by collection scripts."""

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


KIWOOM_TOKEN_ENDPOINT = "/oauth2/token"
DEFAULT_KIWOOM_BASE_URL = "https://api.kiwoom.com"

JsonDict = Dict[str, Any]
Transport = Callable[[str, JsonDict, Dict[str, str], int], JsonDict]


class KiwoomRestError(RuntimeError):
    """Raised when Kiwoom credentials or API responses are invalid."""


@dataclass
class KiwoomSettings:
    """Connection settings for the Kiwoom REST API."""

    app_key: str = ""
    app_secret: str = ""
    access_token: str = ""
    base_url: str = DEFAULT_KIWOOM_BASE_URL
    timeout: int = 10

    @classmethod
    def from_env(cls, timeout: int = 10) -> "KiwoomSettings":
        """Build settings from KIWOOM_* environment variables."""
        return cls(
            app_key=os.environ.get("KIWOOM_APP_KEY", ""),
            app_secret=os.environ.get("KIWOOM_APP_SECRET", ""),
            access_token=os.environ.get("KIWOOM_ACCESS_TOKEN", ""),
            base_url=os.environ.get("KIWOOM_BASE_URL", DEFAULT_KIWOOM_BASE_URL),
            timeout=timeout,
        )


def post_json(url: str, body: JsonDict, headers: Dict[str, str], timeout: int) -> JsonDict:
    """POST a JSON request and decode a JSON response."""
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={**headers, "Content-Type": "application/json;charset=UTF-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec B310 - user-configured brokerage API.
        return json.loads(response.read().decode("utf-8"))


class KiwoomRestClient:
    """Minimal client for token issuance and authenticated Kiwoom REST calls."""

    def __init__(self, settings: KiwoomSettings, transport: Optional[Transport] = None):
        self.settings = settings
        self.transport = transport or post_json
        self._access_token = settings.access_token.strip()

    def get_access_token(self) -> str:
        """Return an existing access token or issue one with client credentials."""
        if self._access_token:
            return self._access_token
        if not self.settings.app_key or not self.settings.app_secret:
            raise KiwoomRestError("Missing KIWOOM_ACCESS_TOKEN or KIWOOM_APP_KEY/KIWOOM_APP_SECRET")

        response = self.transport(
            self._url(KIWOOM_TOKEN_ENDPOINT),
            {
                "grant_type": "client_credentials",
                "appkey": self.settings.app_key,
                "secretkey": self.settings.app_secret,
            },
            {},
            self.settings.timeout,
        )
        token = str(response.get("token") or "").strip()
        if not token:
            raise KiwoomRestError(f"Kiwoom token response missing token: {response.get('return_msg') or response}")
        self._access_token = token
        return token

    def post_api(self, api_id: str, path: str, body: JsonDict) -> JsonDict:
        """POST to an authenticated Kiwoom REST endpoint."""
        response = self.transport(
            self._url(path),
            body,
            {
                "authorization": f"Bearer {self.get_access_token()}",
                "api-id": api_id,
            },
            self.settings.timeout,
        )
        return_code = response.get("return_code")
        if return_code not in (None, "", 0, "0"):
            raise KiwoomRestError(f"Kiwoom API error: {response.get('return_msg') or response}")
        return response

    def _url(self, path: str) -> str:
        return self.settings.base_url.rstrip("/") + "/" + path.lstrip("/")
