---
status: done
created: 2026-11-21
---

# 信頼したフォルダの点検タスク

## 関連

- 前回の整理: Claude Code のセッション `6b3eb4a7-2df1-43f9-a31e-876fa10f60bb`（2026-11-20、`~/claude-work/dotfiles-probe` で起動）
- 仕様の出典: 下の [README に書く仕様の要点](#spec-notes)

<a name="goal"></a>

## 目的

Claude Code が信頼したフォルダ（`~/.claude.json` の `projects`）を、Claude に頼まずに点検できるようにする。前回のセッションで手で行った分類と、消すためのコマンドの作成を、読み取りだけのスクリプトにする。書き換えは人間が行う。

スキルにはしない（2026-11-21 のセッションで判断）。分類は機械的に決まり、書き換えは Claude Code のセッションの外でしかできないため。

背景（事実）: 前回の整理の直後は 16 件だった。翌日（2026-11-21）には 18 件になり、そのうち 2 件はフォルダがない。

<a name="done-criteria"></a>

## 完了条件

1. `mise run claude:trust-audit` が、項目を 4 つの区分に分けて表示し、消す候補があれば、消すためのコマンドを出力する。
2. `~/.claude.json` のほかの値（認証の情報、項目のほかのキー）を出力しない。テストで確かめる。
3. `~/.claude.json` を書き換えない。git を実行しない。
4. 終了コードは、0: 候補なし、1: 候補あり、2: 点検できない。
5. `test-trust-audit.py` が `/usr/bin/python3` と mise の `python3` で通る。`check-repo.py`・`test-check-repo.py`・shellcheck・actionlint が通る。
6. 実物の `~/.claude.json` に対して実行し、2026-11-21 の 18 件が [出力の例](#output) のとおりに分かれる（実行する日までに項目が変わっていれば、その差分を説明できる）。

<a name="behavior"></a>

## スクリプトの動作（`claude/scripts/trust-audit.py`）

`~/.claude.json`（`HOME` から決める）の `projects` のキーと、各項目の `hasTrustDialogAccepted` だけを読む。

区分は上から順に判定する。

| 区分 | 条件 | 出す提案 |
| --- | --- | --- |
| `home` | キーが `HOME` と同じ | なし。ホームの信頼は保存されない仕様 |
| `missing` | フォルダがない | `claude purge --dry-run` と `claude purge`（項目と会話の記録を消す）。記録を残すなら、jq で項目だけ消す |
| `repo` | フォルダ自身か、その親に `.git`（ディレクトリかファイル）がある | なし |
| `not-repo` | 上のどれでもない | 信頼が `true` なら、jq で項目を消す（親の信頼が下のフォルダに及ぶため）。`false` なら提案しない |

- 使っていないリポジトリかどうかは判定しない。一覧を見て人間が決め、jq の `--args` に足す。
- コマンドのパスは `shlex.quote` で引用する。フォルダ名に空白や `$(…)` があっても、シェルに解釈されない。
- 出力は端末だけに出す。ファイルには書かない。

<a name="output"></a>

### 出力の例（2026-11-21 の状態で期待する結果）

```text
区分      信頼   パス
missing   true   ~/Dev/example/gone-a
missing   true   ~/Dev/example/gone-b
home      false  ~
not-repo  false  ~/claude-work/dotfiles-probe
repo      true   ~/Dev/example/repo-a
（repo の残り 13 件）

# Claude Code をすべて閉じてから、通常のターミナルで実行する
cp -p ~/.claude.json ~/.claude.json.bak-20261121

# 1. フォルダがない項目を、会話の記録ごと消す（元に戻せない。先に --dry-run で確かめる）
claude purge --dry-run '<パス>'
claude purge '<パス>'

# 2. 信頼を外す（会話の記録は残す）。1 の代わりに記録を残すなら、1 のパスもここに足す
jq '.projects |= with_entries(select(.key | IN($ARGS.positional[]) | not))' ~/.claude.json --args '<パス>' ... \
  > ~/.claude.json.new && cat ~/.claude.json.new > ~/.claude.json && rm ~/.claude.json.new
```

今の状態では、2 に当たる項目はない（`dotfiles-probe` は信頼が `false`）。2 は、候補があるときだけ出す。

<a name="decisions"></a>

## 判断したこと

1. **書き換えない。** Claude Code は動いている間に `~/.claude.json` を書き戻す。前回外した `dotfiles-probe` の項目は、`lastSessionId` 付きで残っていた。終了したセッションが書き戻したと見ているが、推測である。`claude purge` は元に戻せない。
   - 採らなかった案: `--apply` で書き換える。動いている Claude Code を確実に見つける方法を確かめていないので採らない。
2. **git を実行せず、`.git` の有無で判定する。** 点検の対象は任意のフォルダで、git はそのリポジトリの設定（`core.fsmonitor` など）を読む。`.git` の有無で用が足りるので、その経路を作らない。
   - 代わりに失うもの: `GIT_DIR` を使う構成と bare リポジトリは、`not-repo` に出る。一覧を見て人間が判断できるので受け入れる。
3. **ルートの `mise.toml` に置き、`/usr/bin/python3 -B` で動かす。** `claude:skills-check` などと同じ形にする。Python 3.9 で動く書き方にする。
4. **出力には、パスと `hasTrustDialogAccepted` の値だけを出す。** `~/.claude.json` には認証の情報も入っている。

<a name="files"></a>

## 変更するファイル

| ファイル | 変更 |
| --- | --- |
| `claude/scripts/trust-audit.py` | 新規 |
| `claude/scripts/test-trust-audit.py` | 新規。偽の HOME で確かめる |
| `mise.toml` | `claude:trust-audit` を足す |
| `claude/README.md` | 「信頼したフォルダの点検」の節を足す（使い方と仕様の要点） |
| `CLAUDE.md` | 規約のテストの一覧に `trust-audit.py` を足す |
| `.github/workflows/ci.yaml` | 偽の `~/.claude` を使う単体テストのステップに `test-trust-audit.py` を足す。ステップ名 `Tests for skill doc scripts` が中身と合わなくなるので、`Tests for Claude scripts` に変える |
| `docs/work/20261121_claude-trust-audit/` | この plan と test-report |

<a name="spec-notes"></a>

## README に書く仕様の要点

前回のセッションで、サブエージェントが公式ドキュメントから調べた内容。実装のときに出典を読み直して確かめる。

- 信頼は `~/.claude.json` の `projects["<パス>"].hasTrustDialogAccepted` に記録される。キーは、リポジトリの中ではリポジトリのルート、外ではそのフォルダ自身（permissions）。
- リポジトリの外では、信頼は下のフォルダにも及ぶ。下にある Git リポジトリは除く（permissions）。
- ホームで起動したときの信頼は、そのセッションのあいだだけで、保存されない（permissions・security）。
- 信頼を一覧・取り消す公式のコマンドは見つからなかった。`claude purge <パス>` は、項目（信頼・履歴・MCP の選択）と会話の記録をまとめて消す（claude-directory）。フォルダがないパスにも使える（2026-11-20 に 11 件で実測）。
- 編集は、Claude Code をすべて閉じてから行う。ドキュメントの記述ではなく、前回の観察からの推測。

<a name="impact"></a>

## 影響

- 既存の動作は変わらない。読み取りだけのスクリプトが増える。
- `mise.toml` を変えるので、paranoid の設定により、人間が `mise.toml` の全体を確かめて `mise trust` し直すまで、ルートの mise タスクはどれも読み込まれない。worktree で試すときは、worktree の `mise.toml` も同じ。
- `~/.claude.json` は Claude Code の内部の形式で、変わると点検できなくなる。`projects` が辞書でなければ、終了コード 2 で止める。

<a name="steps"></a>

## 手順

1. テストを書く → スクリプトがないので失敗することを確かめる。
   - 区分の判定: `missing`・`home`・`not-repo`（信頼 `true` と `false`）・`repo`（`.git` がディレクトリ、ファイル（worktree）、親にある）
   - 提案: `missing` は purge、`not-repo` で信頼が `true` は jq、ほかは提案しない
   - ほかの値を出さない: 認証の情報と、項目のほかのキーに目印の文字列を入れ、出力に出ないこと
   - 引用: パスに空白・`'`・`$(…)` があっても、出力の `--args` を `shlex.split` で読むと元のパスに戻ること
   - 終了コード 0・1・2（2 は、ファイルがない、JSON でない、`projects` が辞書でない。Traceback を出さない）
2. スクリプトを書く → テストが `/usr/bin/python3 -B` と mise の `python3 -B` で通る。
3. mise タスク・README・CLAUDE.md・ci.yaml を直す → `check-repo.py`・`test-check-repo.py`・shellcheck・actionlint が通る。README の仕様は、出典を読み直してから書く。
4. 実物で確かめる → Claude が Bash で `/usr/bin/python3 -B claude/scripts/trust-audit.py` を実行し、[出力の例](#output) と比べる（読み取りだけなので sandbox の中で動く）。人間が通常のターミナルで `mise trust` してから `mise run claude:trust-audit` を実行する。
5. `/review` → `/crit-review` でブランチの差分を確かめてもらう → push と PR。

<a name="work-location"></a>

## 作業場所

dotfiles の作業ツリーは、別の作業（`fix/protect-main-branch-read-only-branch`、未コミットの変更あり）が使っている。ここでブランチを切ると、その作業とコミットが混ざる。人間が `claude -w trust-audit` で worktree のセッションを始め、そこで実装する。この plan は worktree に移し、ブランチ名は `feat/claude-trust-audit` に変える。

<a name="out-of-scope"></a>

## 範囲外

- `~/.claude.json` の書き換えと、`claude purge` の実行
- 使っていないリポジトリの判定
- `CLAUDE_CONFIG_DIR` を設定した環境（`~/.claude.json` の場所が変わる）
- Codex・mise の信頼の点検（前回のセッションの最初に一覧を出したが、依頼は Claude Code の信頼だけだった）
