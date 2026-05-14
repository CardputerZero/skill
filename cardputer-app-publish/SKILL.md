---
name: cardputer-app-publish
description: Guide users through publishing CardputerZero apps to the AppStore using czdev CLI. Covers login, publish, PR review, and release lifecycle.
metadata:
  short-description: Publish CardputerZero apps via czdev
---

# CardputerZero App Publishing

## Overview

CardputerZero apps are published to the official AppStore via the `czdev` CLI tool. The canonical reference for the publish workflow is:

- **SSOT (Single Source of Truth):** <https://github.com/m5stack/CardputerZero-AppBuilder>
- **README:** <https://github.com/m5stack/CardputerZero-AppBuilder/blob/main/README.md>

## Publishing Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                  CardputerZero App Publish Flow                      │
└─────────────────────────────────────────────────────────────────────┘

  Developer                        czdev CLI                   GitHub
  ─────────                        ─────────                   ──────
      │                                │                          │
      │  1. czdev login                │                          │
      │───────────────────────────────▶│                          │
      │        (GitHub OAuth)          │ ─── Device Flow ────────▶│
      │                                │◀── token stored locally ─│
      │                                │                          │
      │  2. czdev publish --deb xxx.deb│                          │
      │───────────────────────────────▶│                          │
      │                                │── fork packages repo ───▶│
      │                                │── push branch + deb ────▶│
      │                                │── create PR ────────────▶│
      │                                │                          │
      │  PR URL returned               │                          │
      │◀───────────────────────────────│                          │
      │                                │                          │
      │                                        Admin / Reviewer
      │                                        ────────────────
      │                                              │
      │         3. Review & Merge PR                 │
      │◀─────────────────────────────────────────────│
      │    (automated CI validates .deb)             │
      │                                              │
      │         4. Release pipeline triggers         │
      │              • Updates APT repo index        │
      │              • App appears in AppStore       │
      │                                              │
```

## Step-by-Step Guide

## Development Environment Bootstrap

When this skill is used for build, deploy, or publish work, proactively check the local environment before assuming tools exist:

```bash
command -v czdev || true
command -v git || true
git lfs version || true
command -v cargo || true
command -v cmake || true
command -v pkg-config || true
command -v dpkg-deb || true
pkg-config --modversion sdl2 || true
pkg-config --modversion freetype2 || true
test -f ~/.czdev/credentials -o -f ~/.config/czdev/token && echo czdev-token-present || true
```

If required tools are missing, tell the user exactly what is missing and ask whether they want you to install or bootstrap the environment. Do not install global tools, Homebrew packages, apt packages, Rust, or clone large repositories without user confirmation.

Official AppBuilder desktop-dev setup from the SSOT:

macOS prerequisites:

```bash
brew install cmake pkg-config sdl2 sdl2_image sdl2_mixer freetype git-lfs
```

Debian/Ubuntu prerequisites:

```bash
sudo apt install -y build-essential cmake pkg-config \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libfreetype-dev git-lfs
```

Rust toolchain for `czdev`:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

Build `czdev` from source:

```bash
git clone --recursive git@github.com:m5stack/CardputerZero-AppBuilder.git
cd CardputerZero-AppBuilder
cargo build --release -p czdev
./target/release/czdev doctor
```

If the repo was cloned without submodules:

```bash
git submodule update --init --recursive
```

Alternative: download a prebuilt `czdev` from the AppBuilder GitHub Releases page for the current OS/architecture, then place it somewhere on `PATH`.

During app development, prefer running `czdev doctor` once after install. Its output is the source of truth for missing local dependencies.

### Prerequisites

- `czdev` CLI installed (build from source or download from Releases)
- `git` and `git-lfs` installed
- `dpkg-deb` installed so publish preflight can inspect `.deb` metadata and payload
- A built `.deb` package (via CI workflow or local cross-compile)
- `app-builder.json` with a `"store"` section including screenshots, icon, categories
- A successful mandatory prepublish check with `scripts/prepublish_check.py`

### 1. Login (one-time)

```bash
czdev login
```

Opens a GitHub Device Flow in your browser. After authorization, a token is stored locally at `~/.config/czdev/token`. This maps your GitHub identity (email) to the deb's `Maintainer` field.

### 2. Publish

Before running `czdev publish`, always run the skill's strict prepublish check from the app project root:

```bash
python3 /path/to/cardputer-app-publish/scripts/prepublish_check.py \
  --deb build/my_app_1.0.1_arm64.deb \
  --app-dir .
