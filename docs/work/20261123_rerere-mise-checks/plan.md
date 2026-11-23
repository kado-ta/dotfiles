---
status: in-progress
created: 2026-11-23
---

# git の rerere を止め、mise の信頼の経路を check-repo.py で確かめる

中止した cc-checkout-guard の作業（`bb73bb8`。push していない）から、ガードがなくても独立して効く守りだけを入れる。範囲は rerere と mise の 2 つ（2026-11-23、人間の判断）。

関連: [Issue #75](https://github.com/kado-ta/dotfiles/issues/75)（design の非目標「前の作業の小さな項目」）、[docs/work/20261116_sandbox-path-gaps/design.md](../20261116_sandbox-path-gaps/design.md)（paranoid の経緯）

<a name="goal"></a>

## 目的

- **rerere:** sandbox は `.git/rr-cache` と `.git/MERGE_RR` に書ける。rerere が動くと、sandbox の外の git（人間のターミナルと `!`）が、そこに置かれた解決を任意のパス（作業ツリーの外も）に書く。`rerere.enabled` を設定していなくても、`rr-cache` があれば動く。そのため、グローバルの設定で明示的に false にし、`check-repo.py` で外れないようにする。
- **mise:** paranoid（`config`・`env_files`）の守りを、設定と環境変数で迂回させない。
  - `settings.trusted_config_paths` は、空のリストでも、パスで信頼する経路を開く。
  - 環境変数 `MISE_TRUSTED_CONFIG_PATHS`・`MISE_PARANOID` で、信頼するパスや paranoid を上書きさせない。

<a name="non-goals"></a>

## 入れないもの

- ガードの部分（`check_checkout_guard` のほかの部分、`CHECKOUT_GUARD`・`ZSHRC_BLOCK`・`GUARD_REQUIRED_*`・`MISE_LOCK_DENY`、`WorktreeCreate` フック、`bin/.zshrc` の関数）。
- `Edit(**/mise.lock)` の deny（#75 の design の判断）。Edit の deny は sandbox の denyWrite にもなるので、`mise.lock` を変える switch がクローンの中で途中で止まる。
- `Edit(/etc/**)` の整理と、`claude/README.md` の「sandbox 内の gh」の節の書き分け（別の候補）。

<a name="changes"></a>

## 変えるもの

| ファイル | 変更 |
| --- | --- |
| `bin/.gitconfig` | `[rerere] enabled = false` を、理由のコメントと一緒にファイルの最後に足す |
| `.github/scripts/check-repo.py` | 検査 `rerere` を足す。`mise-paranoid` に、`trusted_config_paths` と環境変数の検査を足す |
| `.github/scripts/test-check-repo.py` | 上の検査のテストを `bb73bb8` から持ってくる（ガードのテストは除く） |
| `CLAUDE.md` | 「sandbox と権限の禁止事項」に 2 項目を足す |
| `.claude/rules/CLAUDE_CONFIG.md` | rerere の節を足す。「Edit・Write ツールの書き込み」の mise の項目に、検査の理由を足す |
| `docs/work/20261123_rerere-mise-checks/` | この plan と test-report |

<a name="check-design"></a>

### 検査の中身

- **`rerere`（新しい検査）:** `git config --file bin/.gitconfig --type=bool --get rerere.enabled` の出力が `false` でなければ失敗する。`bb73bb8` では `check_checkout_guard` の中にあったものを、独立した関数にする。
  - git と同じく読むので、最後の値が勝ち、`no`・`0`・大文字小文字の違いも false として通る。
  - ファイルやキーがない（終了コード 1）、bool でない（128）、値のないキー（true）は失敗する。
  - include の先（`~/.gitconfig_numm`）とリポジトリの `.git/config` は見ない。
- **`mise-paranoid`（既存の検査に足す）:**
  - `mise/mise_config.toml` の `settings` に `trusted_config_paths` があれば、値によらず失敗する。
  - `bin/.zshrc`・`bin/.zprofile`・`mise/mise_config.toml`・`zsh/*.zsh` の本文に `MISE_TRUSTED_CONFIG_PATHS`・`MISE_PARANOID` が含まれれば失敗する。コメントの中も失敗にする（文字列の一致だけで判定し、単純に保つ）。

<a name="claude-decisions"></a>

## Claude の判断（承認のときに確かめる）

- **`[rerere]` をファイルの最後に置く。** `bb73bb8` は `[merge]` の後に置いていた。git の include は書いた位置で読み込まれ、後の値が勝つ。`[includeIf "gitdir:~/Dev/numm/"]` より前に置くと、include の先で `rerere.enabled = true` と書いたときに、そのリポジトリでだけ黙って効かなくなる。最後に置けば、`~/.gitconfig` の中では上書きされない（リポジトリの `.git/config` と `git -c` は上書きできる。前者は sandbox が既定で書き込みを止めている）。
- **環境変数の検査に、paranoid の土台を動かすほかの変数を足さない。** 推測だが、mise には、グローバルの設定の場所や信頼の記録の場所を変える環境変数（`MISE_GLOBAL_CONFIG_FILE`・`MISE_CONFIG_DIR`・`MISE_STATE_DIR` など）がある見込み。設定されると、paranoid が効かない設定や、sandbox から書ける信頼の記録を読む恐れがある。名前と効き方を mise の文書で確かめていないので、この PR には入れず、後続の候補にする。
- **新しい検査の名前は `rerere` にする。** `CLAUDE.md` の禁止事項は、失敗する検査の名前を書くので、それと合わせる。

<a name="steps"></a>

## 手順

1. **テストを先に書く:** `.github/scripts/test-check-repo.py` に rerere と mise のテストを足し、セットアップで `bin/.gitconfig` を書く。
   - 確認: `python3 -B .github/scripts/test-check-repo.py` で、新しいテストだけが失敗する。
2. **検査を実装する:** `.github/scripts/check-repo.py`。
   - 確認: `python3 -B .github/scripts/test-check-repo.py` がすべて通る。`python3 -B .github/scripts/check-repo.py` が、`rerere` でだけ失敗する（`bin/.gitconfig` をまだ変えていないため）。
3. **`bin/.gitconfig` を変える。**
   - 確認: `python3 -B .github/scripts/check-repo.py` が通る。`git config --file bin/.gitconfig --type=bool --get rerere.enabled` が `false` を出す。
4. **文書を変える:** `CLAUDE.md`・`.claude/rules/CLAUDE_CONFIG.md`。
   - 確認: `python3 -B .github/scripts/check-repo.py`（リンクとアンカー）、`python3 -B .github/scripts/test-check-repo.py`、`git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning`、`actionlint`。
5. **レビュー:** `/review`。sandbox の外でコードが動く経路に触れるので、`/security-review` も使う。直した後に Codex のレビューを提案する。結果は test-report に記録する。
6. **push と PR:** `/crit-review` でブランチの差分を開き、`approved: true` が返ってから、`cc-safe-push` と `cc-safe-pr` を使う。PR の本文は日本語。ADR 0001 の PR が先にマージされていれば、PR から ADR にリンクする（2026-11-23 の時点では、main に `docs/decisions/` はなく、開いた PR もない）。CI を `gh pr checks` で確かめる。

コミットは、plan、rerere（設定・検査・テスト・文書）、mise（検査・テスト・文書）、test-report に分ける。

<a name="impact"></a>

## 影響

- `bin/.gitconfig` は `~/.gitconfig` のリンク先なので、マージして人間のチェックアウトに入った時点で、人間の git でも rerere が動かなくなる（今は設定していない。`rr-cache` があるリポジトリでは、今は動いている見込み）。
- 戻すときは、`[rerere]` の節と `check-repo.py` の `rerere` を一緒に外す。
- 残る経路: `~/.zshenv`・launchd など、検査しない場所で設定した環境変数。人間が `git -c rerere.enabled=true` などで明示的に有効にした場合。
