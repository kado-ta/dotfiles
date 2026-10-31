# Documents

リポジトリに文書の配置ルールがない場合の既定。リポジトリの CLAUDE.md / AGENTS.md / ADR に別のルールがあればそちらに従う。スキルの既定の保存先（superpowers の `docs/superpowers/` など）より優先する。

## Layout

文書は寿命で分けて置く。

| 種類 | 寿命 | 更新方針 | 置き場所 |
| --- | --- | --- | --- |
| 仕様書 | 機能が存在する間 | 振る舞いを変える PR で一緒に更新し、常に最新に保つ | `docs/specs/` |
| ADR | 恒久 | 本文は原則変えない。覆すときは新しい ADR を作り、旧 ADR を `superseded by ADR-NNNN` にする | `docs/decisions/` |
| runbook | 運用が続く間 | 随時更新する | `docs/runbooks/` |
| 作業文書（plan / design / 調査 / 試験記録） | 作業完了まで | 完了後は変更しない（履歴として残す） | `docs/work/<ID>_<slug>/` |

```text
docs/
├── specs/<feature>.md          # 現在の仕様（常に最新に保つ）
├── decisions/NNNN-<slug>.md    # ADR（MADR）。リポジトリ全体で通し番号
├── runbooks/                   # 運用手順
└── work/<ID>_<slug>/           # Issue / Work Item 単位の作業文書
    ├── plan.md
    ├── design.md               # 必要なときだけ
    ├── research-<topic>.md     # 調査メモ（複数可）
    ├── test-report.md
    └── assets/                 # 画像など（必要なときだけ）
```

- ID は、GitHub Issue なら `GH-<番号>` とし、ゼロ埋めしない（例: `GH-12`）。それ以外のトラッカー（例: Salesforce Lifecycle Center の `WI-000002`）の ID は、各リポジトリのルールで決める。
- ID のない作業は作成日を ID とし、`YYYYMMDD_<slug>` にする。
- superpowers の brainstorming の design は `work/<ID>_<slug>/design.md` に、writing-plans の plan は `work/<ID>_<slug>/plan.md` に書く。

## Naming

1. ファイル名・ディレクトリ名は英小文字・数字・ハイフン（kebab-case）だけにする。例外は作業ディレクトリ名の ID（`GH-12` など）と、ID と slug の区切りの `_`。日本語のタイトルは本文に書く。日本語名は GitHub の URL がパーセントエンコードされて読めなくなり、macOS の Unicode 正規化の違いで別ファイル扱いになるおそれもあるため。
2. ファイル名に `[ ]` を使わない。シェルが文字の集合と解釈するため（`[plan]_*` は `p_` `l_` `a_` `n_` で始まる名前にマッチする）。
3. 作業ディレクトリは `<ID>_<slug>` とする。ID 自体にハイフンを含むため、区切りは `_` にする。ID はブランチ名・Issue と一致させる。
4. 作業ディレクトリ内のファイル名は種別だけにする（`plan.md` / `design.md` / `research-<topic>.md` / `test-report.md`）。
5. ADR は `NNNN-<slug>.md`（4 桁の通し番号。MADR の既定）とし、採番後は変えない。
6. 仕様書は `<feature>.md` とし、大きくなったら `specs/<feature>/` に分ける。
7. 既に命名が定着しているディレクトリ（例: 大文字の runbooks）は改名しない。

## Metadata

- メタ情報は YAML ヘッダーに書いてよい。キーと値は英語にする。
  - 作業文書: `status` と `created`（`YYYY-MM-DD`）。`status` の値は `draft` / `in-review` / `in-progress` / `done`。
  - ADR: MADR の項目（`status` / `date` / `decision-makers` など）。`status` の値は `proposed` / `accepted` / `rejected` / `deprecated` / `superseded by ADR-NNNN`。
- 関連リンク（Issue・ADR・仕様書・前の作業）は YAML ヘッダーではなく、本文の「関連」欄に書く。

## Workflow

- 作業が完了したら `status` を `done` にし、以後は編集しない。後続の作業は新しいディレクトリを作り、前の作業へリンクする。
- 仕様書は、振る舞いを変える作業の PR で一緒に更新する。
- 作業文書・仕様書の更新・ADR は、その作業のブランチでコミットする。
- 生成物（ログ、retrieve の結果など）はコミットせず、Git 管理外の `tmp/` に出し、要点だけを `research-<topic>.md` に書く。`tmp/` が Git の管理外になっていなければ、書き出す前に `.gitignore` への追加を提案する。
