#!/usr/bin/env python3
"""Strict prepublish checks for CardputerZero AppStore submissions."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


REQUIRED_CONTROL_FIELDS = ("Package", "Version", "Architecture", "Maintainer")


class Problem:
    def __init__(self, severity: str, message: str) -> None:
        self.severity = severity
        self.message = message


def slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return value or "app"


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def load_json(path: Path, problems: list[Problem]) -> dict:
    if not path.is_file():
        problems.append(Problem("error", f"app-builder.json not found: {path}"))
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - show parse details to the user.
        problems.append(Problem("error", f"app-builder.json is not valid JSON: {exc}"))
        return {}


def png_size(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as fh:
            header = fh.read(24)
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", header[16:24])


def check_image(path: Path, label: str, problems: list[Problem], require_square: bool = False) -> None:
    if not path.is_file():
        problems.append(Problem("error", f"{label} file not found: {path}"))
        return
    suffix = path.suffix.lower()
    if suffix == ".png":
        size = png_size(path)
        if not size:
            problems.append(Problem("error", f"{label} is not a valid PNG: {path}"))
            return
        if require_square and size[0] != size[1]:
            problems.append(Problem("error", f"{label} must be square, got {size[0]}x{size[1]}: {path}"))
        if min(size) < 64:
            problems.append(Problem("warning", f"{label} is very small ({size[0]}x{size[1]}): {path}"))
    elif suffix not in {".jpg", ".jpeg"}:
        problems.append(Problem("error", f"{label} must be PNG/JPEG: {path}"))


def app_name_from_manifest(raw: dict) -> str:
    for key in ("app_name", "name", "package_name", "package"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "App"


def package_from_manifest(raw: dict) -> str:
    for key in ("package_name", "package", "name", "app_name"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return slug(value)
    return "app"


def generate_source_icon(app_dir: Path, manifest_path: Path, raw: dict, problems: list[Problem]) -> bool:
    store = raw.setdefault("store", {})
    if not isinstance(store, dict):
        problems.append(Problem("error", "app-builder.json field store must be an object"))
        return False

    icon_rel = store.get("icon")
    if not isinstance(icon_rel, str) or not icon_rel.strip():
        icon_rel = f"share/images/{package_from_manifest(raw)}.png"
        store["icon"] = icon_rel

    icon_path = app_dir / icon_rel
    summary = " ".join(
        str(v)
        for v in (
            raw.get("description", ""),
            store.get("summary", ""),
            app_name_from_manifest(raw),
        )
        if v
    )

    generator = Path(__file__).resolve().parents[1].parent / "cardputer-zero-application" / "scripts" / "generate_app_icon.py"
    if not generator.is_file():
        problems.append(Problem("error", f"icon generator not found: {generator}"))
        return False

    cmd = [
        sys.executable,
        str(generator),
        "--app-name",
        app_name_from_manifest(raw),
        "--summary",
        summary,
        "--out",
        str(icon_path),
        "--force",
    ]
    result = run(cmd, cwd=app_dir)
    if result.returncode != 0:
        problems.append(Problem("error", f"failed to generate source icon:\n{result.stderr.strip()}"))
        return False

    manifest_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result.stdout.strip())
    print(f"fixed source icon metadata: {icon_rel}")
    return True


def extract_deb(deb: Path, problems: list[Problem]) -> tuple[dict[str, str], Path | None, tempfile.TemporaryDirectory[str] | None]:
    if not deb.is_file():
        problems.append(Problem("error", f"deb file not found: {deb}"))
        return {}, None, None
    if not shutil.which("dpkg-deb"):
        problems.append(Problem("error", "dpkg-deb is required for publish preflight checks"))
        return {}, None, None

    metadata: dict[str, str] = {}
    for field in REQUIRED_CONTROL_FIELDS:
        result = run(["dpkg-deb", "-f", str(deb), field])
        if result.returncode != 0:
            problems.append(Problem("error", f"dpkg-deb -f {field} failed: {result.stderr.strip()}"))
            continue
        metadata[field] = result.stdout.strip()

    tmp = tempfile.TemporaryDirectory(prefix="cardputer-prepublish-")
    root = Path(tmp.name)
    result = run(["dpkg-deb", "-x", str(deb), str(root)])
    if result.returncode != 0:
        problems.append(Problem("error", f"dpkg-deb -x failed: {result.stderr.strip()}"))
        tmp.cleanup()
        return metadata, None, None
    return metadata, root, tmp


def parse_desktop(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key.strip()] = value.strip()
    return fields


def check_deb_payload(root: Path, problems: list[Problem]) -> None:
    app_root = root / "usr/share/APPLaunch"
    apps_dir = app_root / "applications"
    desktops = sorted(apps_dir.glob("*.desktop")) if apps_dir.is_dir() else []
    if not desktops:
        problems.append(Problem("error", "deb is missing /usr/share/APPLaunch/applications/*.desktop"))
        return
    if len(desktops) > 1:
        problems.append(Problem("warning", f"deb contains multiple .desktop files: {', '.join(p.name for p in desktops)}"))

    for desktop in desktops:
        fields = parse_desktop(desktop)
        for key in ("Name", "Exec", "Icon"):
            if not fields.get(key):
                problems.append(Problem("error", f"{desktop.name} missing required field {key}"))
        icon = fields.get("Icon", "")
        if icon:
            if icon.startswith("/"):
                icon_path = root / icon.lstrip("/")
            else:
                icon_path = app_root / icon
            check_image(icon_path, f"{desktop.name} Icon", problems, require_square=True)
        exec_value = fields.get("Exec", "")
        if exec_value.startswith("/"):
            exec_path = root / exec_value.lstrip("/")
            if not exec_path.exists():
                problems.append(Problem("error", f"{desktop.name} Exec target not found in deb: {exec_value}"))
        elif "/" in exec_value:
            exec_path = app_root / exec_value
            if not exec_path.exists():
                problems.append(Problem("error", f"{desktop.name} Exec target not found in deb: {exec_value}"))


def check_manifest(app_dir: Path, raw: dict, problems: list[Problem]) -> None:
    if not raw:
        return
    store = raw.get("store")
    if not isinstance(store, dict):
        problems.append(Problem("error", 'app-builder.json missing required object "store"'))
        return

    summary = store.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        problems.append(Problem("error", "store.summary is required"))

    categories = store.get("categories")
    if not isinstance(categories, list) or not any(isinstance(v, str) and v.strip() for v in categories):
        problems.append(Problem("error", "store.categories must contain at least one category"))

    icon = store.get("icon")
    if not isinstance(icon, str) or not icon.strip():
        problems.append(Problem("error", "store.icon is required and must point to a square PNG"))
    else:
        check_image(app_dir / icon, "store.icon", problems, require_square=True)

    screenshots = store.get("screenshots")
    if not isinstance(screenshots, list) or not screenshots:
        problems.append(Problem("error", "store.screenshots must contain at least one screenshot"))
    else:
        for idx, shot in enumerate(screenshots, start=1):
            if not isinstance(shot, str) or not shot.strip():
                problems.append(Problem("error", f"store.screenshots[{idx}] must be a path string"))
                continue
            check_image(app_dir / shot, f"store.screenshots[{idx}]", problems)

    for key in ("app_name", "package_name", "version", "description"):
        value = raw.get(key)
        fallback_ok = key == "package_name" and isinstance(raw.get("package"), str)
        fallback_ok = fallback_ok or (key == "app_name" and isinstance(raw.get("name"), str))
        if not fallback_ok and (not isinstance(value, str) or not value.strip()):
            problems.append(Problem("warning", f"app-builder.json missing recommended field {key}"))


def print_report(problems: list[Problem]) -> int:
    errors = [p for p in problems if p.severity == "error"]
    warnings = [p for p in problems if p.severity == "warning"]
    if errors:
        print("Prepublish check failed:")
        for problem in errors:
            print(f"  ERROR: {problem.message}")
        for problem in warnings:
            print(f"  WARN: {problem.message}")
        return 1
    print("Prepublish check passed.")
    for problem in warnings:
        print(f"  WARN: {problem.message}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate critical CardputerZero AppStore publish metadata and deb payload.")
    parser.add_argument("--deb", required=True, type=Path, help="Path to the .deb that will be submitted.")
    parser.add_argument("--app-dir", type=Path, default=Path("."), help="App project directory containing app-builder.json.")
    parser.add_argument("--auto-fix-source-icon", action="store_true", help="Generate a missing source store.icon and update app-builder.json. Rebuild the .deb afterwards.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    app_dir = args.app_dir.resolve()
    deb = args.deb.resolve()
    problems: list[Problem] = []
    manifest_path = app_dir / "app-builder.json"
    raw = load_json(manifest_path, problems)

    if args.auto_fix_source_icon and raw:
        store = raw.get("store")
        missing_icon = not isinstance(store, dict) or not isinstance(store.get("icon"), str) or not store.get("icon", "").strip()
        missing_file = False
        if isinstance(store, dict) and isinstance(store.get("icon"), str) and store["icon"].strip():
            missing_file = not (app_dir / store["icon"]).is_file()
        if missing_icon or missing_file:
            generate_source_icon(app_dir, manifest_path, raw, problems)
            raw = load_json(manifest_path, problems)

    check_manifest(app_dir, raw, problems)
    metadata, root, tmp = extract_deb(deb, problems)
    try:
        for field in REQUIRED_CONTROL_FIELDS:
            if not metadata.get(field):
                problems.append(Problem("error", f"deb control field {field} is required"))
        if metadata.get("Architecture") and metadata["Architecture"] != "arm64":
            problems.append(Problem("error", f"deb Architecture must be arm64, got {metadata['Architecture']}"))
        if root:
            check_deb_payload(root, problems)
    finally:
        if tmp:
            tmp.cleanup()

    return print_report(problems)


if __name__ == "__main__":
    raise SystemExit(main())
