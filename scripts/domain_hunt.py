#!/usr/bin/env python3
import argparse
import json
import ssl
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib import error, parse, request


COMMON_RDAP = {
    "com": "https://rdap.verisign.com/com/v1/",
    "net": "https://rdap.verisign.com/net/v1/",
    "org": "https://rdap.publicinterestregistry.org/rdap/",
    "io": "https://rdap.identitydigital.services/rdap/",
    "co": "https://rdap.centralnic.com/co/",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search for available domains using prefix + zero-padded numeric suffix."
    )
    parser.add_argument("--prefix", default="", help="Fixed prefix before the numeric suffix.")
    parser.add_argument(
        "--digits",
        type=int,
        default=5,
        help="Width of the numeric suffix. Example: 3 -> 000..999",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Starting numeric value for the suffix range.",
    )
    parser.add_argument(
        "--end",
        type=int,
        help="Ending numeric value for the suffix range. Defaults to the max for the digit width.",
    )
    parser.add_argument("--tld", default="com", help="Top-level domain without a leading dot.")
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=350,
        help="Delay between RDAP checks in milliseconds.",
    )
    parser.add_argument(
        "--stop-after-hits",
        type=int,
        default=50,
        help="Stop early after this many available domains are found. Use 0 to disable.",
    )
    parser.add_argument(
        "--results-dir",
        default="results",
        help="Directory where result files will be written.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="HTTP timeout in seconds.",
    )
    return parser


def http_get_json(url: str, timeout: float) -> Tuple[int, Optional[dict], Optional[str]]:
    req = request.Request(
        url,
        headers={
            "Accept": "application/rdap+json, application/json",
            "User-Agent": "domain-finder-actions/1.0",
        },
    )
    context = ssl.create_default_context()
    try:
        with request.urlopen(req, timeout=timeout, context=context) as resp:
            status = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body else {}
            return status, data, None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        data = None
        if body:
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = None
        return exc.code, data, body or exc.reason
    except Exception as exc:
        return 0, None, str(exc)


def discover_rdap_base(tld: str, timeout: float) -> Optional[str]:
    if tld in COMMON_RDAP:
        return COMMON_RDAP[tld]

    bootstrap_url = "https://data.iana.org/rdap/dns.json"
    status, data, _ = http_get_json(bootstrap_url, timeout)
    if status != 200 or not data:
        return None

    for service in data.get("services", []):
        suffixes = service[0] if len(service) > 0 else []
        base_urls = service[1] if len(service) > 1 else []
        if tld in suffixes and base_urls:
            return base_urls[0]
    return None


def classify_domain(domain: str, rdap_base: str, timeout: float) -> Tuple[str, str]:
    url = parse.urljoin(rdap_base.rstrip("/") + "/", f"domain/{domain}")
    status, data, raw_error = http_get_json(url, timeout)

    if status == 200 and data is not None:
        return "taken", "RDAP record exists"

    if status == 404:
        title = ""
        description = ""
        if data:
            title = str(data.get("title", ""))
            description_list = data.get("description", [])
            description = " ".join(description_list) if isinstance(description_list, list) else str(description_list)
        detail = " ".join(part for part in [title, description] if part).strip() or "RDAP 404"
        return "available", detail

    if status in {429, 502, 503, 504}:
        return "unclear", f"temporary HTTP {status}"

    if status == 0:
        return "unclear", raw_error or "network error"

    return "unclear", f"unexpected HTTP {status}"


def ensure_results_dir(path_str: str) -> Path:
    path = Path(path_str)
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_domains(prefix: str, digits: int, start: int, end: int, tld: str):
    width = max(digits, 1)
    for value in range(start, end + 1):
        suffix = f"{value:0{width}d}"
        yield f"{prefix}{suffix}.{tld}"


def write_outputs(
    results_dir: Path,
    params: dict,
    stats: dict,
    available_domains: List[str],
    sample_errors: List[dict],
) -> None:
    (results_dir / "available_domains.txt").write_text(
        "\n".join(available_domains) + ("\n" if available_domains else ""),
        encoding="utf-8",
    )

    report = {
        "params": params,
        "stats": stats,
        "available_domains": available_domains,
        "sample_unclear_results": sample_errors,
    }
    (results_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Domain Hunt Summary",
        "",
        f"- Prefix: `{params['prefix']}`",
        f"- Digits: `{params['digits']}`",
        f"- Range: `{params['start']}` to `{params['end']}`",
        f"- TLD: `.{params['tld']}`",
        f"- Checked: `{stats['checked']}`",
        f"- Available: `{stats['available']}`",
        f"- Taken: `{stats['taken']}`",
        f"- Unclear: `{stats['unclear']}`",
        "",
    ]

    if available_domains:
        lines.append("## Available Domains")
        lines.append("")
        for domain in available_domains[:100]:
            lines.append(f"- {domain}")
        if len(available_domains) > 100:
            lines.append("")
            lines.append(f"Only the first 100 are shown here. Full list: `{results_dir / 'available_domains.txt'}`")
    else:
        lines.append("No available domains were found in this run.")

    if sample_errors:
        lines.extend(["", "## Sample Unclear Results", ""])
        for item in sample_errors[:20]:
            lines.append(f"- {item['domain']}: {item['detail']}")

    (results_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    tld = args.tld.lower().lstrip(".")
    end = args.end if args.end is not None else (10**args.digits) - 1

    if args.digits < 1:
        print("--digits must be >= 1", file=sys.stderr)
        return 2
    if args.start < 0 or end < 0 or end < args.start:
        print("invalid start/end range", file=sys.stderr)
        return 2

    rdap_base = discover_rdap_base(tld, args.timeout)
    if not rdap_base:
        print(f"Unable to discover an RDAP endpoint for .{tld}", file=sys.stderr)
        return 2

    results_dir = ensure_results_dir(args.results_dir)
    params = {
        "prefix": args.prefix,
        "digits": args.digits,
        "start": args.start,
        "end": end,
        "tld": tld,
        "delay_ms": args.delay_ms,
        "stop_after_hits": args.stop_after_hits,
        "rdap_base": rdap_base,
    }

    stats = {"checked": 0, "available": 0, "taken": 0, "unclear": 0}
    available_domains: List[str] = []
    sample_errors: List[dict] = []
    total_candidates = (end - args.start) + 1

    print(json.dumps({"event": "start", "params": params, "total_candidates": total_candidates}, ensure_ascii=False))

    for domain in generate_domains(args.prefix, args.digits, args.start, end, tld):
        status, detail = classify_domain(domain, rdap_base, args.timeout)
        stats["checked"] += 1
        stats[status] += 1

        if status == "available":
            available_domains.append(domain)
            print(f"[AVAILABLE] {domain} :: {detail}")
        elif status == "unclear" and len(sample_errors) < 50:
            sample_errors.append({"domain": domain, "detail": detail})
            print(f"[UNCLEAR]   {domain} :: {detail}", file=sys.stderr)

        if stats["checked"] % 25 == 0:
            print(json.dumps({"event": "progress", "stats": stats}, ensure_ascii=False))

        if args.stop_after_hits > 0 and len(available_domains) >= args.stop_after_hits:
            print(f"Reached stop-after-hits={args.stop_after_hits}, ending early.")
            break

        if args.delay_ms > 0:
            time.sleep(args.delay_ms / 1000.0)

    write_outputs(results_dir, params, stats, available_domains, sample_errors)

    print(json.dumps({"event": "done", "stats": stats, "results_dir": str(results_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
