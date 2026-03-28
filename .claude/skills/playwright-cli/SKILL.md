---
name: playwright-cli
description: Automates browser interactions for web testing, form filling, screenshots, and flow exploration. Use when the user needs browser-based verification or when an interaction should be turned into Playwright test code.
allowed-tools: Bash(playwright-cli:*)
---

# Browser Automation with playwright-cli

## 基本方針

1. `open` / `goto` で対象ページを開く
2. `snapshot` で要素の ref を確認する
3. `click` / `fill` / `type` / `press` で操作する
4. 必要なら `tracing-start` / `video-start` で証跡を残す
5. 安定したら `@playwright/test` に落として自動化する

## よく使うコマンド

```bash
playwright-cli open https://example.com
playwright-cli snapshot
playwright-cli click e3
playwright-cli fill e5 "user@example.com"
playwright-cli type "hello"
playwright-cli press Enter
playwright-cli screenshot
playwright-cli close
```

## セッション

名前付きセッションを使うとブラウザ状態を分離できる。

```bash
playwright-cli -s=auth open https://example.com/login
playwright-cli -s=auth snapshot
playwright-cli -s=auth close
playwright-cli close-all
```

## デバッグ

```bash
playwright-cli console
playwright-cli network
playwright-cli tracing-start
playwright-cli tracing-stop
playwright-cli video-start
playwright-cli video-stop demo.webm
```

## 実務ルール

- まず `snapshot` を取ってから操作する
- CSS セレクタを決め打ちする前に、生成された role ベースの操作を優先する
- 操作確認だけで終わらせず、再利用価値があるなら Playwright テストに落とす
- アーティファクトを残す場合は `.playwright-cli/` と `playwright-report/` を Git 管理対象外にする
