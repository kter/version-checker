---
name: create-pr
description: Handles the complete git workflow for code changes: inspect the diff, create or reuse a feature branch, stage only relevant files, commit intentionally, push, create a pull request, and ask the user to review.
---

# Create PR Workflow

このスキルは、変更の把握から PR 作成までの Git ワークフローを一貫して扱う。

## いつ使うか

- ユーザーが「commit」「push」「PR を作成」「プルリクを作って」などを依頼したとき
- 実装が一段落し、変更を公開可能な単位にまとめるとき

## 手順

### 1. 変更を理解する

以下を並列に確認する。

```bash
git status
git diff
git log --oneline -5
```

確認ポイント:

- 何のための変更か
- 既に feature branch 上か
- `.env` や認証情報など、ステージしてはいけないものが混ざっていないか

変更がなければそこで終了する。

### 2. ブランチを作る

未作成なら、内容に沿った短い kebab-case のブランチ名を作る。

- `feature/...`
- `fix/...`
- `refactor/...`
- `chore/...`
- `docs/...`

```bash
git checkout -b <branch-name>
```

### 3. ステージしてコミットする

関連ファイルだけを明示的に `git add` する。`git add .` や `git add -A` は使わない。

```bash
git add <file1> <file2> ...
git commit
```

ルール:

- `--no-verify` は使わない
- フックが失敗したら原因を修正して再実行する
- シークレットや無関係な変更は含めない

### 4. Push する

```bash
git push -u origin <branch-name>
```

失敗したら force push は避け、原因を確認する。

### 5. PR を作る

`gh pr create` か同等の手段で PR を作成する。

PR 本文には最低限以下を含める:

- 概要
- 変更内容
- テスト方法
- レビュー観点

### 6. ユーザーに報告する

- PR URL
- ブランチ名
- コミット要約

を短く共有し、レビュー依頼を出す。
