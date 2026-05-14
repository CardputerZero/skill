---
name: cardputer-app-publish
description: 指导用户通过 czdev CLI 将 CardputerZero 应用发布到 AppStore。涵盖登录、发布、PR 审核及上架全流程。
metadata:
  short-description: 通过 czdev 发布 CardputerZero 应用
---

# CardputerZero 应用发布

## 概述

CardputerZero 应用通过 `czdev` 命令行工具发布到官方 AppStore。权威参考文档：

- **唯一信息源 (SSOT)：** <https://github.com/m5stack/CardputerZero-AppBuilder>
- **README：** <https://github.com/m5stack/CardputerZero-AppBuilder/blob/main/README.md>

## 发布流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                CardputerZero 应用发布流程                             │
└─────────────────────────────────────────────────────────────────────┘

  开发者                            czdev CLI                   GitHub
  ──────                            ─────────                   ──────
      │                                │                          │
      │  1. czdev login                │                          │
      │───────────────────────────────▶│                          │
      │     (GitHub OAuth 设备授权)     │ ─── Device Flow ────────▶│
      │                                │◀── token 存储到本地 ─────│
      │                                │                          │
      │  2. czdev publish --deb xxx.deb│                          │
      │───────────────────────────────▶│                          │
      │                                │── fork packages 仓库 ───▶│
      │                                │── push 分支 + deb ──────▶│
      │                                │── 创建 PR ─────────────▶│
      │                                │                          │
      │  返回 PR 链接                   │                          │
      │◀───────────────────────────────│                          │
      │                                │                          │
      │                                        管理员 / 审核者
      │                                        ───────────────
      │                                              │
      │         3. 审核并合并 PR                      │
      │◀─────────────────────────────────────────────│
      │    (CI 自动验证 .deb 包)                      │
      │                                              │
      │         4. 发布流水线触发                      │
      │              • 更新 APT 仓库索引              │
      │              • 应用上架 AppStore              │
      │                                              │
```

## 详细步骤

## 开发环境初始化

当使用本 skill 进行构建、部署或发布时，先主动检查本地环境，不要默认工具已经安装：

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

如果缺少必要工具，明确告诉用户缺了什么，并询问是否需要你帮助安装或初始化环境。不要在未确认的情况下安装全局工具、Homebrew 包、apt 包、Rust，或 clone 大型仓库。

官方 AppBuilder 桌面开发环境安装命令如下。

macOS 前置依赖：

```bash
brew install cmake pkg-config sdl2 sdl2_image sdl2_mixer freetype git-lfs
```

Debian/Ubuntu 前置依赖：

```bash
sudo apt install -y build-essential cmake pkg-config \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libfreetype-dev git-lfs
```

`czdev` 需要 Rust 工具链：

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

从源码构建 `czdev`：

```bash
git clone --recursive git@github.com:m5stack/CardputerZero-AppBuilder.git
cd CardputerZero-AppBuilder
cargo build --release -p czdev
./target/release/czdev doctor
```

如果仓库 clone 时没有带 submodule：

```bash
git submodule update --init --recursive
```

也可以从 AppBuilder GitHub Releases 下载当前系统/架构对应的预编译 `czdev`，并放到 `PATH` 里。

开发应用时，安装后优先跑一次 `czdev doctor`。本地依赖缺失以 `czdev doctor` 输出为准。

### 前置条件

- 已安装 `czdev` CLI（从源码构建或下载预编译版本）
- 已安装 `git` 和 `git-lfs`
- 已安装 `dpkg-deb`，用于发布前检查 `.deb` 元数据和包内容
- 已构建好的 `.deb` 包（通过 CI 工作流或本地交叉编译）
- `app-builder.json` 中包含 `"store"` 字段（需填写截图、图标、分类信息）
- 已通过 `scripts/prepublish_check.py` 的强制发布前检查

### 1. 登录（仅需一次）

```bash
czdev login
```

在浏览器中打开 GitHub 设备授权流程。授权完成后，token 保存在 `~/.config/czdev/token`。此步骤将你的 GitHub 身份（邮箱）与 deb 包中的 `Maintainer` 字段关联。

### 2. 发布

运行 `czdev publish` 前，必须在应用项目根目录先执行本 skill 的严格发布前检查：

```bash
python3 /path/to/cardputer-app-publish/scripts/prepublish_check.py \
  --deb build/my_app_1.0.1_arm64.deb \
  --app-dir .
