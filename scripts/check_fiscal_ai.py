#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Smoke-test Fiscal.ai API connectivity without printing secrets.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict

from lib.env import read_env_file_value


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT / ".env.local"
FISCAL_PROFILE_URLS = (
    "https://api.fiscal.ai/v2/company/profile",
    "https://api.fiscal.ai/v1/company/profile",
)


def configure_stdio() -> None:
    """Prefer UTF-8 console output when the runtime supports it."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")





def fiscal_request(company_key: str, api_key: str, timeout: int) -> Dict:
    """Fetch a company profile from Fiscal.ai using supported auth shapes."""
    attempts = []
    for base_url in FISCAL_PROFILE_URLS:
        for auth_mode in ("header", "query"):
            query_params = {"companyKey": company_key}
            headers = {
                "Accept": "application/json",
                "User-Agent": "stock-orchestrator/1.0",
            }
            if auth_mode == "header":
                headers["X-Api-Key"] = api_key
            else:
                query_params["apiKey"] = api_key
            query = urllib.parse.urlencode(query_params)
            request = urllib.request.Request(f"{base_url}?{query}", headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    payload = response.read().decode("utf-8")
                data = json.loads(payload)
                data["_fiscal_check"] = {"endpoint": base_url.rsplit("/", 3)[-3] if "/v" in base_url else base_url, "auth_mode": auth_mode}
                return data
            except urllib.error.HTTPError as exc:
                attempts.append({"endpoint": base_url.rsplit("/", 3)[-3], "auth_mode": auth_mode, "status": exc.code})
            except Exception as exc:
                attempts.append({"endpoint": base_url.rsplit("/", 3)[-3], "auth_mode": auth_mode, "error": exc.__class__.__name__})
    raise RuntimeError(json.dumps({"attempts": attempts}, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Check Fiscal.ai API connectivity.")
    parser.add_argument("--company-key", default="NASDAQ_MSFT")
    parser.add_argument("--api-key-env", default="FISCAL_AI_API_KEY")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--timeout", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    api_key = os.environ.get(args.api_key_env, "").strip() or read_env_file_value(Path(args.env_file), args.api_key_env)
    if not api_key:
        print(f"ERROR {args.api_key_env} is not set in environment or {args.env_file}", file=sys.stderr)
        return 1
    try:
        data = fiscal_request(args.company_key, api_key, args.timeout)
        company_name = data.get("name") or data.get("companyName") or data.get("ticker") or args.company_key
        print(json.dumps({
            "ok": True,
            "source": "fiscal_ai",
            "company_key": args.company_key,
            "company": company_name,
            "connection": data.get("_fiscal_check", {}),
            "key_present": True,
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "source": "fiscal_ai",
            "company_key": args.company_key,
            "key_present": True,
            "error": str(exc) if exc.__class__.__name__ == "RuntimeError" else exc.__class__.__name__,
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