```

Treat any `ERROR` as a hard blocker. Do not run `czdev publish` until the check passes. The check enforces the critical AppStore information that `czdev` may not fully reject on its own:

- `app-builder.json` exists and has a `store` object.
- `store.summary`, `store.categories`, `store.icon`, and at least one `store.screenshots` entry are present.
- Source icon and screenshots exist and are PNG/JPEG; the icon must be a square PNG.
- The `.deb` has required control fields: `Package`, `Version`, `Architecture=arm64`, and `Maintainer`.
- The `.deb` contains an APPLaunch `.desktop` file with `Name`, `Exec`, and `Icon`.
- The `.desktop` `Icon` resolves to a real square PNG inside the `.deb`.
- The `.desktop` `Exec` target exists inside the `.deb` when it is an absolute or APPLaunch-relative path.

If the source icon is missing and the user is available, ask whether they want you to generate one. If the user explicitly asked to publish now, the session is non-interactive, or the work is running in an automated handoff, run the prepublish check with `--auto-fix-source-icon`, then rebuild the `.deb` through the `cardputer-zero-application` packaging helper and rerun the strict check. Never submit the original `.deb` if the icon is missing from its payload.

```bash
czdev publish --deb build/my_app_1.0.1_arm64.deb
```

This command:
1. **Preflight checks:** validates `.desktop` exists in deb, email matches GitHub account, package name is valid, size < 100 MB, version is newer than existing
2. **Fork & branch:** forks `CardputerZero/packages` (if no write access), creates a `publish/<pkg>-<ver>-<ts>` branch
3. **Upload:** pushes the `.deb` via git-lfs, along with `meta.json`, icon, and screenshots
4. **Create PR:** opens a Pull Request against `CardputerZero/packages` main branch

You'll see a PR URL in the output.

### 3. Review

- Automated CI checks the package structure
- A repository admin reviews the PR
- Once merged, the release pipeline updates the APT repository index

### 4. App goes live

After the PR is merged:
- The package appears in `cardputerzero.github.io/packages`
- Users can install via `sudo apt update && sudo apt install <package>`
- The app appears in the on-device AppStore

## Recommended UX Metadata

For apps with user-facing UI or admin surfaces, recommend i18n support for Simplified Chinese, Japanese, and English. The default language should follow the system language automatically. If the app includes a calendar management admin console, document that users can switch language there and that this manual setting overrides the system language.

### Unpublish

```bash
czdev unpublish my_app --version 1.0.1
```

Removes your own published package version.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `email_mismatch` error | Set your deb `Maintainer` email to match your GitHub account email or noreply address |
| `version_not_newer` | Bump the version in your `app-builder.json` and rebuild |
| `git-lfs not installed` | `brew install git-lfs && git lfs install` (macOS) or `sudo apt install git-lfs` (Linux) |
| `dpkg-deb` missing | macOS: `brew install dpkg`; Debian/Ubuntu: `sudo apt install dpkg` |
| `multiple .deb files in build/` | Specify explicitly with `--deb <path>` |
| `app-builder.json missing store section` | Add `"store": { "summary": "...", "categories": [...], "screenshots": [...] }` |
| `store.icon is required` or icon missing from `.deb` | Generate or provide a square PNG icon, rebuild the `.deb`, rerun `scripts/prepublish_check.py`, then publish |
