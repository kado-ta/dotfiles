# Karpathy 由来のコーディング行動指針を `.claude/CLAUDE.md` に追加

- 日付: 2026-05-22
- 対象ファイル: `/Users/kado/dotfiles/.claude/CLAUDE.md` (=`~/.claude/CLAUDE.md` のシンボリックリンク元)
- 参考: <https://github.com/multica-ai/andrej-karpathy-skills>

## 背景と動機

現状の `.claude/CLAUDE.md` は運用ルール (Safety / Testing / Git / Codex / Skill Routing / gstack) に厚みがある一方、コーディング行動そのものを律する指針は `Working Principles` の 3 行のみ。Andrej Karpathy が指摘する LLM の典型的失敗 — 推測で進める / 過度に複雑化する / 周辺コードを勝手にいじる / 検証不能なゴールで走る — を抑制する明示ルールが薄い。

参考リポジトリの 4 原則を取り込み、これらの失敗モードに対する歯止めをかける。

## 設計判断

| 判断項目 | 採用案 | 理由 |
|---|---|---|
| 取り込み範囲 | Karpathy 原典 4 原則をそのまま新セクションとして追加 | 凝縮より原典への忠実さを優先。後で各原則を運用と摺り合わせやすい。 |
| 配置 | `Working Principles` の直後 | 運用ルールより手前に置き、読み手 (= Claude) が最初に通る場所にする。 |
| 既存重複 | `Working Principles` の「要件が曖昧な場合は推測で確定せず、質問・前提・方針・代替案を提示」を削除 | Karpathy `Think Before Coding` と完全重複するため。 |
| 他セクション | 触らない (Safety / Testing / Git / Codex / Skill Routing / gstack) | `Surgical Changes` 原則そのものを守る。 |
| 言語 | 見出しは英語+日本語併記、本文は日本語訳 | 既存スタイル (`Coding Discipline` 等) と整合。 |
| Tradeoff 注記 | 原典の「caution over speed。trivial task は判断で」も併記 | 4 原則を機械的に適用してオーバーヘッドが出ないよう、エスケープハッチを残す。 |

## 追加するセクション (確定文面)

```markdown
## Coding Discipline

Karpathy の LLM コーディング原則 (<https://github.com/multica-ai/andrej-karpathy-skills>) をベースに、このリポジトリで遵守するコーディング行動を定義する。

**Tradeoff**: これらの指針は速度よりも慎重さに寄せている。trivial なタスクでは判断で省略してよい。

### 1. Think Before Coding (実装前に考える)
**推測しない。迷いを隠さない。トレードオフを明示する。**
- 前提を明示して進める。不確かなら質問する。
- 解釈が複数あるなら、黙って選ばず並べて示す。
- よりシンプルな代替案があれば提示する。必要なら押し返す。
- 不明点があれば手を止め、何が不明か言語化して質問する。

### 2. Simplicity First (シンプルさを優先)
**問題を解く最小限のコード。推測は不要。**
- 依頼されていない機能は作らない。
- 一回しか使わないコードを抽象化しない。
- 要求されていない `flexibility` / `configurability` を追加しない。
- 起こりえないシナリオのエラーハンドリングは不要。
- 200 行で書いたものが 50 行で済むなら書き直す。
- 「Senior engineer が複雑すぎると言うか?」と自問し、Yes なら簡素化する。

### 3. Surgical Changes (外科手術的な変更)
**必要な部分だけに触れる。自分が出したゴミだけ片付ける。**
- 隣接コード・コメント・フォーマットを「改善」しない。
- 壊れていないものをリファクタしない。
- 既存スタイルに合わせる (自分の好みと違っても)。
- 無関係なデッドコードに気づいたら、勝手に消さず報告する。
- 自分の変更で発生した未使用 import / 変数 / 関数のみ除去する。既存のデッドコードは依頼がない限り残す。
- 変更された全行がユーザー依頼に直接トレースできること。

### 4. Goal-Driven Execution (ゴール駆動の実行)
**成功基準を定義し、検証ループを回す。**
- `validation を追加` → `不正入力のテストを書き pass させる`
- `バグ修正` → `再現テストを書いてから修正する`
- `リファクタ` → `前後でテストが pass することを保証`
- マルチステップ作業では `[step → verify: check]` 形式で計画を明示する。
- 「動くようにする」のような曖昧なゴールでは進めず、明確な判定基準を先に定義する。
```

## 既存セクションへの変更

### `Working Principles` (削除のみ)

削除する行:

```
- 要件が曖昧な場合は推測で確定せず、質問・前提・方針・代替案を提示すること。
```

削除後の `Working Principles`:

```markdown
## Working Principles
- 思考は英語で行い、最終的な出力は日本語とする。
  - ユーザーへの確認・質問・結果表示は、必ず日本語を使用すること。
- 仕様が曖昧な場合は既存コード → テスト → ドキュメント → 依頼内容の順で確認する。
```

## 影響範囲

- `/Users/kado/dotfiles/.claude/CLAUDE.md` (1 ファイル)
- `~/.claude/CLAUDE.md` (シンボリックリンク先のため自動反映)
- グローバル設定のため全プロジェクトの Claude Code 起動時に読み込まれる
- プロジェクト固有 CLAUDE.md (例: `/Users/kado/dotfiles/CLAUDE.md`) より優先度は低いため、プロジェクト側ルールがある場合はそちらが勝つ

## 検証

dotfiles リポジトリには自動テストがない。以下を目視確認:

1. `~/.claude/CLAUDE.md` がシンボリックリンクで実体は `/Users/kado/dotfiles/.claude/CLAUDE.md` であること:
   ```sh
   ls -l ~/.claude/CLAUDE.md
   ```
2. Markdown レンダリングが崩れていないこと (見出し階層・コードフェンス・テーブル)
3. 既存セクション (Safety / Testing / Git / Codex / Skill Routing / gstack) が無変更であること:
   ```sh
   git diff main -- .claude/CLAUDE.md
   ```

## やらないこと (Out of Scope)

- 他セクション (Safety, Testing, Git, Codex, Skill Routing, gstack) の改稿
- プロジェクト側 `/Users/kado/dotfiles/CLAUDE.md` の変更
- `.claude/docs/CODEX_OFFLOAD.md` / `SKILL_ROUTING.md` への手入れ
- 新スキルの追加