```

任何 `ERROR` 都是硬阻塞；检查未通过时不要执行 `czdev publish`。该检查会强制验证 `czdev` 可能不会完整拦截的 AppStore 关键信息：

- `app-builder.json` 存在，且包含 `store` 对象。
- `store.summary`、`store.categories`、`store.icon`、至少一个 `store.screenshots` 都已填写。
- 源码中的图标和截图文件存在，格式为 PNG/JPEG；图标必须是正方形 PNG。
- `.deb` control 字段包含 `Package`、`Version`、`Architecture=arm64`、`Maintainer`。
- `.deb` 包含 APPLaunch `.desktop` 文件，且有 `Name`、`Exec`、`Icon`。
- `.desktop` 的 `Icon` 能解析到 `.deb` 内真实存在的正方形 PNG。
- `.desktop` 的 `Exec` 如果是绝对路径或 APPLaunch 相对路径，目标必须存在于 `.deb` 内。

如果源码图标缺失且用户在线，先询问是否需要帮助生成。如果用户明确要求现在提交、当前是无交互流程，或任务已经进入自动化 handoff，则用 `--auto-fix-source-icon` 运行发布前检查，然后通过 `cardputer-zero-application` 的打包 helper 重新构建 `.deb`，再重新执行严格检查。不要提交原始 `.deb`，如果它的包内容里缺少图标。

```bash
czdev publish --deb build/my_app_1.0.1_arm64.deb
```

该命令执行以下操作：
1. **预检查：** 验证 deb 中包含 `.desktop` 文件、邮箱与 GitHub 账号匹配、包名合法、体积 < 100 MB、版本号比已发布版本更新
2. **Fork 并创建分支：** fork `CardputerZero/packages` 仓库（若无写入权限），创建 `publish/<包名>-<版本>-<时间戳>` 分支
3. **上传：** 通过 git-lfs 推送 `.deb` 文件，同时包含 `meta.json`、图标和截图
4. **创建 PR：** 向 `CardputerZero/packages` 的 main 分支发起 Pull Request

命令执行完成后会输出 PR 链接。

### 3. 审核

- CI 自动检查包结构
- 仓库管理员审核 PR
- 合并后，发布流水线自动更新 APT 仓库索引

### 4. 应用上架

PR 合并后：
- 包出现在 `cardputerzero.github.io/packages`
- 用户可通过 `sudo apt update && sudo apt install <包名>` 安装
- 应用出现在设备端 AppStore 中

### 下架

```bash
czdev unpublish my_app --version 1.0.1
```

移除你自己发布的包版本。

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| `email_mismatch` 错误 | 将 deb 的 `Maintainer` 邮箱设置为你的 GitHub 账号邮箱或 noreply 地址 |
| `version_not_newer` | 在 `app-builder.json` 中升级版本号并重新构建 |
| `git-lfs not installed` | macOS: `brew install git-lfs && git lfs install`；Linux: `sudo apt install git-lfs` |
| 缺少 `dpkg-deb` | macOS: `brew install dpkg`；Debian/Ubuntu: `sudo apt install dpkg` |
| `multiple .deb files in build/` | 用 `--deb <路径>` 明确指定 |
| `app-builder.json missing store section` | 添加 `"store": { "summary": "...", "categories": [...], "screenshots": [...] }` |
| `store.icon is required` 或 `.deb` 内缺少 icon | 生成或提供正方形 PNG 图标，重新打 `.deb`，重新跑 `scripts/prepublish_check.py` 后再发布 |
