---
status: in-progress
created: 2026-11-24
---

# Vault の点検スクリプトがないときに知らせる 試験記録

関連: [plan.md](plan.md)

<a name="tests"></a>

## 試験の結果

| 実行した場所 | コマンド | 結果 |
| --- | --- | --- |
| Claude Code の sandbox | `bash claude/hooks/tests/test-check-vault-note.sh` | pass=27 fail=0 skip=1（Seatbelt の中の確認はスキップ） |
| ユーザーのターミナル | `CHECK_VAULT_NOTE_SEATBELT_REQUIRED=1 bash claude/hooks/tests/test-check-vault-note.sh` | pass=44 fail=0 skip=0 |
| Claude Code の sandbox | 既存のフックの試験 7 本、`check-repo.py`、`test-check-repo.py`、shellcheck、`actionlint` | すべて通過 |

足した試験（どこでも動く）:

- Vault に点検スクリプトがない → exit 2、`syncUnderscoreItems` を含む文
- Vault の点検スクリプトの場所がディレクトリ → exit 2、同じ文
- Vault に点検スクリプトがなく、Command Line Tools もない → exit 2、`xcode-select --install` を含む文
- 大きな入力を、Vault に点検スクリプトがない場合も読み切る

Vault 以外のプロジェクトで点検スクリプトがない場合（Command Line Tools がない場合も）は、既存の試験のとおり何も出さない。

<a name="mutations"></a>

## 壊した写しでの確認

一時フォルダに写して壊したフックで、試験が失敗することを確かめた（写しはコミットしていない）。

| 壊し方 | 失敗した試験 |
| --- | --- |
| bash で、Vault でも点検スクリプトがなければ何もしない（変更前に戻す） | Vault の 3 件 |
| Python で、通常のファイルかを確かめない | ディレクトリの件（「写しと違う」の文になる） |
| bash で、点検スクリプトがなければ常に Python まで進む | Command Line Tools がないとき、Vault 以外のプロジェクトでも知らせが出る |

確かめていないもの: 通常のファイルかを確かめた後に消える競合（`FileNotFoundError` の分岐）。判定と読み込みのあいだに消す競合でしか届かないため。
