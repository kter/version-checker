---
name: test-implementation
description: Implement unit tests and integration tests for backend and web application features with an emphasis on reliable, isolated coverage.
---

# Test Implementation

## 目的

テストは「緑にするため」ではなく、仕様の重要な分岐を壊れにくく保証するために書く。

## 進め方

### 1. 先に対象を分解する

着手前に以下を整理する。

- 何を保証したいのか
- 既に何がテスト済みか
- 純粋ロジックか、HTTP/API 経由で検証すべきか
- 外部依存を mock すべきか

### 2. Unit と Integration を分ける

Unit test を選ぶケース:

- 分岐や境界値を細かく押さえたい
- 外部 API や DB を本物で使う必要がない
- エラー条件を安価に再現したい

Integration test を選ぶケース:

- ルーティング、依存注入、レスポンス整形まで通したい
- 複数コンポーネントの組み合わせを確認したい
- 実際の API 契約を守れているか見たい

### 3. Unit test の原則

- 成功系と失敗系の両方を書く
- 境界値は `limit - 1`, `limit`, `limit + 1`, `0` を意識する
- 依存は fixture / mock で差し替える
- 例外が仕様なら、例外型とメッセージまたは status code を確認する

### 4. Integration test の原則

- 1 ファイル 1 機能領域を基本にする
- データ作成 fixture には cleanup を持たせる
- `yield` か `try/finally` で後始末を保証する
- 404 / 401 / 403 / 422 など主要エラーパスも確認する

### 5. マルチテナントと認可

ユーザー分離がある機能では以下を必ず見る。

- user A のデータを user B が読めない
- 更新できない
- 削除できない
- 一覧 API に他人のデータが混ざらない

### 6. 完了条件

- テスト名だけで仕様意図が分かる
- fixture が後始末を持つ
- 重要分岐を落としていない
- 変更したコードに対応するテストが追加または更新されている
