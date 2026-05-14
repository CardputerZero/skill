# Cardputer Zero APPLaunch Contract

This reference summarizes the local APPLaunch behavior observed from:

- the APPLaunch application packaging guide in `M5CardputerZero-Pulse/doc/`
- `M5CardputerZero-UserDemo/projects/APPLaunch/main/ui/components/ui_app_launch.cpp`
- `M5CardputerZero-UserDemo/projects/APPLaunch/main/hal/linux/hal_paths_linux.c`
- `M5CardputerZero-UserDemo/projects/APPLaunch/main/hal/sdl/hal_paths_sdl.c`
- `M5CardputerZero-*/projects/*/SConstruct`
- `M5CardputerZero-*/projects/*/main/src/main.cpp`

## Contents

- [Discovery](#discovery)
- [Desktop File Fields](#desktop-file-fields)
- [Exec Resolution](#exec-resolution)
- [Icon Resolution](#icon-resolution)
- [Debian Package Layout](#debian-package-layout)
- [On-Device Installation Rule](#on-device-installation-rule)
- [Build Modes](#build-modes)
- [Runtime Requirements For GUI Apps](#runtime-requirements-for-gui-apps)
- [Troubleshooting](#troubleshooting)

## Discovery

APPLaunch discovers dynamic apps by scanning:

```text
/usr/share/APPLaunch/applications/*.desktop
```

On SDL/local builds, the applications directory resolves to `<APPLaunch executable dir>/applications`.

The current source also starts an inotify watcher and polls it every 3 seconds, but a service restart is still the most reliable deployment step:

```bash
sudo systemctl restart APPLaunch.service
```

## Desktop File Fields

Default app policy:

- Every Cardputer APPLaunch app should be a real 320 x 170 LVGL GUI app with `Terminal=false` by default.
- Use `Terminal=true` only when the user explicitly asks for CLI, terminal, or text-only behavior.
- Do not implement ASCII/terminal apps unless the user explicitly asks for that interface.

Required for generated APPLaunch apps:

- `Name`: display name in the launcher carousel.
- `Exec`: command or executable path.
- `Icon`: app-specific PNG logo path. Use `Icon=share/images/<slug>.png`.

Optional:

- `Terminal`: `true`, `True`, or `1` means run inside APPLaunch console. Default false.
- `Sysplause`: `true`, `True`, or `1` means wait for a key after terminal command exits. Default true. Only relevant with `Terminal=true`.
- `Type`: normally `Application`; APPLaunch does not enforce it.
- `TryExec`: documentation only; APPLaunch does not parse it.

Parser details:

- The section header must be exactly `[Desktop Entry]`.
- Key and value are trimmed for space and tab.
- Empty lines and lines beginning with `#` or `;` are ignored.
- Unknown fields are ignored.
- Entries missing `Name` or `Exec` are skipped.
- Entries with an `Exec` value already in the launcher list are skipped.
- APPLaunch can technically load entries without `Icon`, but VibAPP-generated apps must include one so the launcher is customer-ready.

## Exec Resolution

APPLaunch resolves `Exec` before launching:

- Empty or absolute paths are used as-is.
- If the first token has no slash, it is used as a PATH command, for example `python3` or `bash`.
- If the first token has a slash and is relative, it is resolved under `/usr/share/APPLaunch`, for example `bin/run-myapp`.

Launch behavior:

- `Terminal=false`: APPLaunch forks and calls `execlp(resolved_exec, resolved_exec, NULL)`. It does not split arguments and does not run through a shell. Use a wrapper script for args, env vars, `cd`, platform switching, or complex launch logic.
- `Terminal=true`: APPLaunch opens a PTY console. The command string is split on whitespace into executable plus args. It does not implement shell quoting. Use a wrapper script for quoted args, redirection, pipes, env vars, or working-directory changes.

Wrapper pattern:

```sh
#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$APP_DIR"
exec "$APP_DIR/M5CardputerZero-MyApp-linux-aarch64" "$@"
```

Then use:

```ini
Exec=bin/run-myapp
Terminal=false
```

## Icon Resolution

Icon resolution:

- Empty stays empty.
- Absolute path becomes an LVGL path like `A:/absolute/path.png`.
- Relative path becomes `A:/usr/share/APPLaunch/<relative>`.
- For generated apps, do not leave it empty. Create a real PNG under `share/images`.
- If the app does not already provide an icon, generate one from the app name and functional summary before staging. The bundled packaging helper does this automatically unless `--no-auto-icon` is set.
- During interactive development, ask the user before generating a replacement icon when the choice affects branding. In non-interactive packaging, automated handoff, or direct publish/submit flows, generate the missing required icon automatically and rerun package validation.

Prefer:

```ini
Icon=share/images/myapp.png
```

which maps to:

```text
/usr/share/APPLaunch/share/images/myapp.png
```

## Debian Package Layout

Recommended app package staging:

```text
debian-myapp/
├── DEBIAN/
│   └── control
└── usr/
    └── share/
        └── APPLaunch/
            ├── applications/
            │   └── myapp.desktop
            ├── bin/
            │   ├── run-myapp
            │   └── M5CardputerZero-MyApp-linux-aarch64
            ├── share/
            │   ├── font/
            │   └── images/
            │       └── myapp.png
            └── lib/
```

Package command:

```bash
dpkg-deb -b debian-myapp myapp_0.1-m5stack1_arm64.deb
```

Control file minimum:

```text
Package: myapp
Version: 0.1
Architecture: arm64
Maintainer: Your Name <you@example.com>
Section: APPLaunch
Priority: optional
Homepage: https://cardputerzero.github.io
Description: Cardputer Zero MyApp
```

Use lowercase package names with no spaces. Architecture is `arm64`.

## On-Device Installation Rule

When the current host is the Cardputer Zero device, install the final app into APPLaunch paths before considering the task complete:

```text
/usr/share/APPLaunch/applications/<app>.desktop
/usr/share/APPLaunch/bin/<wrapper-or-binary>
/usr/share/APPLaunch/share/images/<icon>.png
```

Do not leave customer-visible work only in:

- `projects/*/dist`
- `/home/pi`
- a temporary Debian staging directory
- a copied binary without a matching `.desktop` entry

After copying files, ensure executable permissions on wrappers/binaries:

```bash
sudo chmod 755 /usr/share/APPLaunch/bin/<wrapper-or-binary>
```

Then make APPLaunch reload the entry:

```bash
sudo systemctl restart APPLaunch.service
```

If systemd is unavailable, restart the APPLaunch process or reboot the device. The acceptance check is customer-visible: the app entry appears in APPLaunch with the intended name and icon, and selecting it starts the app.

When work is triggered through VibAPP, remember that APPLaunch starts VibAPP as `root`. Root-owned runtime paths are the source of truth for generated jobs:

```text
/root/.config/opencode/opencode.json
/root/.config/opencode/skills
/root/.local/share/vibapp/jobs
/root/.local/share/vibapp/workspace
```

If a tool works manually as `pi` but fails inside VibAPP, check root's opencode config and root's installed skills before debugging the app itself.

Do not report success only because the model command exited with code 0. A generated job is complete only when `result.json`, `.desktop`, executable, and icon files all exist and resolve through the APPLaunch rules above.

The packaging helper supports this:

```bash
python3 scripts/make_applauncher_package.py \
  --app-name MyApp \
  --binary projects/MyApp/dist/M5CardputerZero-MyApp \
  --description "Calendar with online ICS sync and lunar details" \
  --auto-install-cardputer
```

Pass `--icon assets/myapp.png` to use a project-provided icon instead of the automatic generator.

Do not use `--no-auto-icon` unless `--icon` or `--icon-ref` is also provided. A generated APPLaunch package must not leave the `.desktop` `Icon` field empty.

Use `--install-local` when auto-detection does not recognize the device but `/usr/share/APPLaunch` is the intended target.

## Build Modes

Local SDL debug:

```text
CONFIG_V9_5_LV_USE_SDL=y
```

Device framebuffer build:

```text
CONFIG_V9_5_LV_USE_LINUX_FBDEV=y
CONFIG_V9_5_LV_USE_EVDEV=y
CONFIG_V9_5_LV_DRAW_SW_ASM_NEON=y
CONFIG_V9_5_LV_USE_DRAW_SW_ASM=1
CONFIG_TOOLCHAIN_PREFIX="aarch64-linux-gnu-"
```

Some projects also use:

```text
CONFIG_TOOLCHAIN_SYSROOT="<project>/static_lib"
```

When switching modes, remove stale `build/config/config_tmp.mk` or run `scons distclean`; many templates only write config when that file does not exist.

## Runtime Requirements For GUI Apps

Display:

- Target 320 x 170.
- Use Linux fbdev on device.
- Respect `LV_LINUX_FBDEV_DEVICE` if set.
- Otherwise scan `/proc/fb` for `fb_st7789v` and select `/dev/fbN`.
- Do not assume `/dev/fb0`: the Cardputer Zero ST7789V LCD is commonly `/dev/fb1`; `/dev/fb0` may be HDMI or another framebuffer. Patch or wrap apps such as LoFiBox if they open `/dev/fb0` internally.

Input:

- Default keyboard device: `/dev/input/by-path/platform-3f804000.i2c-event`.
- Keymap path used by custom queue examples: `/usr/share/keymaps/tca8418_keypad_m5stack_keymap.map`.
- Basic apps can use LVGL evdev directly.
- Text-heavy apps should reuse the local `keyboard_input.c` pattern that carries key code, state, symbol name, UTF-8, and codepoint.

Lifecycle:

- APPLaunch pauses its UI while a `Terminal=false` child is running, then reloads the home screen after child exit.
- Long Home press can cause APPLaunch to send `SIGINT`, then `SIGKILL` if the child does not exit.
- Apps should handle a normal in-app back/escape action and, when feasible, `SIGINT`.
- Long-running GUI apps should not require terminal mode.

## Troubleshooting

App does not appear:

- Check filename ends with `.desktop`.
- Check exact `[Desktop Entry]`.
- Check `Name`, `Exec`, and `Icon` are non-empty.
- Check duplicate `Exec` is not already registered by a fixed or dynamic entry.
- Confirm the icon file resolves under `/usr/share/APPLaunch/share/images`.
- Restart APPLaunch and watch logs: `sudo journalctl -u APPLaunch.service -f`.

Launch fails:

- For `Terminal=false`, remove args from `Exec` and use a wrapper script.
- Confirm executable bit: `chmod 755 /usr/share/APPLaunch/bin/run-myapp`.
- Confirm binary architecture: `file /usr/share/APPLaunch/bin/M5CardputerZero-MyApp-linux-aarch64`.
- Confirm dynamic libraries are present on the device.

Icon missing:

- Use `Icon=share/images/myapp.png`.
- Confirm the file exists under `/usr/share/APPLaunch/share/images`.
- Prefer PNG assets sized for the carousel rather than large source images.
- If no project icon exists, run `scripts/generate_app_icon.py` or package again without `--no-auto-icon` so the helper creates a function-aware PNG.

Framebuffer blank or wrong:

- Confirm the app was built for fbdev, not SDL.
- Confirm `/proc/fb` includes `fb_st7789v`.
- Identify the ST7789V node with `awk '/fb_st7789v/ {print "/dev/fb" $1}' /proc/fb`; try `LV_LINUX_FBDEV_DEVICE=/dev/fb1 /usr/share/APPLaunch/bin/run-myapp` only after confirming that node.
- If the app still paints the wrong display, check whether it opens `/dev/fb0` internally and patch or wrap that behavior.

Keyboard missing:

- Confirm the device path exists.
- If direct evdev does not provide characters, use the custom `keyboard_input.c` queue pattern with keymap.
- Attach the LVGL keypad indev to the relevant group/screen after UI init.
