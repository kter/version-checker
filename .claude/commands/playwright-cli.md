---
description: Automates browser interactions for web testing, form filling, screenshots, and data extraction
allowed-tools: Bash
---

# playwright-cli

Playwright CLI を使ったブラウザ自動化ツール。

## ワークフロー

1. `open` と `snapshot` で画面状態を確認する
2. `click` / `fill` / `type` で必要な操作を再現する
3. `@playwright/test` に落として `npx playwright test --headed` で検証する

## Core Commands

```bash
playwright-cli open <url>
playwright-cli snapshot
playwright-cli click <ref>
playwright-cli fill <ref> <text>
playwright-cli type <text>
playwright-cli screenshot [ref]
playwright-cli close
```

## Sessions

```bash
playwright-cli --session=<name> open <url>
playwright-cli close-all
```

## DevTools

```bash
playwright-cli tracing-start
playwright-cli tracing-stop
playwright-cli console [min-level]
```

`.playwright-cli/` と `playwright-report/` は `.gitignore` に追加しておくこと。
