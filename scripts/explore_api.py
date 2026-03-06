#!/usr/bin/env python3
"""EVE Frontier World API Explorer.

Hit every known endpoint, dump response structure, save field names.
Run this FIRST before writing any schema or ingestion code.

Usage:
    python scripts/explore_api.py
    python scripts/explore_api.py --save  # writes to docs/api-notes.md
    python scripts/explore_api.py --base-url https://custom-api.example.com
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

# Known endpoints to probe — update as discovered
ENDPOINTS = [
    "/types",
    "/killmails",
    "/smartassemblies",
    "/smartcharacters",
    "/smartgates",
    "/smartstorage",
    "/smartturrets",
    "/solarsystems",
    "/smartdeployables",
    "/health",
    "/status",
]

# Alternate base URLs to try
BASE_URLS = [
    "https://world-api.evefrontier.com",
    "https://blockchain-gateway-stillness.live.tech.evefrontier.com",
    "https://blockchain-gateway-nova.nursery.reitnorf.com",
    "https://world-api-nova.nursery.reitnorf.com",
]


def probe_endpoint(client: httpx.Client, base: str, endpoint: str) -> dict:
    url = f"{base}{endpoint}"
    try:
        r = client.get(url, timeout=10.0)
        result = {
            "url": url,
            "status": r.status_code,
            "content_type": r.headers.get("content-type", ""),
        }

        if r.status_code == 200:
            try:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    result["count"] = len(data)
                    result["sample_keys"] = (
                        sorted(data[0].keys()) if isinstance(data[0], dict) else None
                    )
                    result["sample"] = data[0]
                elif isinstance(data, dict):
                    result["keys"] = sorted(data.keys())
                    result["sample"] = {k: type(v).__name__ for k, v in data.items()}
                else:
                    result["data_type"] = type(data).__name__
            except Exception:
                result["body_preview"] = r.text[:500]
        else:
            result["body_preview"] = r.text[:200]

        return result
    except httpx.TimeoutException:
        return {"url": url, "error": "timeout"}
    except httpx.ConnectError:
        return {"url": url, "error": "connection_failed"}
    except Exception as e:
        return {"url": url, "error": str(e)}


def find_working_base(client: httpx.Client) -> str | None:
    for base in BASE_URLS:
        print(f"  Trying {base}...", end=" ")
        try:
            r = client.get(f"{base}/types", timeout=5.0)
            if r.status_code in (200, 404, 403):
                print(f"REACHABLE (HTTP {r.status_code})")
                return base
        except Exception:
            pass
        print("FAILED")
    return None


def main():
    parser = argparse.ArgumentParser(description="EVE Frontier API Explorer")
    parser.add_argument("--save", action="store_true", help="Save results to docs/api-notes.md")
    parser.add_argument("--base-url", type=str, help="Override base URL")
    args = parser.parse_args()

    print("=== EVE Frontier World API Explorer ===")
    print(f"Time: {datetime.now(UTC).isoformat()}")
    print()

    client = httpx.Client()

    if args.base_url:
        base = args.base_url.rstrip("/")
        print(f"Using provided base URL: {base}")
    else:
        print("Discovering working API base URL...")
        base = find_working_base(client)
        if not base:
            print("\nERROR: No API endpoint reachable.")
            print("This is expected before March 11 (Sui migration).")
            print("Run again on hackathon day 1 with --base-url if needed.")
            sys.exit(1)

    print(f"\nUsing base: {base}")
    print("=" * 60)

    results = {}
    for endpoint in ENDPOINTS:
        print(f"\nProbing {endpoint}...")
        result = probe_endpoint(client, base, endpoint)
        results[endpoint] = result

        if "error" in result:
            print(f"  ERROR: {result['error']}")
        elif result["status"] == 200:
            if "count" in result:
                print(f"  OK — {result['count']} items")
                if result.get("sample_keys"):
                    print(f"  Fields: {result['sample_keys']}")
            elif "keys" in result:
                print(f"  OK — object with keys: {result['keys']}")
            else:
                print(f"  OK — {result.get('data_type', 'unknown')}")
        else:
            print(f"  HTTP {result['status']}")

    if args.save:
        output_path = Path("docs/api-notes.md")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write("# EVE Frontier API Field Mapping\n")
            f.write(f"Generated: {datetime.now(UTC).isoformat()}\n")
            f.write(f"Base URL: {base}\n\n")
            for endpoint, result in results.items():
                f.write(f"## {endpoint}\n")
                f.write(f"```json\n{json.dumps(result, indent=2, default=str)}\n```\n\n")
        print(f"\nSaved to {output_path}")

    # Also dump raw JSON for reference
    raw_path = Path("docs/api-raw-responses.json")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with open(raw_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Raw responses saved to {raw_path}")

    client.close()


if __name__ == "__main__":
    main()
