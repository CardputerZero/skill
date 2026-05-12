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

### 前置条件

- 已安装 `czdev` CLI（从源码构建或下载预编译版本）
- 已安装 `git` 和 `git-lfs`
- 已构建好的 `.deb` 包（通过 CI 工作流或本地交叉编译）
- `app-builder.json` 中包含 `"store"` 字段（需填写截图、图标、分类信息）

### 1. 登录（仅需一次）

```bash
czdev login
```

在浏览器中打开 GitHub 设备授权流程。授权完成后，token 保存在 `~/.config/czdev/token`。此步骤将你的 GitHub 身份（邮箱）与 deb 包中的 `Maintainer` 字段关联。

### 2. 发布

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
| `multiple .deb files in build/` | 用 `--deb <路径>` 明确指定 |
| `app-builder.json missing store section` | 添加 `"store": { "summary": "...", "categories": [...], "screenshots": [...] }` |
