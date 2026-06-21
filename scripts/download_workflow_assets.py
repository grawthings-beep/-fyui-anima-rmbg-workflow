#!/usr/bin/env python3
import argparse
import json
import pathlib
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "config" / "workflow-assets.json"


def load_manifest(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def select_assets(entries, selected_ids):
    if not selected_ids:
        return entries
    wanted = {value.casefold() for value in selected_ids}
    selected = [entry for entry in entries if entry["id"].casefold() in wanted]
    missing = wanted - {entry["id"].casefold() for entry in selected}
    if missing:
        raise ValueError(f"unknown asset id(s): {', '.join(sorted(missing))}")
    return selected


def parse_hf_resolve_url(url):
    path = unquote(urlsplit(url).path).strip("/").split("/")
    if len(path) < 5 or path[2:4] != ["resolve", "main"]:
        raise ValueError(f"unsupported Hugging Face resolve URL: {url}")
    return "/".join(path[:2]), "/".join(path[4:])


def verify_hf_login():
    try:
        subprocess.run(["hf", "auth", "whoami"], check=True)
    except FileNotFoundError as exc:
        raise SystemExit(
            "The hf command was not found. Install huggingface_hub, "
            "then run: hf auth login"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            "Hugging Face authentication is required. Run: hf auth login"
        ) from exc


def target_is_valid(path, minimum):
    return path.exists() and path.stat().st_size >= int(minimum or 0)


def copy_from_source(entry, root, source_root):
    target = root / entry["path"]
    source = source_root / entry["path"]
    if not source.exists():
        return False
    minimum = int(entry.get("min_bytes") or 0)
    if source.stat().st_size < minimum:
        raise RuntimeError(f"source file is too small: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"COPY: {entry['id']} -> {target}")
    return True


def download_from_hf(entry, root):
    url = entry.get("url")
    if not url:
        raise RuntimeError(
            f"{entry['id']} has no URL in config/workflow-assets.json"
        )

    target = root / entry["path"]
    minimum = int(entry.get("min_bytes") or 0)
    repo_id, filename = parse_hf_resolve_url(url)
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"DOWNLOAD: {entry['id']} -> {target}")
    with tempfile.TemporaryDirectory(
        prefix=f".{entry['id']}-",
        dir=target.parent,
    ) as temporary_directory:
        subprocess.run(
            [
                "hf",
                "download",
                repo_id,
                filename,
                "--repo-type",
                "model",
                "--local-dir",
                temporary_directory,
            ],
            check=True,
        )
        temporary = pathlib.Path(temporary_directory) / filename
        if not temporary.is_file():
            raise RuntimeError(f"hf download did not create: {temporary}")
        if temporary.stat().st_size < minimum:
            raise RuntimeError(f"downloaded file is too small: {temporary}")
        temporary.replace(target)


def main():
    parser = argparse.ArgumentParser(
        description="Download or copy only the model files referenced by the packaged workflow."
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument(
        "--root",
        default="/workspace/comfyui",
        help="ComfyUI root containing the models directory.",
    )
    parser.add_argument(
        "--source-root",
        help="Optional existing ComfyUI root to copy already-installed assets from first.",
    )
    parser.add_argument(
        "--id",
        action="append",
        dest="selected_ids",
        help="Download/copy only this asset id. Repeat for multiple assets.",
    )
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    assets = select_assets(manifest.get("assets", []), args.selected_ids)
    if args.list:
        for entry in assets:
            url_state = "url" if entry.get("url") else "missing-url"
            print(f"{entry['id']:28} {entry['kind']:16} {url_state:11} {entry['path']}")
        return

    root = pathlib.Path(args.root)
    source_root = pathlib.Path(args.source_root) if args.source_root else None
    if any(entry.get("url") for entry in assets):
        verify_hf_login()

    failures = []
    for entry in assets:
        target = root / entry["path"]
        if target_is_valid(target, entry.get("min_bytes")):
            print(f"SKIP existing: {entry['id']} -> {target}")
            continue
        try:
            if source_root and copy_from_source(entry, root, source_root):
                continue
            download_from_hf(entry, root)
        except Exception as exc:
            failures.append((entry["id"], exc))
            print(f"ERROR: {entry['id']}: {exc}")

    if failures:
        raise SystemExit(f"{len(failures)} asset install(s) failed")


if __name__ == "__main__":
    main()
