#!/usr/bin/env python3
"""Create APPLaunch desktop metadata and Debian staging files."""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "myapp"


def desktop_bool(value: bool) -> str:
    return "true" if value else "false"


def copy_executable(src: Path, dst: Path) -> None:
    if not src.is_file():
        raise SystemExit(f"binary not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    mode = dst.stat().st_mode
    dst.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def is_cardputer_zero() -> bool:
    if platform.system() != "Linux":
        return False
    if platform.machine().lower() not in {"aarch64", "arm64"}:
        return False

    applaunch_root = Path("/usr/share/APPLaunch")
    keyboard = Path("/dev/input/by-path/platform-3f804000.i2c-event")
    if applaunch_root.is_dir() or keyboard.exists():
        return True

    try:
        proc_fb = Path("/proc/fb").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        proc_fb = ""
    return "fb_st7789v" in proc_fb


def run_privileged(args) -> None:
    if os.geteuid() == 0:
        subprocess.run(args, check=True)
        return
    sudo = shutil.which("sudo")
    if not sudo:
        raise SystemExit("install requires root or sudo")
    subprocess.run([sudo, *args], check=True)


def install_to_applaunch(stage: Path, restart: bool) -> None:
    source = stage / "usr/share/APPLaunch"
    target = Path("/usr/share/APPLaunch")
    if not source.is_dir():
        raise SystemExit(f"missing staged APPLaunch tree: {source}")
    if not target.exists():
        raise SystemExit(f"APPLaunch target does not exist: {target}")

    for name in ("applications", "bin", "share", "lib"):
        src = source / name
        if src.exists():
            run_privileged(["mkdir", "-p", str(target / name)])
            run_privileged(["cp", "-a", f"{src}/.", str(target / name)])

    bin_dir = target / "bin"
    if (source / "bin").exists():
        run_privileged(["find", str(bin_dir), "-maxdepth", "1", "-type", "f", "-exec", "chmod", "755", "{}", "+"])

    print(f"installed into: {target}")
    if restart:
        systemctl = shutil.which("systemctl")
        if systemctl:
            run_privileged([systemctl, "restart", "APPLaunch.service"])
            print("restarted: APPLaunch.service")
        else:
            print("systemctl not found; restart APPLaunch manually")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create APPLaunch Debian staging files for Cardputer Zero apps."
    )
    parser.add_argument("--app-name", required=True, help="Launcher display name.")
    parser.add_argument(
        "--package",
        help="Debian package name. Defaults to a lowercase slug of --app-name.",
    )
    parser.add_argument("--version", default="0.1", help="Debian package version.")
    parser.add_argument(
        "--revision",
        default="m5stack1",
        help="Debian package revision for .deb name. Defaults to the existing APPLaunch package convention.",
    )
    parser.add_argument(
        "--binary",
        type=Path,
        help="Executable to copy into usr/share/APPLaunch/bin.",
    )
    parser.add_argument(
        "--exec",
        dest="exec_cmd",
        help="Exec value to write when --binary is not used.",
    )
    parser.add_argument(
        "--wrapper-name",
        help="Wrapper/executable name under APPLaunch bin. Defaults to binary basename.",
    )
    parser.add_argument("--icon", type=Path, help="Icon file to copy into share/images.")
    parser.add_argument(
        "--icon-ref",
        help="Icon reference to write without copying a file, for example share/images/math.png.",
    )
    parser.add_argument(
        "--icon-summary",
        help="Functional summary used by the automatic icon generator. Defaults to --description or --app-name.",
    )
    parser.add_argument(
        "--auto-icon",
        dest="auto_icon",
        action="store_true",
        default=True,
        help="Generate a function-aware PNG icon when --icon and --icon-ref are omitted. This is the default.",
    )
    parser.add_argument(
        "--no-auto-icon",
        dest="auto_icon",
        action="store_false",
        help="Do not generate an icon when --icon and --icon-ref are omitted.",
    )
    parser.add_argument("--terminal", action="store_true", help="Set Terminal=true.")
    parser.add_argument(
        "--no-sysplause",
        action="store_true",
        help="Set Sysplause=false for Terminal=true entries.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("build/applauncher-packages"),
        help="Output directory that receives the staging tree.",
    )
    parser.add_argument(
        "--maintainer",
        default="Cardputer Zero <dev@example.com>",
        help="Debian Maintainer field.",
    )
    parser.add_argument("--section", default="APPLaunch", help="Debian Section field.")
    parser.add_argument(
        "--homepage", default="https://cardputerzero.github.io", help="Debian Homepage field."
    )
    parser.add_argument(
        "--description",
        help="Debian Description field. Defaults to 'Cardputer Zero <app-name>'.",
    )
    parser.add_argument(
        "--deb",
        action="store_true",
        help="Run dpkg-deb -b after creating the staging tree.",
    )
    parser.add_argument(
        "--install-local",
        action="store_true",
        help="Copy staged files into /usr/share/APPLaunch on this host.",
    )
    parser.add_argument(
        "--auto-install-cardputer",
        action="store_true",
        help="Install locally when this host looks like a Cardputer Zero.",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Do not restart APPLaunch.service after local install.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    package = slug(args.package or args.app_name)

    if bool(args.binary) == bool(args.exec_cmd):
        raise SystemExit("provide exactly one of --binary or --exec")
    if args.icon and args.icon_ref:
        raise SystemExit("provide at most one of --icon or --icon-ref")
    if not args.icon and not args.icon_ref and not args.auto_icon:
        raise SystemExit("missing required icon: provide --icon/--icon-ref or omit --no-auto-icon")

    stage = args.out / f"debian-{package}"
    if stage.exists():
        shutil.rmtree(stage)

    app_root = stage / "usr/share/APPLaunch"
    apps_dir = app_root / "applications"
    bin_dir = app_root / "bin"
    image_dir = app_root / "share/images"
    font_dir = app_root / "share/font"
    lib_dir = app_root / "lib"

    for path in (apps_dir, bin_dir, image_dir, font_dir, lib_dir, stage / "DEBIAN"):
        path.mkdir(parents=True, exist_ok=True)

    if args.binary:
        binary_name = args.wrapper_name or args.binary.name
        dest = bin_dir / binary_name
        copy_executable(args.binary, dest)
        exec_value = f"/usr/share/APPLaunch/bin/{binary_name}"
    else:
        exec_value = args.exec_cmd

    if not args.icon and not args.icon_ref and args.auto_icon:
        generated_icon = args.out / "generated-icons" / f"{package}.png"
        generator = Path(__file__).with_name("generate_app_icon.py")
        summary = args.icon_summary or args.description or args.app_name
        subprocess.run(
            [
                sys.executable,
                str(generator),
                "--app-name",
                args.app_name,
                "--summary",
                summary,
                "--out",
                str(generated_icon),
                "--force",
            ],
            check=True,
        )
        args.icon = generated_icon

    icon_value = args.icon_ref
    if args.icon:
        if not args.icon.is_file():
            raise SystemExit(f"icon not found: {args.icon}")
        icon_dest = image_dir / args.icon.name
        shutil.copy2(args.icon, icon_dest)
        icon_value = f"share/images/{args.icon.name}"

    desktop_lines = [
        "[Desktop Entry]",
        f"Name={args.app_name}",
        f"Exec={exec_value}",
        f"Terminal={desktop_bool(args.terminal)}",
    ]
    if args.terminal and args.no_sysplause:
        desktop_lines.append("Sysplause=false")
    if icon_value:
        desktop_lines.append(f"Icon={icon_value}")
    desktop_lines.append("Type=Application")
    write_text(apps_dir / f"{package}.desktop", "\n".join(desktop_lines) + "\n")

    description = args.description or f"Cardputer Zero {args.app_name}"
    control = "\n".join(
        [
            f"Package: {package}",
            f"Version: {args.version}",
            "Architecture: arm64",
            f"Maintainer: {args.maintainer}",
            f"Section: {args.section}",
            "Priority: optional",
            f"Homepage: {args.homepage}",
            f"Description: {description}",
            "",
        ]
    )
    write_text(stage / "DEBIAN/control", control)

    print(f"staged: {stage}")
    print(f"desktop: {apps_dir / (package + '.desktop')}")

    if args.deb:
        deb_name = f"{package}_{args.version}-{args.revision}_arm64.deb"
        deb_path = args.out / deb_name
        subprocess.run(["dpkg-deb", "-b", str(stage), str(deb_path)], check=True)
        print(f"deb: {deb_path}")

    if args.install_local or (args.auto_install_cardputer and is_cardputer_zero()):
        install_to_applaunch(stage, restart=not args.no_restart)
    elif args.auto_install_cardputer:
        print("auto-install skipped: this host does not look like a Cardputer Zero")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
