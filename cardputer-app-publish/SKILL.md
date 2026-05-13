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

### Prerequisites

- `czdev` CLI installed (build from source or download from Releases)
- `git` and `git-lfs` installed
- A built `.deb` package (via CI workflow or local cross-compile)
- `app-builder.json` with a `"store"` section including screenshots, icon, categories

### 1. Login (one-time)

```bash
czdev login
```

Opens a GitHub Device Flow in your browser. After authorization, a token is stored locally at `~/.config/czdev/token`. This maps your GitHub identity (email) to the deb's `Maintainer` field.

### 2. Publish

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
| `multiple .deb files in build/` | Specify explicitly with `--deb <path>` |
| `app-builder.json missing store section` | Add `"store": { "summary": "...", "categories": [...], "screenshots": [...] }` |
