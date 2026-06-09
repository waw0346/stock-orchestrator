#!/usr/bin/env python3
# pylint: disable=broad-exception-caught
"""
Script to refresh Kiwoom REST API access token and save it to .env.local.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.local"
DEFAULT_KIWOOM_BASE_URL = "https://api.kiwoom.com"


def configure_stdio() -> None:
    """Prefer UTF-8 console output when supported."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def load_env_file(path: Path) -> dict:
    """Load env variables from file."""
    env = {}
    if not path.exists():
        return env
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env[key.strip()] = val.strip().strip('"').strip("'")
    except Exception as exc:
        print(f"Warning: Failed to read env file: {exc}", file=sys.stderr)
    return env


def update_env_file(path: Path, new_token: str) -> None:
    """Update KIWOOM_ACCESS_TOKEN in env file, preserving other contents."""
    if not path.exists():
        path.write_text(f"KIWOOM_ACCESS_TOKEN={new_token}\n", encoding="utf-8")
        return

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    updated = False
    new_lines = []

    for line in lines:
        if line.strip().startswith("KIWOOM_ACCESS_TOKEN="):
            new_lines.append(f"KIWOOM_ACCESS_TOKEN={new_token}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"KIWOOM_ACCESS_TOKEN={new_token}")

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def main() -> int:
    configure_stdio()
    env = load_env_file(ENV_FILE)

    app_key = env.get("KIWOOM_APP_KEY") or os.environ.get("KIWOOM_APP_KEY", "")
    app_secret = env.get("KIWOOM_APP_SECRET") or os.environ.get("KIWOOM_APP_SECRET", "")
    base_url = env.get("KIWOOM_BASE_URL") or os.environ.get("KIWOOM_BASE_URL", DEFAULT_KIWOOM_BASE_URL)

    if not app_key or not app_secret:
        print("Error: KIWOOM_APP_KEY or KIWOOM_APP_SECRET is missing in .env.local", file=sys.stderr)
        return 1

    url = base_url.rstrip("/") + "/oauth2/token"
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "secretkey": app_secret,
    }
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json;charset=UTF-8"}

    print(f"Requesting new access token from {url}...", file=sys.stderr)
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            token = str(res_data.get("token") or "").strip()
            if not token:
                print(f"Error: Token response missing token: {res_data}", file=sys.stderr)
                return 1

            print("Token successfully issued. Updating .env.local...", file=sys.stderr)
            update_env_file(ENV_FILE, token)
            print("Successfully refreshed and saved KIWOOM_ACCESS_TOKEN to .env.local!", file=sys.stdout)
            return 0
    except Exception as exc:
        print(f"Error issuing token: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
