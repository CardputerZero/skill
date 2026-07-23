# Application Store Web Publishing

Use this reference when preparing or submitting a CardputerZero `.deb` through
<https://dev.cardputer.cc/#/upload>. The form behavior below was verified
against the live page on 2026-07-24.

## Submission Flow

1. Sign in with GitHub on the developer portal.
2. Select or drop the `.deb`. The page parses it locally before upload.
3. Resolve every blocking item in the preliminary report.
4. Fill or confirm the listing fields recorded in the app project's
   `PUBLISH.md`.
5. Review package ownership, version, privacy, icon, and screenshots.
6. Submit only after the user explicitly approves the external action.
7. Record the returned message, Actions URL, tracking URL, or pull-request URL
   in `PUBLISH.md`.

Do not bypass the visible portal by manually posting to its API. Let the portal
manage the authenticated GitHub session, validation feedback, and submission
result.

## Form Fields

| Portal value | Required | Source and behavior |
|---|---:|---|
| GitHub login | Yes | Required before submission. The first uploader owns a new package name; later updates require the owner or an administrator. |
| `.deb` file (`deb`) | Yes | User-selected Debian package. It is parsed locally before upload. |
| Package (`package`) | Automatic | Read from the `.deb` control `Package` field. |
| Version (`version`) | Automatic | Read from the `.deb` control `Version` field. An existing package requires a version newer than the latest published version. |
| Architecture (`arch`) | Automatic | Read from the `.deb` control `Architecture` field. The portal accepts `arm64` or `all`; native CardputerZero binaries should use `arm64`. |
| Source repository (`source_repo`) | No | Public repository URL. When it contains an `app-builder.json` `store` section, the portal can import listing metadata and screenshots. |
| Hide email (`hide_email`) | Yes | Boolean submitted by the page; defaults to `true`. When enabled, publication uses a GitHub noreply identity instead of exposing the verified GitHub email. |
| Application name (`title`) | No | Listing override. Otherwise the portal falls back to source metadata, `.desktop` `Name`, or package data. |
| One-line summary (`summary`) | No | Listing override, maximum 80 characters. |
| Description (`description`) | No | Multiline listing description. |
| Categories (`categories`) | No | Comma-separated values, maximum six categories. |
| Icon override (`icon`) | No | PNG, JPEG, or WebP input. The page center-crops it to a square and uploads a 128 x 128 PNG. Leave empty to use the `.deb` icon. This portal normalization does not replace the project's 256 x 256 source-icon requirement. |
| Screenshots (`screenshots`) | No | Repeated PNG, JPEG, or WebP inputs, up to six. The page center-crops each image to exactly 320 x 170 PNG. Keep the skill's four clean, distinct baseline screenshots ready unless current publication policy explicitly asks for a different count. |

Empty listing overrides and absent images cause the service to fall back to
`source_repo` or metadata derived from the `.deb`. Still record deliberate
listing copy and asset paths in `PUBLISH.md` so the submission is reviewable.

## Browser-Side Blocking Checks

The current page blocks submission when the developer is not logged in, the
package name belongs to another GitHub user, the version is not newer, or the
local `.deb` report contains a `danger` result. Its preliminary parser checks:

- Control fields `Package`, `Version`, `Architecture`, and `Maintainer`.
- A valid lowercase Debian package name.
- `Architecture` equal to `arm64` or `all`.
- An APPLaunch file under
  `usr/share/APPLaunch/applications/*.desktop`.
- A non-empty `.desktop` `Exec`; a missing `Name` is reported as a warning.
- Whether the declared icon resolves inside the package and is PNG.
- Suspicious paths, device files, setuid files, non-arm64 ELF files,
  maintainer scripts, and other package-safety indicators.

The service may apply additional server-side checks after upload. Treat portal
feedback as authoritative and update `PUBLISH.md` when the submitted values or
assets change.

## Required Interaction After Local Cross-Compile

After a local development machine successfully cross-compiles the app and
creates its `.deb`:

1. Parse the package control fields and update the app-root `PUBLISH.md`.
2. Confirm the recorded icon and screenshot paths exist.
3. Show the user the `.deb` path and any unresolved TODO fields.
4. Ask whether they want the agent to open the web portal and submit using the
   record.
5. Stop before login or submission unless the user says yes.
