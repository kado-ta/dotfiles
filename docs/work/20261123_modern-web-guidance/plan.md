---
status: done
created: 2026-11-23
---

# modern-web-guidance の導入と更新の自動化

<a name="related"></a>

## 関連

- 前の作業: [PR #70 SkillSpector を mise に追加](https://github.com/kado-ta/dotfiles/pull/70)
- 試験記録: [test-report.md](test-report.md)
- 上流: [GoogleChrome/modern-web-guidance](https://github.com/GoogleChrome/modern-web-guidance)（v1.0.1）、npm の `modern-web-guidance@1.0.1`

<a name="goal"></a>

## 目的

フロントエンドと Chrome 拡張機能の開発で、エージェントが最新の Web 標準の書き方（ガイド）を引けるようにする。そのうえで、次を満たす。

- CLI の版を固定し、実行時に npm の最新版を動かさない。
- テレメトリを止める。Claude Code 本体の設定には影響させない。
- 新しい版が出たら、`update-skills.sh` で気づける。取り込みは差分を確かめてから行う。

<a name="decisions"></a>

## 決めたこと

2026-11-23 にユーザーが選んだ。

| 項目 | 決定 | 理由 |
| --- | --- | --- |
| 入れ方 | 上流の SKILL.md を個人スキルとして取り込み、CLI は mise で版を固定する | 公式プラグインは、実行のたびに `npx -y …@latest` で最新版を取得して動かす |
| テレメトリ | SKILL.md のコマンドの先頭に `DISABLE_TELEMETRY=1` を付ける | `settings.json` の `env` に置くと、Claude Code の機能フラグの取得も止まり、Remote Control などが使えなくなる |
| 更新 | `update-skills.sh` から呼ぶスクリプトは、新しい版を知らせるだけで、何も書かない。取り込みは、作業ブランチで `--apply` を明示して行う（`/review` を受けて変えた。[レビューで変えたこと](#review-changes)） | 作業ツリーに書いた候補は、レビューの前に有効になる（スキルはリンク、mise は自動インストール） |
| 取り込み元 | npm の配布物（CLI と同じ tarball） | SKILL.md と CLI の版が必ずそろう |
| `chrome-extensions` | 同じ tarball に同梱されたスキルも、手を加えずに取り込む | Chrome 拡張機能を開発する予定がある（Crit のレビューで追加） |

<a name="facts"></a>

## 調べた事実

- SkillSpector（v2.13.6、`--no-llm`）の判定は 100/100（CRITICAL、DO_NOT_INSTALL）。194 件のうち 179 件は RP1「版を固定しない `npx -y modern-web-guidance`」。ほかの HIGH（AR2・AR3・MP3）は、ガイドの本文（"no warnings"、"without Guardrails"、"clear state"）への誤検知。
- ガイドの本文に `npx -y modern-web-guidance@latest retrieve …` の参照が 208 か所ある。SKILL.md は、pnpm があれば `pnpx` を使えと書いている。sandbox の中でも npm レジストリへの通信（`*.npmjs.org`）と `~/.npm` への書き込みができるので、参照どおりに実行すると最新版が sandbox の中で動く。
- テレメトリは既定で on。検索語・取得したガイドの ID・呼び出し元のエージェント名などを `https://play.googleapis.com/log` に送る。送るたびに、切り離した Node の子プロセスを起動する。止める手段は環境変数 `DISABLE_TELEMETRY`（`1` か `true`）だけ。
- Claude Code の `DISABLE_TELEMETRY` は、値が空でなければ有効になる。テレメトリと一緒に機能フラグの取得も止まり、Remote Control などが使えなくなる（[公式ドキュメント](https://code.claude.com/docs/en/env-vars.md)）。
- npm の 1.0.1 は、依存がなく、インストール時に動くスクリプトもない。tarball には CLI と一緒に `skills/modern-web-guidance/SKILL.md` と `skill-version.txt` が入っている。SKILL.md は GitHub のタグ v1.0.1 のものと同一で、`skill-version.txt`（`2026_11_10-47b4c80e`）は SKILL.md の `--skill-version` と一致する。
- 上流の SKILL.md は、直近 5 リリース（v0.0.195〜v1.0.1）のうち 4 回変わった。リリースはほぼ毎週。
- CLI は、SKILL.md の `--skill-version` が自分の版より 5 日を超えて古いと、更新を促す警告を出す（60 日以上で強い警告）。SKILL.md の方が新しいときは何も出さない。
- 検索はローカルで行い（埋め込みと BM25）、テレメトリを止めれば外部と通信しない。
- 同梱の `chrome-extensions` は、CLI を使わない自己完結のスキル（SKILL.md 530 行と参照ファイル 23 個、172 KB）。npx・CLI・テレメトリへの参照はなく、`modern-web-guidance` のスキルを名前で 1 か所参照するだけ。自動で起動する（拡張機能の話題で）。SkillSpector の判定は 56/100（HIGH）で、指摘は誤検知（PE3 は zip から `.env` を除外する行、E1 は例の URL、AE1 は参照ファイルの表）。

<a name="files"></a>

## 変更するファイル

| # | ファイル | 変更 | 書く人 |
| --- | --- | --- | --- |
| 1 | `mise/mise_config.toml` | `"npm:modern-web-guidance" = "1.0.1"` と理由のコメントを足す | Claude（Edit、確認あり） |
| 2 | `claude/scripts/update-modern-web-guidance.py` | 新規。[更新スクリプト](#script) | Claude |
| 3 | `claude/scripts/test-update-modern-web-guidance.py` | 新規。2 のテスト | Claude |
| 4 | `claude/skills/modern-web-guidance/SKILL.md`・`LICENSE.md` | 新規。2 が生成したものを置く | 人（通常のターミナルで 2 を `--out ~/dotfiles/claude/skills` で実行する） |
| 4b | `claude/skills/chrome-extensions/`（`SKILL.md`・`references/`・`skill-version.txt`・`LICENSE.md`） | 新規。tarball のものをそのまま置く（2 が書く） | 人（4 と同じ実行で置かれる） |
| 5 | `claude/scripts/update-skills.sh` | 2 を呼ぶ手順と、取り込み待ちの表示を足す | Claude |
| 6 | `claude/scripts/test-update-skills.py` | 5 のテストを足す | Claude |
| 7 | `claude/settings.json` | `permissions.deny` に 7 行を足す（[権限](#permissions)） | 人（Claude Code の設定ファイルなので Edit で書けない） |
| 8 | `.github/workflows/ci.yaml` | 3 を macOS のジョブ（`/usr/bin/python3`）で実行する | Claude |
| 9 | `CLAUDE.md` | 「規約」のテストの一覧に 3 を足す | Claude |
| 10 | `claude/SKILL_INVENTORY.md`・`SKILL_CHEATSHEET.md`・`skills-snapshot.json`（要れば `rules/SKILL_ROUTING.md`） | `/sync-skill-docs` で更新する | Claude |
| 11 | `.github/scripts/check-repo.py`・`test-check-repo.py`、`CLAUDE.md` の禁止事項 | スキルがあるあいだ、7 の deny があることを確かめる検査を足す（`playwright-mcp` の検査と同じ考え方。2026-11-23 にユーザーが選んだ）。禁止事項に 1 行足す | Claude |
| 12 | `mise.toml`（`claude:update` の説明）・`claude/README.md` | 新しい版を知らせることを書く（`/review` を受けて足した） | Claude（`mise.toml` を変えたので、人が中身を確かめて `mise trust` し直す） |

<a name="script"></a>

## 更新スクリプト

通常のターミナルで、ホームから実行する。macOS の `/usr/bin/python3`（3.9）で動く書き方にする（`update-skills.sh` と同じ）。

| 使い方 | すること | 誰が・どこで |
| --- | --- | --- |
| 引数なし | 新しい版があるかを確かめるだけ。何も書かない | `update-skills.sh` の手順の 1 つ（[update-skills.sh の変更](#update-skills)） |
| `--out DIR [--latest]` | 固定している版（`--latest` なら npm の latest）のスキルを、DIR の下にだけ書く。取り込む前に中身を確かめる | 誰でも。Claude のセッション（sandbox の中）は `claude/` と `mise/` に書けないので、これを使う |
| `--apply` | npm の latest のスキルと mise の版を、このリポジトリに書く。`check-repo.py` を実行し、パス付きの戻し方を表示する | 人が作業ブランチで、通常のターミナルから。書いた時点で有効になる |

<a name="script-steps"></a>

### 手順

1. `mise/mise_config.toml` から固定している版を読む。`"npm:modern-web-guidance" = "X.Y.Z"` がちょうど 1 行でなければ失敗する。
2. 一時ディレクトリを作る。npm はすべてここで、一時のキャッシュ（`--cache`）・プロジェクトの場所（`--prefix`）・既定のレジストリ（`--registry=https://registry.npmjs.org/`）を指定して動かす。作業ディレクトリや祖先の `.npmrc` と、sandbox の中から書ける `~/.npm` を読ませないため。
3. `npm view modern-web-guidance version` で最新版を得る（`--out` で `--latest` がないときは得ない）。最新版が固定している版より古ければ、取り下げや非推奨を確かめるよう失敗する。
4. 引数なしのとき: 同じなら「最新」と表示して 0、新しければ版と `--apply` の案内を表示して 3 で終わる。何も書かない。`--apply` で同じなら「最新」と表示して 0 で終わる。
5. `npm pack modern-web-guidance@<版>` を実行する。
6. tarball から、`package/LICENSE`・`package/package.json`、`package/skills/modern-web-guidance/` の `SKILL.md`・`skill-version.txt`、`package/skills/chrome-extensions/` の下の全ファイルだけをメモリに読む（ディスクに展開しない）。次のどれかに当たれば失敗する。
   - `package/` の外のエントリーがある（インストーラーは先頭の階層を名前によらず取り除くので、検査していない package.json がインストールで使われうる）
   - 取り込まないものも含めて、名前が正規の相対パスでない（`//`・`.`・`..`・絶対パス・末尾の `/`・`\`）。展開するときは正規のパスと同じ場所を指すので、`package/./package.json` が検証した package.json を上書きしうるため（Codex のレビューの指摘）
   - 取り込まないものも含めて、通常のファイルでない（シンボリックリンクなど）
   - 取り込まないファイルも含めて、重複か、大文字小文字・Unicode の正規化だけが違う名前がある（大文字小文字を区別しない APFS で、検証した内容が上書きされないように）
   - ルートに `binding.gyp` がある（インストールで node-gyp rebuild が暗黙に動く）
   - 取り込むファイルの名前が、ドットで始まる（`.gitignore` などで差分から隠せないように）
   - 取り込むファイルの合計が 2 MB を超える
   - 壊れた tarball
7. [変換と検証](#transform)を行う。失敗したら何も書かずに 1 で終わる。
8. 書き込む。一時ディレクトリに組み立て、書き込み先がその下にあることを確かめてから入れ替える。入れ替えの途中で失敗したら（Ctrl-C を含む）、元のディレクトリに戻し、前になかったスキルは消す。戻すのにも失敗したら、旧版の写しを一時ディレクトリに残して場所を表示する。`--out` のときは DIR の下にだけ書き、mise の設定は変えない。
   - `claude/skills/modern-web-guidance/` に、変換した `SKILL.md` と `LICENSE.md`
   - `claude/skills/chrome-extensions/` に、tarball のファイルをそのまま（上流でなくなったファイルは消す）と `LICENSE.md`
   - mise の版の行（`--apply` のときだけ）
9. `skillspector` があれば、2 つのスキルそれぞれに `skillspector scan <スキル> --no-llm` を実行し、要約を表示する。結果は失敗に数えない。ないときは、入れていないことを表示する。
10. `--apply` のときは、`check-repo.py` を mise の `python3` で実行して結果を表示し、パス付きの戻し方（`git -C <リポジトリ> restore --source=HEAD --staged --worktree -- <3 つのパス>` と `git -C <リポジトリ> clean -fdx -- <2 つのスキル>`）を表示する。スクリプト自身は `git` を実行しない（`check-repo.py` は内部で `git ls-files` を使う。人が続けて使う `git` と同じ程度なので受け入れる）。`check-repo.py` が失敗しても、取り込みは済んでいるので終了コードは 0 で、失敗したことを表示する。

終了コード: 0 は最新、`--out`・`--apply` で書いた。1 は失敗（`--apply` の書き込みの途中の失敗を除き、何も書いていない。途中の失敗では、戻せたかに関わらず戻し方を表示する）。3 は新しい版がある（引数なしのときだけ）。

<a name="transform"></a>

### 変換と検証

変換（上流の SKILL.md に対して、この順で行う）:

1. `npx -y modern-web-guidance@latest` をすべて `DISABLE_TELEMETRY=1 modern-web-guidance` に置き換える。
2. 見出しに `npx` か `pnpx` を含む H2 の節（v1.0.1 では `## Using npx / pnpx`）を、次の H2 の手前まで消す。
3. 本文の `` directly with `npx` `` のような言い回しがあれば消す（v1.0.1 では Step 1 の最初の文）。
4. frontmatter の直後に、変更の表示を HTML コメントで入れる。元の版、Apache-2.0、生成したスクリプト、手で編集しないこと。Apache-2.0 の 4(b)（変更したファイルにその旨を書く）のため。
5. 末尾に、ローカルの節 `## Running the CLI (local install)` を足す。原文に合わせて英語で、次を書く。
   - CLI は mise で版を固定して入れてある。`DISABLE_TELEMETRY=1 modern-web-guidance <command> …` で直接実行する。ネットワークは要らない。
   - ガイドの中の `npx -y modern-web-guidance@latest retrieve "<id>"` は、`DISABLE_TELEMETRY=1 modern-web-guidance retrieve "<id>"` と読み替える。
   - `npx`・`pnpx`・`pnpm dlx`・`bunx`・`npm exec` では実行しない。npm の最新版を取得して動かすうえ、権限の規則で拒否される。
   - `DISABLE_TELEMETRY=1` を必ず付ける。付けないと Google に利用状況を送る。

検証（どれかに当たったら、2 つのスキルとも書かない）:

- package.json に依存（`dependencies`・`optionalDependencies`・`peerDependencies`・`bundleDependencies`）か、インストール時のスクリプト（`preinstall`・`install`・`postinstall`・`prepare` など）がある。`mise install` は sandbox の外で npm のパッケージを入れるため（mise 2026.11 は aube を使う。1.0.1 にはどれもない）。
- package.json の `name` が `modern-web-guidance` でないか、`bin` のコマンドが `modern-web-guidance` だけでないか、`directories.bin` がある。mise は `node_modules/.bin` を PATH の先頭に入れるので、bin が増えると `git` などが置き換わるため。
- frontmatter が閉じていないか、トップレベルのキーに `name`・`description`・`license`・`metadata` 以外がある（`hooks` は sandbox の外で動き、`allowed-tools` は確認なしでツールを使えるので、取り込む前に人が判断する）。`name` が `modern-web-guidance` でない。
- 読み込み時にコマンドを実行する書き方（インラインの `` !`…` `` と、フェンスの ` ```! `・` ~~~! `）がある。フェンスの形が Claude Code で動くかは確かめていない（2 回目のレビューの指摘。拒否しても害はないので含めた）。
- 4 の表示と 5 の節を足した後の本文に、実行できる形が残っている。`npx`・`pnpx`・`bunx` の後に、同じ行で `modern-web-guidance` があるもの。`pnpm`・`bun`・`yarn`・`npm`・`deno` で、オプションの後のサブコマンド（`dlx`・`exec`・`x`・`run`）と、`modern-web-guidance` が同じ行にあるもの。行末の `\` で続けた行は、つなげてから調べる。上流の構成が変わって 2 で消せなかったときに当たる。そのときは手で取り込み、スクリプトの規則を直す。足した表示と節もこの形を含まないように書く（実装中に、最初の文面が SkillSpector の RP1 に当たったため、足す前だけを調べる計画から変えた）。
- `DISABLE_TELEMETRY=1 modern-web-guidance search` が 1 つもない。
- SKILL.md の `--skill-version` が、tarball の `skill-version.txt` と一致しない。
- UTF-8 でない。

`chrome-extensions` は変換しない。検証は、frontmatter（`name` は `chrome-extensions`）と読み込み時に実行する書き方を `SKILL.md` に、実行できる形の npx 系をすべてのファイルに、上と同じ基準で当てる（今はどれもない。上流が CLI を使うように変わったときなどに気づくため）。置いてよいファイルは `SKILL.md`・`skill-version.txt` と `references/` の下の `.md` だけにする（`CLAUDE.md` などが、作業ディレクトリの指示として読まれないように）。ファイルとディレクトリで名前がぶつかるときも失敗する。

<a name="update-skills"></a>

## update-skills.sh の変更

- crit の手順の前に、`modern-web-guidance` の手順を足す。スクリプトを引数なしで `/usr/bin/python3 -I -B` で呼ぶ（`-I` で、スクリプトと同じディレクトリに置かれたモジュールを読まない）。`step` は使わずに終了コードを見て、3 は「取り込み待ち」、それ以外の 0 でない値は失敗として記録する。`step` の中で 3 を区別すると、ほかの手順が返した 3 を取り違えるため。
- 最後の案内の前に、取り込み待ちがあれば次を表示する: 「取り込みを待つ更新: modern-web-guidance（chrome-extensions を含む）。取り込むときは、作業ブランチで /usr/bin/python3 -I -B ~/dotfiles/claude/scripts/update-modern-web-guidance.py --apply を実行する（先に --out <dir> --latest で中身を確かめられる）」。
- 何も書かないので、取り込むまで毎回この表示が出る。取り込み待ちだけなら、終了コードは 0 のまま（失敗ではないため）。

dotfiles の作業ツリーはそのまま使われている設定（スキルは `~/.claude/skills` から、mise の設定は `~/.config/mise/config.toml` からのリンク）で、mise は足りない版を自動で入れる（`auto_install` などが on）。作業ツリーに書いた時点で有効になるので、`update-skills.sh` からは書かない。

<a name="permissions"></a>

## 権限

`claude/settings.json` の `permissions.deny` に次の 7 行を足す（人が編集する）。最初は 5 行（`npm` は `npm exec` だけ）だったが、`/review` で `npm x`（`npm exec` の別名）・`bun x`・`yarn dlx` の漏れが分かり、`npm`・`bun`・`yarn` はサブコマンドを問わない形にした。

```text
Bash(npx *modern-web-guidance*)
Bash(pnpx *modern-web-guidance*)
Bash(pnpm *modern-web-guidance*)
Bash(bunx *modern-web-guidance*)
Bash(bun *modern-web-guidance*)
Bash(yarn *modern-web-guidance*)
Bash(npm *modern-web-guidance*)
```

ガイドの本文の参照や、上流の SKILL.md の指示に従ってエージェントが npx 系で実行し、固定した版を迂回するのを止める。確かめ方は、ダウンロードしない形（`npx --no-install …`・`pnpm --version …` など）が拒否されること。Bash の規則は、ふだんの形を止めるもので、絶対パスや `sh -c` で包んだ形には当たらない（境界ではない）。`modern-web-guidance` という文字列を含むだけのコマンド（`npx prettier docs/work/20261123_modern-web-guidance/plan.md` など）も止まる（受け入れる）。

<a name="steps"></a>

## 手順と確認

| # | 手順 | 確認 |
| --- | --- | --- |
| 1 | 更新した main から `feat/modern-web-guidance` を切る | `git branch --show-current` |
| 2 | 3 のテストを先に書く | テストが失敗する（スクリプトがない） |
| 3 | 2 のスクリプトを書く | 3 のテストが `/usr/bin/python3` と mise の `python3` の両方で通る |
| 4 | `update-skills.sh` と、そのテストを変える | `test-update-skills.py` が通る |
| 5 | mise に `1.0.1` を足し、人が通常のターミナルで `mise install` する | sandbox の中で `modern-web-guidance --version` が 1.0.1 を返す |
| 6 | `--out <scratchpad>` で、本物の 1.0.1 から 2 つのスキルを生成して確かめる。人が通常のターミナルで `--out ~/dotfiles/claude/skills` を実行して置く（`chrome-extensions` は 25 ファイルあり、Write で置くと確認が多いため、実装中に変えた） | SkillSpector の RP1 が消える。置いたものが、scratchpad に生成したものと `diff -r` で一致する |
| 7 | 人が `permissions.deny` に 7 行を足す（`/review` の後に 5 行から広げた） | `npx --no-install modern-web-guidance --version` などが拒否される |
| 8 | 人が 2 つのスキルのリンクを張る: `ln -s ~/dotfiles/claude/skills/modern-web-guidance/ ~/.claude/skills/modern-web-guidance` と、`chrome-extensions` の同じ形（`setup.sh` は全セッションを閉じる必要があるため） | 新しいセッションで 2 つともスキルの一覧に出る。`search` と `retrieve` が、更新の警告なしで動く |
| 9 | `ci.yaml` と `CLAUDE.md` を変える | `actionlint` |
| 10 | `/sync-skill-docs` | 文書がスナップショットと一致する |
| 11 | 全体の検査 | `check-repo.py`・`test-check-repo.py`・`shellcheck`・`actionlint`・変えたスクリプトのテスト |
| 12 | `/review` → 指摘を直す（[レビューで変えたこと](#review-changes)。テストを先に書く）→ もう一度レビュー → コミット → `/crit-review` → push と PR | 変えたスクリプトのテスト・変異テスト・全体の検査、CI の結果 |

<a name="review-changes"></a>

## レビューで変えたこと

`/review`（Testing・Maintainability・Security・Performance・Simplification の観点、攻撃者視点のレビュー、Red Team）の指摘を受けて、2026-11-23 にユーザーが次を選んだ。

| # | 決定 | 指摘 |
| --- | --- | --- |
| D1 | `update-skills.sh` は新しい版を知らせるだけにし、取り込みは作業ブランチで `--apply` を明示する | 作業ツリーに書いた候補は、レビューの前に有効になる。スキルはリンクで即座に読まれ、mise は足りない版を sandbox の外で自動で入れる（`auto_install` などがすべて on。実測）。候補を未コミットのまま残すと、次の実行が「最新」と表示し、取り込み待ちの表示が消えていた |
| D2 | セキュリティの 7 件を直す | `//` を含むパスが検査を抜けて、任意の絶対パスに書けた（再現した）。frontmatter をそのまま写していた。大文字小文字だけが違う名前で、検証した SKILL.md が上書きされうる。ドットで始まる名前で差分から隠せる。package.json の依存とインストール時のスクリプトを見ていない。npm が作業ディレクトリの `.npmrc` と共有のキャッシュを読む。npx 系の網羅（`npm x`・`bun x`・`yarn dlx`） |
| D3 | 堅牢性・テスト・文書を直す | 戻し方の案内にパスがなく、共有の作業ツリーでほかのファイルを消しうる。書き込みの途中の失敗で元に戻さない。壊れた tarball などで例外のまま終わる。latest が固定した版より古くても黙る。`check-repo.py` を取り込みの後に実行しない。テスト 3 件が失敗しえない。sandbox の外で `git status` を自動で実行する |
| D4 | sandbox の中から `~/.npm` に書ける問題は、GitHub Issue にして別の作業で扱う（#74） | この PR の前からある問題 |
| D6 | Codex のレビュー（`codex review`）の P2 を直す | 取り込まないエントリーには正規のパスの検査が当たらず、`package/./package.json` や `package//package.json` が、検証した package.json を展開時に上書きしうる |
| D5 | 2 回目のレビュー（攻撃者視点）の 8 件を直す | フェンス形式（` ```! `）の拒否がない。package.json の `bin` を確かめていない（mise の PATH で `git` などが置き換わる）。`package/` の外や重複のエントリーと `binding.gyp`。`chrome-extensions` がどんな名前でも受け入れる（`CLAUDE.md` など）。`check-repo.py` が git を使う点が、テストと計画と食い違う。入れ替えの戻しが不完全。npx 系の検出の抜け（オプション付き・行の継続・`deno`）。npm の `--prefix` |

<a name="risks"></a>

## 受け入れるリスクと未確認のこと

- テレメトリの停止は、SKILL.md の指示に頼る。付け忘れても、sandbox の中なら `play.googleapis.com` は通信の許可リストにないので届かない見込み。ただし、止まるだけか、許可を求める確認が出るかは確かめていない。人が sandbox の外で CLI を直接実行したときは送られる。上流がテレメトリを止める環境変数の名前を変えても、スクリプトは気づかない。
- deny のルールは、環境変数を前に付けた形（`NPM_CONFIG_CACHE=… npx …`・`DISABLE_TELEMETRY=1 npx …`）にも当たることを確かめた。絶対パスや `sh -c` で包んだ形には当たらない（[権限](#permissions)）。
- ガイドの本文は、CLI の配布物の中身をそのまま使う。取り込みと検査の対象にしない。
- 2 つとも自動で起動するスキルなので、説明文（`modern-web-guidance` は約 200 トークン、`chrome-extensions` は約 175 トークン。README の値）がすべてのセッションのコンテキストに載る。
- `--apply` は、書いた時点でスキルと mise の版を有効にする。mise は自動インストールが on なので、PR のマージより前に、新しい版の CLI が sandbox の外で入りうる。`--out --latest` で中身を確かめてから `--apply` する手順で受け入れる。
- 上流が SKILL.md の構成を変えると、変換の検証で失敗する。そのときは手で取り込み、規則を直す。
- 上流の modern-web-guidance のスキルに、SKILL.md と skill-version.txt 以外のファイル（参照ファイルなど）が増えても、取り込まずに捨てる。見出しに npx を含む節を消す処理は、コードのフェンスの中の `## ` も見出しとして扱う。
- 上流に NOTICE が増えても写さない（Apache-2.0 の 4(d)）。1.0.1 にはない。
- レジストリのメタデータ（packument）の依存・スクリプト・bin を、tarball の package.json と突き合わせていない（manifest confusion）。インストーラーがどちらを使うかによっては、検査をすり抜けうる。
- 設定の `disableSkillShellExecution` で、スキルの読み込み時のシェルの実行を全体で止める方法もある。gstack のスキルがこの書き方を使うので、入れない。
- sandbox の中から `~/.npm`（npm の共有のキャッシュ）に書ける。このスクリプトは一時キャッシュを使うので影響しないが、sandbox の外の npm（`mise install` など）は、sandbox の中で仕込んだキャッシュを信用しうる。この PR の前からある問題で、GitHub Issue にして別の作業で扱う（2026-11-23 にユーザーが選んだ）。

<a name="out-of-scope"></a>

## やらないこと

- 公式プラグインでの導入
- SkillSpector の LLM による分析: 更新スクリプトでの検査は `--no-llm` のままにする。得失は[付録](#llm-analysis)。

<a name="llm-analysis"></a>

## 付録: SkillSpector の LLM による分析の得失

`SKILLSPECTOR_PROVIDER=claude_cli` で `--no-llm` を外すと、静的解析（Stage 1）の後に、手元の `claude` による分析（Stage 2）が加わる。SkillSpector v2.13.6 のソース（`providers/_agent_cli.py`）と README で確かめた。

<a name="llm-how"></a>

### claude の呼び出し方（事実）

- `claude -p` に、`--tools ""`・`--allowed-tools ""`・`--permission-mode dontAsk` を付けてツールをなくす。ほかに `--strict-mcp-config`（MCP なし）、`--setting-sources=`（ユーザー・プロジェクトの設定と hooks を読まない）、`--disable-slash-commands`、`--no-session-persistence`（会話を残さない）を付け、システムプロンプトも固定の短い文に差し替える。
- 検査するスキルの中身は stdin だけで渡し、引数には入れない。子プロセスの環境変数から、API キー・SSH・クラウドの認証情報を消す。
- モデルは、指定しなければ claude の既定のモデル。`SKILLSPECTOR_MODEL` で指定できる。

<a name="llm-pros-cons"></a>

### 得失

| | LLM 分析を使う | 使わない（`--no-llm`） |
| --- | --- | --- |
| 検出 | 文脈と意図を判断する。文字列のパターンに出ない問題（言い換えた指示、説明と動作の食い違い）を見つけうる | 文字列のパターン・AST・YARA だけ。再現率は高く、精度は中程度（README） |
| 誤検知の仕分け | 静的解析の指摘ごとに、確認・否定を判断する。確認できなかった指摘には `llm-unconfirmed` が付く。静的解析の指摘は消えない | 指摘の行を自分で読んで判断する（例: socratic-tutor の "without warning"） |
| 送り先 | Anthropic（Claude Code の利用と同じ契約の範囲）。社内の非公開のスキルを検査すると、その中身も送られる | 外部に送らない（依存パッケージがあれば、その名前を OSV.dev に問い合わせる） |
| 使用量・時間 | Claude のプランの使用量を消費する。1 回の検査で 4 つの分析段が呼ばれる。量と時間は未計測 | 数秒（socratic-tutor で約 3 秒） |
| 安定性 | LLM の判断なので、同じ入力でも結果が変わりうる | 同じ入力なら同じ結果 |
| プロンプトインジェクション | 悪意のあるスキルは、分析役の判断（確認・否定）を誘導しうる。ツールがないので、コマンドの実行などの実害にはならない。`llm-unconfirmed` を安全の印と読まない | 影響を受けない |
| 実行する場所 | sandbox の中では Keychain を読めないので、claude の認証が通らない見込み（未確認）。通常のターミナルで実行する | sandbox の中でも動く |

<a name="llm-recommendation"></a>

### 推奨

- 既定は `--no-llm` のままにする。更新スクリプトの検査も同じ（速さと使用量のため）。
- HIGH 以上の指摘で判断に迷うときや、外部の大きなスキルを入れる前に、通常のターミナルで `SKILLSPECTOR_PROVIDER=claude_cli skillspector scan <dir>` を単発で使う。
- 常用するかは、小さなスキルで使用量と時間を測ってから決める（この作業の範囲外）。
