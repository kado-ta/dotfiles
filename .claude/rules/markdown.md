---
paths:
  - "**/*.md"
---

# Markdown authoring

- GitHub Flavored Markdown を基準とし、GitHub と Typora の両方で正しく表示されること。
- ドキュメント内リンクは `[表示名](#anchor-id)` を使う。Obsidian の Wikilink（`[[...]]`）は使わない。
- 明示的なアンカー ID は英小文字・数字・ハイフンのみとし、文書内で一意にする。
- 日本語や記号を含む見出し、または安定したリンク先が必要な見出しには、直前に `<a name="anchor-id"></a>` を置く。
- 見出し名の重複は避ける。
- 編集後、内部リンクの参照先が存在し、アンカー ID が一意であることを確認する。
