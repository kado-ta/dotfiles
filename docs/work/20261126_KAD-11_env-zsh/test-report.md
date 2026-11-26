---
status: in-progress
created: 2026-11-26
---

# 試験記録: sheldon の env-zsh を外す

<a name="related"></a>

## 関連

- Linear: KAD-11（この作業）、KAD-26（SOPS で暗号化したファイルを mise で読み込むか決める。別の作業）
- 変更したファイル: `config/sheldon/plugins.toml`・`zsh/README.md`・`.claude/rules/CLAUDE_CONFIG.md`

<a name="summary"></a>

## 要点

- env-zsh は、zsh の起動時とディレクトリを移るたびに、作業ディレクトリの `.env` と `.env.term` をシェルのコードとして読み込んでいた。中身を確かめる仕組みはなかった（プラグインの本体 `env.plugin.zsh` を読んで確かめた）。
- 対応の案は、外す・direnv に替える・読み込むディレクトリを限る、の 3 つを比べ、外すことにした（2026-11-26、人間の判断）。SOPS は秘密の中身を守る仕組みで、書いた人を確かめないので、この作業では扱わず KAD-26 にした。
- 代わりの読み込み方は、プロジェクトの `mise.toml` の `[env] _.file` にした。mise はグローバルの設定の paranoid（`config`・`env_files`）で、設定と env ファイルを中身で信頼する。

<a name="checks"></a>

## リポジトリの検査

CLAUDE.md の規約の検査を、変更のたびに実行した。

| 対象 | コマンド | 結果 |
| --- | --- | --- |
| 3ebcdc6（コミット前の作業ツリー） | `python3 -B .github/scripts/check-repo.py` | 全項目 PASS |
| 同上 | `python3 -B .github/scripts/test-check-repo.py` | 147 件 OK |
| 同上 | shellcheck（CLAUDE.md の形）・`actionlint`・`zizmor --offline .` | すべて rc=0 |
| 7e0066c（コミット前の作業ツリー） | 上の 5 つ | 同じ結果 |
| Codex の 1 回目への対応（コミット前の作業ツリー。この記録を含む） | 上の 5 つ | 同じ結果 |
| Crit の 1 回目への対応（README の節の分割。コミット前の作業ツリー） | 上の 5 つ | 同じ結果 |

<a name="behavior"></a>

## 動作の確認

一時ディレクトリだけを使った。mise の信頼の記録も一時ディレクトリに置き、手元の記録には書いていない。sandbox は `.env*` を読めないので、env ファイルの名前は `vars.env` にした（拡張子が `.env` なので dotenv として解析される）。

| # | 確かめたこと | 結果 |
| --- | --- | --- |
| C1 | 新しい `plugins.toml` で、sheldon 0.8.5 が生成するスクリプトに env-zsh が入らない | pass。`sheldon source` は exit 0、env-zsh を指す行は 0 件、`zsh -n` は exit 0（3ebcdc6） |
| C2 | mise 2026.11.14 の `_.file` は解析だけで実行しない。信頼するまで読み込まず、中身が変わると信頼が外れる | pass。信頼の前は exit 1。信頼の後は `$(...)` とバッククォートが文字列のまま残り、`touch` は実行されない。env ファイルを書き換えると exit 1 |
| C3 | env ファイルが読めないときの mise の振る舞い | 実行していない（`chmod 000` を使う確認が、Claude Code の auto mode に拒否された） |
| C4 | `_.file` に書いた `PATH` の扱いと、配列の読み込み順（Codex の指摘の確認） | `PATH` は `mise env` の出力に入らなかった。`_.file = ["vars.env", "vars.env.term"]` では後ろの値が勝った |

<a name="review"></a>

## /review

gstack の `/review` を 3ebcdc6 に対して実行した。差分は 9 行で、specialist は対象外、Claude の adversarial review を 1 回実行した（Codex のパスは gstack の設定で無効）。

- 採用: `_.file` は値を export し、そのディレクトリで起動したプロセス（Claude Code を含む）にも渡る。env-zsh の `KEY=value` は子プロセスに渡らなかったので、README に秘密の値を入れない注意を足した。`$(...)` と `~` が展開されないことも書いた（7e0066c）。
- 見送り: env-zsh の足し直しを止める検査を `check-repo.py` に足す案（人間の判断。足し直しは `plugins.toml` の差分として PR のレビューで見える）。
- 欠陥ではないとしたもの: 外したことで `.env` の変数が読み込まれなくなる（受け入れたトレードオフ）。信頼した env ファイルは mise の設定を変える変数も export できる（信頼したすべての mise の設定に当てはまる、もとからの性質）。

<a name="codex"></a>

## Codex レビュー

<a name="codex-run-1"></a>

### 1 回目（2026-11-26、7e0066c）

`codex review --base main`。結果は「patch is incorrect」で、指摘は 4 件、どれも `zsh/README.md` の移行の案内に対するもの。

| 指摘 | 採否 | 理由 |
| --- | --- | --- |
| [P1] `mise trust` は確かめたファイルを明示して実行するよう案内する | 採用 | `mise trust --help` に、パスを省くと設定が読む env ファイルとスクリプトもまとめて信頼する、とある。`.claude/rules/CLAUDE_CONFIG.md` の手順（`mise trust <ファイル>`）とも合う |
| [P2] 外す前から開いている zsh は起動し直すよう案内する | 採用 | env-zsh は chpwd にフックを登録するので、開いているシェルでは読み込みが続く。README の既存の手順を指した |
| [P2] `.env` の `PATH` は `_.path` に移すよう案内する | 採用 | C4 で、`PATH` が使われないことを確かめた |
| [P2] `.env.term` を使っていた場合の移し方を案内する | 採用 | C4 で、配列の後ろのファイルが勝つことを確かめた |

<a name="unverified"></a>

## 未検証

- Claude Code の sandbox の中で、`_.file = ".env"` にしたプロジェクトの mise がどう振る舞うか（C3）。
- マージの後、`~/dotfiles` を更新して開き直した zsh で、`.env` が読み込まれないこと。人間が確かめる。
