#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.request


TEMPLATE_RE = re.compile(
    r"\{\{.+?\}\}|\$\{[A-Za-z_][A-Za-z0-9_]*\}|\$[A-Za-z_][A-Za-z0-9_]*"
)


def expand(value):
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [expand(item) for item in value]
    if isinstance(value, dict):
        return {key: expand(item) for key, item in value.items()}
    return value


def has_unresolved_template(value):
    return isinstance(value, str) and bool(TEMPLATE_RE.search(value))


def missing_required_env(names):
    missing = []
    for name in names or []:
        value = os.environ.get(str(name), "").strip()
        if not value or has_unresolved_template(value):
            missing.append(str(name))
    return missing


def cleaned_headers(raw):
    headers = {}
    for key, value in (raw or {}).items():
        value = expand(str(value)).strip()
        if not value:
            continue
        if key.lower() == "authorization":
            token = (
                value.split(" ", 1)[1].strip()
                if value.lower().startswith("bearer ")
                else value
            )
            if not token or has_unresolved_template(token):
                continue
        headers[key] = value
    return headers


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024 * 8), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def run_curl(url, output, headers):
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
    cmd = [
        "curl",
        "-fL",
        "--retry",
        "5",
        "--retry-delay",
        "3",
        "--retry-all-errors",
        "-A",
        headers.get("User-Agent", "Mozilla/5.0"),
    ]
    for key, value in headers.items():
        if key.lower() == "user-agent":
            continue
        cmd.extend(["-H", f"{key}: {value}"])
    cmd.extend(["-o", str(tmp), url])
    subprocess.run(cmd, check=True)
    tmp.replace(output)


def resolve_download_url(url, headers, timeout=90):
    request_headers = {
        "User-Agent": headers.get("User-Agent", "runpod-anima-rmbg-template")
    }
    request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.geturl()


def run_aria2(url, output, connections, splits):
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "aria2c",
        "-x",
        str(connections),
        "-s",
        str(splits),
        "-k",
        "1M",
        "--continue=true",
        "--allow-overwrite=true",
        "--auto-file-renaming=false",
        "--summary-interval=10",
        "--console-log-level=warn",
        "-d",
        str(output.parent),
        "-o",
        output.name,
        url,
    ]
    subprocess.run(cmd, check=True)


def run_urllib(url, output, headers):
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    request_headers = {
        "User-Agent": headers.get("User-Agent", "runpod-anima-rmbg-template")
    }
    request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(request, timeout=120) as response, tmp.open("wb") as handle:
        shutil.copyfileobj(response, handle, length=1024 * 1024 * 8)
    tmp.replace(output)


def download(entry, root, use_aria2, connections, splits):
    entry = expand(entry)
    if not entry.get("enabled", True):
        print(f"SKIP disabled: {entry.get('name') or entry.get('path')}")
        return

    name = entry.get("name") or entry.get("path")
    required = bool(entry.get("required", True))
    missing_env = missing_required_env(entry.get("requires_env"))
    if missing_env:
        message = f"missing required env for {name}: {', '.join(missing_env)}"
        if required:
            raise RuntimeError(message)
        print(f"WARN optional model skipped: {message}", file=sys.stderr)
        return

    url = entry["url"]
    if has_unresolved_template(url):
        message = f"unresolved template in url for {name}"
        if required:
            raise RuntimeError(message)
        print(f"WARN optional model skipped: {message}", file=sys.stderr)
        return

    output = root / entry["path"]
    expected_sha = (entry.get("sha256") or "").lower()
    min_bytes = int(entry.get("min_bytes") or 0)

    if output.exists() and output.stat().st_size > 0:
        if min_bytes and output.stat().st_size < min_bytes:
            print(f"Too small, redownloading: {name}", file=sys.stderr)
            output.unlink()
        elif expected_sha and sha256_file(output) != expected_sha:
            print(f"SHA mismatch, redownloading: {name}", file=sys.stderr)
            output.unlink()
        else:
            print(f"SKIP existing: {name}")
            return

    headers = cleaned_headers(entry.get("headers"))
    method = str(entry.get("method") or "").lower()
    try:
        print(f"DOWNLOAD: {name}")
        if method == "curl" and shutil.which("curl"):
            run_curl(url, output, headers)
        elif use_aria2 and entry.get("use_aria2", True) and shutil.which("aria2c"):
            final_url = resolve_download_url(url, headers)
            run_aria2(final_url, output, connections, splits)
        else:
            run_urllib(url, output, headers)

        if min_bytes and output.stat().st_size < min_bytes:
            raise RuntimeError(
                f"downloaded file is too small: {output} ({output.stat().st_size} bytes)"
            )
        if expected_sha and sha256_file(output) != expected_sha:
            raise RuntimeError(f"sha256 mismatch: {output}")
    except Exception as exc:
        tmp = output.with_suffix(output.suffix + ".tmp")
        if tmp.exists():
            tmp.unlink()
        if output.exists():
            output.unlink()
        if required:
            raise
        print(f"WARN optional model failed: {name}: {exc}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--no-aria2", action="store_true")
    parser.add_argument(
        "--connections", type=int, default=int(os.environ.get("ARIA2_CONNECTIONS", "16"))
    )
    parser.add_argument("--splits", type=int, default=int(os.environ.get("ARIA2_SPLITS", "16")))
    args = parser.parse_args()

    manifest = json.loads(pathlib.Path(args.manifest).read_text(encoding="utf-8"))
    root = pathlib.Path(args.root)
    for entry in manifest.get("models", []):
        download(entry, root, not args.no_aria2, args.connections, args.splits)


if __name__ == "__main__":
    main()

