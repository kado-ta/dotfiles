---
name: code-style
description: Use when writing or reviewing code - applies naming conventions, code quality rules, and style guidelines for this project
---

# Code Style

## Core Rules
- 命名は省略しすぎない。可読性を優先する（`ctx`/`cfg`/`mgr` などの慣習的省略は既存コードに合わせる）。
- 関数/メソッドは単一責務を守る。
- hidden side effects を避ける。
- エラーハンドリングを省略しない。
- 一時しのぎの分岐やフラグ追加は極力避ける。
- マジックナンバーは定数化を検討する。
- 既存 formatter / linter の規約に従う。

## Naming Conventions

| 対象 | ルール | 例 |
|---|---|---|
| boolean | `is_`, `has_`, `can_` または肯定形で意味が明確な名前 | `isAuthenticated`, `hasAdminRole`, `canEdit` |
| enum / state | 略語より完全な語を優先 | `UserAccountStatus` (not `UserStat`) |
| DB カラム / API フィールド | 既存規約に合わせる | `created_at` → `CreatedAt` (Go), `createdAt` (TS) |
