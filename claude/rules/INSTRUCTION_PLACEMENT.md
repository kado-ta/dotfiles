# Instruction placement

Claude への指示（CLAUDE.md・rules・skills・subagents・hooks・permissions）を追加・移動・削除するときに適用する。リポジトリの規則（CLAUDE.md・rules・リポジトリの検査）が優先する。

- 必ず守らせたいこと（「〇〇のたびに Y」「〇〇しない」）は、文章ではなく hooks か permissions で強制する。
- CLAUDE.md には、毎回必要な事実（コマンド・構成・規約）だけを置く。
- 特定のファイルにだけ効く規約は、paths 付きの rules にする。paths 付きの rules は一致するファイルを Read・Write・Edit したときに読み込まれるので、どのファイルを触るかを決める前に必要な規則（置き場所の判断など）には paths を付けない。
- 手順は skills に置き、途中経過のいらない調査は subagents に任せる。
- 個人の好みはユーザーレベル（`~/.claude/`）に置き、プロジェクトには書かない。
- 読み込みのタイミング・frontmatter の項目・フックの種類などの仕様は、記事や記憶に頼らず公式ドキュメントで確かめる。記事と食い違うときは公式ドキュメントに従い、食い違いを報告する。

出典: [Steering Claude Code: when to use CLAUDE.md, skills, hooks, and subagents](https://claude.com/ja/resources/articles/steering-claude-code-skills-hooks-rules-subagents-and-more)（2026-06-18）
