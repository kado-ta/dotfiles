# Skill Routing セクションのスキル化 — 設計ドキュメント

**作成日:** 2026-05-27  
**対象ブランチ:** `docs/claude-md-karpathy-discipline`

---

## 概要

`~/.claude/CLAUDE.md` 内の `Skill Routing` セクション（約30行）と  
`.claude/docs/SKILL_ROUTING.md`（詳細フロー・プロンプト例、約300行）を  
`.claude/skills/skill-routing/SKILL.md` として 1 つのスキルファイルに統合・切り出す。

---

## 背景と動機

### 現状の問題

| ファイル | 役割 | 問題 |
|---|---|---|
| `CLAUDE.md` の Skill Routing セクション | シーン判定表・ルーティングルール | 常にコンテキストに存在し、CLAUDE.md が肥大化 |
| `docs/SKILL_ROUTING.md` | 各シーンの詳細フロー・プロンプト例（人間向けリファレンス） | Claude が参照するには手動 Read が必要。スキルでない |

- ルーティングロジックが 2 ファイルに分散し、管理コストが高い
- `SKILL_ROUTING.md` は「人間向けリファレンス」と明記されており、Claude が機械的に活用する仕組みがない
- `code-style` / `superpowers-doc-conventions` 等のカスタムスキルと一貫したパターンになっていない

### 目標

1. ルーティングロジックを単一スキルとして管理する
2. `using-superpowers` の「1% でも関連しそうなら呼べ」ルールに乗って、タスク開始時に自動起動する
3. `CLAUDE.md` をスリム化し、ルーティング詳細を削除する

---

## 設計

### ファイル構成の変更

```
変更前:
  .claude/CLAUDE.md          ← Skill Routing セクション (~30行) を含む
  .claude/docs/SKILL_ROUTING.md  ← 詳細フロー・プロンプト例 (~300行)

変更後:
  .claude/CLAUDE.md          ← Skill Routing セクションが 1 行ポインターに
  .claude/skills/skill-routing/SKILL.md  ← 新規。全内容を統合
  .claude/docs/SKILL_ROUTING.md  ← 削除（スキルに吸収）

自動生成（setup.sh 再実行で作成）:
  ~/.claude/skills/skill-routing  →  .claude/skills/skill-routing
```

---

### skill-routing/SKILL.md の構造

#### frontmatter（呼び出しトリガー）

```markdown
---
name: skill-routing
description: Use when starting any task — determines which skill to invoke
  by detecting the scene type (new feature, bug fix, UI/design, code review,
  deploy, refactor, etc.) and routes to the correct starting skill.
  Also defines when direct answers are allowed without invoking a skill.
---
```

`description` は `using-superpowers` のスキル選択ロジックのインプットになる。
「どのスキルを呼ぶか決める」という責務を description に書くことで、
Claude がすべての非自明タスクの起点でこのスキルを呼ぶ動線を作る。

#### コンテンツ構成

```
1. 直接回答可（スキル起動不要）
   - CLAUDE.md の 3 項目をそのまま移植

2. シーン判定ルール
   - 衝突優先順位: (1) UI/Design > (2) レビュー・デプロイ > (3) 動詞判断
   - 判定不能時のルール

3. シーン判定表
   - 9 シーン × トリガー例・起点スキル・連鎖先

4. 完了後の連鎖提示フォーマット
   - `{起点スキル}` 完了 → 次は **{次のスキル}** を使います。進めてよいですか？

5. 各シーン詳細フロー（SKILL_ROUTING.md から吸収）
   - シーン 1: 新機能開発
   - シーン 2a/2b: バグ修正（非UI / UI/ブラウザ起因）
   - シーン 3: UI/Design 改善
   - シーン 4: PR コードレビュー
   - シーン 5: デプロイ・PR 作成
   - シーン 6: リファクタリング
   - シーン 7a/7b: 振り返り / セキュリティ監査
```

---

### CLAUDE.md の変更

**変更前:**
```markdown
## Skill Routing
ユーザーのリクエストはまずシーンを判定し、該当する起点スキルを呼ぶ。詳細フロー・プロンプト例は `.claude/docs/SKILL_ROUTING.md` を参照。

直接回答可（スキル起動不要）:
- ...（3項目）

### シーン判定ルール
...

### シーン判定表
| ... | ... |（9行）

各シーンで [Codex Offload Rules] を参照し委譲する。...
```

**変更後:**
```markdown
## Skill Routing
`skill-routing` スキルを使用してシーンを判定すること。
```

---

### シンボリックリンク

`setup.sh` の既存ループ（54〜58行目）が `skills/*/` を自動処理する:

```bash
for skill_dir in "${SCRIPT_DIR}/skills"/*/; do
  skill_name=$(basename "${skill_dir}")
  ln -snfv "${skill_dir}" "${CLAUDE_DIR}/skills/${skill_name}"
done
```

`skill-routing/` ディレクトリを追加後、`bash .claude/setup.sh` を実行すれば  
`~/.claude/skills/skill-routing` が自動作成される。

---

## 動作原理

```
タスク開始
  └── using-superpowers: 「関連スキルがあるか確認」
        └── skill-routing の description を確認
              └── "Use when starting any task" → 1% ルール発動
                    └── Skill tool で skill-routing を呼ぶ
                          ├── 直接回答可判定 → そのまま回答
                          └── シーン判定 → 起点スキルを呼ぶ
                                例: brainstorming / systematic-debugging / etc.
```

---

## 成功基準

| チェック項目 | 検証方法 |
|---|---|
| 新機能リクエスト（「〜を作りたい」）で brainstorming が起動される | 手動動作確認 |
| バグ修正リクエストで systematic-debugging が起動される | 手動動作確認 |
| 単純な質問（「この変数の型は？」）でスキルが起動されない | 手動動作確認 |
| `~/.claude/skills/skill-routing` の symlink が作成される | `ls -la ~/.claude/skills/` |
| `docs/SKILL_ROUTING.md` が削除されている | `ls .claude/docs/` |
| CLAUDE.md の Skill Routing セクションが 1 行になっている | ファイル確認 |

---

## 影響範囲

- `~/.claude/CLAUDE.md` — グローバル設定（全プロジェクト共通）
- `~/.claude/skills/skill-routing` — 新規グローバルスキル
- `using-superpowers` の動作フロー — 変更なし（description で自然に組み込まれる）
- `docs/SKILL_ROUTING.md` — 削除（内容はスキルに移植済み）

---

## 非目標（スコープ外）

- `SKILL_ROUTING.md` の内容を書き直す・改善する
- Codex Offload Rules セクションの変更
- 既存スキル（code-style 等）の変更
- CLAUDE.md のその他セクションの変更
