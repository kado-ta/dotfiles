---
name: superpowers-doc-conventions
description: Use when superpowers generates documents (Plan, Design, etc.) - provides required directory structure and file naming conventions
---

# superpowers Doc Conventions

## Directory Structure

```
docs/
  YYYYMMDD_<name>/         ← 日付プレフィックス必須（例: 20260415_skill_routing）
    [plan]_<name>.md       ← ファイル種別プレフィックス必須
    [design]_<name>.md
```

## Rules

- 保存先: プロジェクトルートの `docs/` ディレクトリ
- ディレクトリ名: `YYYYMMDD_<名前>` 形式（日付は今日の日付を `YYYYMMDD` で付与）
- ファイル名: `[<種別>]_<名前>.md` 形式
  - 種別は `plan` / `design` など文書の種類を英語で
  - 単語の区切りはアンダースコア（スネークケース）

## Quick Reference

| 文書種別 | ファイル名例                      |
|--------|---------------------------------|
| Plan   | `[plan]_user_authentication.md` |
| Design | `[design]_skill_routing.md`     |
| 複数文書 | 同一ディレクトリ内に並列配置         |

## Example

機能「user authentication」の設計・計画ドキュメントを作成する場合:

```
docs/
  20260415_user_authentication/
    [plan]_user_authentication.md
    [design]_user_authentication.md
```
