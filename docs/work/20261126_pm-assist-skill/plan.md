---
status: done
created: 2026-11-26
---

# pm-assist スキルの追加

<a name="related"></a>

## 関連

- 調査: [research-improvements.md](research-improvements.md)
- 参考元: ローカルにある他の dotfiles の pm-assist スキル（非公開の見込みで LICENSE もないので、中身の詳細と文面は載せない）
- [スキルの規則](../../../claude/rules/SKILL_ROUTING.md)、[文書の置き場所](../../../claude/rules/DOCUMENTS.md)、[sync-skill-docs](../../../.claude/skills/sync-skill-docs/SKILL.md)

<a name="goal"></a>

## 目的と範囲

個人スキル `pm-assist` を足す。プロジェクト（ゴールと期限のある有期の取り組み）の運営を補佐し、現状・進め方・タスク・リスク・判断事項を整理する。決めるのはユーザー。

範囲外:

- 何を作るかの判断（`/office-hours`）、機能の要件と設計（`brainstorming`）、実装の計画（`writing-plans`）
- Notion の読み取り（[Issue #121](https://github.com/kado-ta/dotfiles/issues/121)）
- `claude/rules/SKILL_ROUTING.md` の変更（起動テストで誤った振り分けが分かったときだけ、ユーザーに確かめてから 1 行足す）

<a name="decisions"></a>

## 決まったこと

2026-11-26 にユーザーが判断した。

- 調査の推奨をすべて採る（[推奨の一覧](research-improvements.md#summary)）。
- 自動で起動する（[C1](research-improvements.md#c1)）。明示だけ（C2）にはしない。
- リンクは worktree に一時的に張り、マージの後に張り替える（[G1](research-improvements.md#g1) の案 A）。その後、`/review` の指摘（守りの境界が動く）を受けて、出力の確認の後に外し、マージの直後に `~/dotfiles` に張ることにした（2026-11-26 にユーザーが判断）。
- 起動テストは、ユーザーが通常のターミナルで実行する。

<a name="files"></a>

## 作るファイル・変えるファイル

| ファイル | 区分 | 要点 |
| --- | --- | --- |
| `claude/skills/pm-assist/SKILL.md` | 新規（約 90 行） | 起動条件・確かめる順番・原則。下の [SKILL.md の要点](#skill-md) |
| `claude/skills/pm-assist/REFERENCE.md` | 新規（約 90 行） | 必要なときに読む道具箱。下の [REFERENCE.md の要点](#reference-md) |
| `claude/skills/pm-assist/TEMPLATES.md` | 新規（約 70 行） | 整理メモと見直しの 2 つの雛形。下の [TEMPLATES.md の要点](#templates-md) |
| `docs/work/20261126_pm-assist-skill/assets/trigger-eval.json` | 新規 | 起動テストの依頼文 21 件（[一覧](#trigger-queries)）。結果の JSON はコミットしない |
| `docs/work/20261126_pm-assist-skill/test-report.md` | 新規 | 出典の確認（ユーザーのブラウザでの確認と、保存してもらった PDF）・起動テスト・出力の確認・リポジトリの検査の記録 |
| `claude/SKILL_INVENTORY.md` | 変更 | 時点の行、提供元の表の個人スキルの件数（7 → 8）、個人スキルの節の見出しと表の行、重複と裁定の表に 1 行（プロジェクトの運営）、規則の効果の確認の節に 1 文（測定の期間中に、自動で起動するスキルを足した） |
| `claude/SKILL_CHEATSHEET.md` | 変更 | 場面の表に 1 行、個人スキルの一覧に 1 行 |
| `claude/skills-snapshot.json` | 作り直し | ユーザーが通常のターミナルで作る（sandbox の中から `claude/` に書けないため） |

変えないもの: `claude/rules/SKILL_ROUTING.md`（上の範囲外のとおり）、`claude/settings.json`、`claude/setup.sh`（今の個人スキルのリンクの処理で足りる）、`claude/README.md`（提供元を足さないので対象外）。

<a name="skill-md"></a>

### SKILL.md の要点

- frontmatter は `name: pm-assist` と `description` だけ。description は英語で書き、日本語の例を添える（近くの個人スキルに合わせる）。案（1,536 文字の上限の内）:

  ```text
  Use when the user asks for help running a project — a time-boxed effort with a goal and a deadline — such as organizing a new project or product launch, preparing a kickoff, reviewing progress, recovering a slipping project, or laying out a project's tasks, risks and decisions (e.g. 「ローンチまでの進め方を整理したい」「キックオフまでに決めておくことを洗い出して」「リリースまでのスケジュールと体制のリスクを洗い出して」「遅れている案件の立て直しを相談したい」). Not for breaking down a single ticket or a day's tasks, the risks of a code change or design under development, deciding what to build (/office-hours), feature requirements (brainstorming), or implementation plans (writing-plans).
  ```

  例の選び方: 日々のタスクや開発中の変更と見分けられる語（ローンチ・キックオフ・スケジュールと体制・立て直し）を、1 つの例に 1 つ以上入れる。立ち上げ・計画・実行中・立て直しのフェーズを 1 つずつ覆う。「次に何をすべきか」「リスクを洗い出して」のような汎用の言い回しは、単独では開発中にも出るので、リスクの例は「スケジュールと体制」を付けてプロジェクトの文脈に限る。「このプロジェクト」は開発中にはリポジトリを指すことがあるので使わない。どれも Claude の想定で、ユーザーの普段の言い方に基づいていない。普段の言い方が分かれば入れ替える。

- 本文は日本語。確かめる順番として 6 つを書く（決まった手順にはしない）。
  1. 現状把握: 渡された資料は、使える手段（`gh`・MCP・WebFetch）で先に読み、読めなければ要点の貼り付けを頼む。確かめる項目は目的・完了の定義・期限とその根拠・体制と決める人・関係者・制約・現在地。不明で重要なものだけを 5 件までにして聞く。分かっている範囲で仮に組み、前提として示す。出す前にも同じ項目で確かめる（セルフチェックをここにまとめる）。
  2. 進め方の型: 規模（軽量型・エンプラ型。目安の表。迷ったら軽いほう）と、不確実性（答えが分かっている／調べれば分かる／やってみないと分からない／すぐ止血が要る）の 2 つの軸で決める。やってみないと分からない案件では、細かいタスク分解より、仮説と小さな検証をマイルストーンにする。
  3. フェーズ: 立ち上げ・計画・実行と監視・立て直し・終結と、それぞれの焦点。判定を示して、ユーザーとすり合わせる。
  4. タスク: 成果物から分解し、直近は細かく遠くは粗くする。担当・依存・優先度を付け、マイルストーンとクリティカルパスを置く。忘れられがちなタスク（承認待ち・環境・受け入れ・周知・引き継ぎ・リリース後の監視）を確かめる。見積もりは `REFERENCE.md` に従う。
  5. リスク（省かない）: リスク・前提・課題・依存・分かっていないことの 5 つに分ける。人・外部・技術・スコープ・意思決定の観点は毎回見る。上位のものに次のアクションと担当を付ける。量は案件に合わせ、軽い依頼では上位 3 件にする。出尽くさないときと節目には、プレモーテムを使う。
  6. アウトプット: `TEMPLATES.md` の形で出す。判断事項には、元に戻せるか・決める人（1 人）・期限・推奨と理由を付け、依存があれば親の決定から並べる。
- 2 回目以降は、前回の結果から差分（終わったこと・遅れ・計画とのずれ・新しいリスク）を先に見る。前回の結果が手元になければ、貼り付けを頼む。
- 保存: 既定はチャットに出すだけ。保存を頼まれたら、リポジトリの規則に従い、なければ DOCUMENTS.md の作業文書として、作業ディレクトリの `plan.md` に置く。作業ディレクトリの名前の形は書き写さず、DOCUMENTS.md を参照する（2026-11-26 に `YYYYMMDD_<ID>_<slug>` に変わったため。調査の [D2](research-improvements.md#d2) は変わる前の形で書いた）。
- 原則（このスキルに固有のものだけ）: リスクを出さずに終わらない。目的を問い、要らない作業は「やらない」と提案する。プロセスや成果物を押し付けない。誰に何をいつ先回りで伝えるかを含める。

<a name="reference-md"></a>

### REFERENCE.md の要点

- 抜けを見つける問い: PMBOK 第 8 版の 7 つのパフォーマンス領域（governance・scope・schedule・finance・stakeholders・resources・risk）を見出しにし、問いは自分の言葉で書く。品質（完了の定義と受け入れ）・コミュニケーション・調達は自前の問いとして足す（第 8 版では、品質は原則に入り、コミュニケーションを扱う領域はないとされる。二次情報）。領域の名前はユーザーがブラウザで確かめた。軽量型では一部に絞ってよいと書く。
- 不確実性の 4 つの分類と、それぞれの進め方（Cynefin を参考にしたと出典を書く）。
- リスク: カテゴリ別の観点（技術・外部・組織・プロジェクトの運営・関係者・好機）、確率 × 影響の 3 段階の表、脅威への対応 5 つ（回避・軽減・転嫁・受容・エスカレーション）と好機への対応、プレモーテム（Klein）と Tiger / Paper Tiger / Elephant（Doshi。Paper Tiger は、ほかの人は心配しているかもしれないが、挙げた本人は担当として抑えられていると確信している脅威。Elephant は、誰も話題にしていないことが心配なもの）。対策は上位の Tiger と Elephant に絞り、1 件に担当を 1 人付けて、プロジェクトの計画に組み込む。Tiger に緊急度の区分は付けない（出典にないため）。
- 判断: 元に戻せない決定は慎重に、戻せる決定は小さく速く（Bezos）。決める人は 1 人にする。チームをまたぐ決定では DACI の役割を使ってもよい（1 行）。
- 見積もり: 先に類似案件の実績を聞く（参照クラス予測、Flyvbjerg）。不確実なら三点見積もりと幅で示す。幅は決めることを決めないと狭まらない（McConnell）。コーンの数値は書かない。
- 優先度: Impact × Effort、MoSCoW（W は「今回はやらない」。Must は工数の 6 割以下が目安）。
- 関係者: 権力 × 関心のグリッドは、エンプラ型か関係者が多いときだけ使う。
- アンチパターン: 数人の案件に重い成果物を持ち込む、リスクを並べるだけで終わる、全部を同じ粒度で分解する、質問攻め、一点の見積もり。
- 出典: 上の枠組みの出典の URL（調査の[出典と取得の状況](research-improvements.md#sources)のうち、本文か抄録で確かめたもの）。

<a name="templates-md"></a>

### TEMPLATES.md の要点

- 整理メモ: 現状のまとめ（フェーズ・型とその根拠・ゴール・期限）、タスク（担当・依存・優先度・マイルストーン）、リスク（5 つの分類。上位に次のアクション）、次のアクション（3〜7 個）、共有（誰に・何を・いつ）、判断事項（元に戻せるか・決める人・期限・推奨と理由）。エンプラ型で足す節（体制と関係者、成果物ごとのワークパッケージ、クリティカルパス、コミュニケーション計画）は注記で示す。リスクの節は消さないと書く。
- 見直し（2 回目以降）: 前回からの差分、リスクの見直し（顕在化・新規・消えたもの）、再計画、次のアクション、判断事項。

<a name="changes"></a>

## 参考元から変える点

| 変える点 | 参考元 | 変えた後 | 理由 |
| --- | --- | --- | --- |
| 起動条件 | 日本語の文章。開発中にも出る言い回しを起動語にする | 英語の「Use when …」と日本語の例。プロジェクトの運営に限り、起動しない例を書く | [C1](research-improvements.md#c1) |
| PMBOK の版 | 2 つの版の枠組みが混ざる | 第 8 版の 7 領域を見出しにした自前の問い。原則の一覧は書かない | [A1](research-improvements.md#a1) |
| 進め方の型 | 規模の軸だけ | 規模と不確実性の 2 つの軸 | [B1](research-improvements.md#b1) |
| リスクの分類 | 課題と依存が独立していない | リスク・前提・課題・依存・分かっていないことの 5 つ。量は案件に合わせる | [B2](research-improvements.md#b2)、[E4](research-improvements.md#e4) |
| リスクへの対応 | エスカレーションがない | 脅威への 5 つ（エスカレーションを足す）と好機への対応 | [A2](research-improvements.md#a2) |
| プレモーテム | 出典がなく、Paper Tiger の定義が記事と違う。Tiger に緊急度の区分を付ける | Klein と Doshi を出典に書き、Paper Tiger の定義を記事に合わせる。緊急度の区分は削る | [A3](research-improvements.md#a3) |
| 判断事項 | 元に戻せるかの観点がない | 元に戻せるか、決める人は 1 人、を足す | [B3](research-improvements.md#b3) |
| 見積もり | 類似案件の実績は技法の 1 つにとどまる | 先に類似案件の実績を聞く。幅は決めないと狭まらない | [B4](research-improvements.md#b4)、[A4](research-improvements.md#a4) |
| 優先度 | 製品の優先度付けの手法を含む | RICE を削る。MoSCoW を DSDM の定義に合わせる | [B5](research-improvements.md#b5) |
| 資料の読み方 | 特定のツールの資料を MCP で読む前提 | 使える手段で読み、読めなければ貼り付けを頼む | [D1](research-improvements.md#d1) |
| 保存 | 決めていない | 既定はチャット。頼まれたら DOCUMENTS.md の作業文書 | [D2](research-improvements.md#d2) |
| 原則 | グローバルの CLAUDE.md と重なるものを含む | グローバルの CLAUDE.md と重なる 2 つを削る | [D3](research-improvements.md#d3) |
| 雛形・重複 | 型ごとの雛形、セルフチェック、フェーズ別の成果物の表が重なる | 雛形 2 つ。セルフチェックは現状把握にまとめ、成果物の表は削る | [E1](research-improvements.md#e1)〜[E3](research-improvements.md#e3) |
| 文面 | — | すべて自分の言葉で書く | 参考元に LICENSE がなく、このリポジトリは公開 |

<a name="steps"></a>

## 手順

各手順の後に、右の確かめ方で確かめてから次に進む。

| # | 手順 | 確かめ方 |
| --- | --- | --- |
| 1 | この plan を `/crit-review` で開く | `approved: true` が返る |
| 2 | 3 つのファイルを書く（Edit・Write。`claude/` の編集は承認の画面が出る） | 各ファイルが 500 行未満。`check-repo.py` の `markdown-names`・`markdown-links` が PASS |
| 3 | `trigger-eval.json` を書く | `jq length` が 21。起動すべき依頼が 10 件、起動すべきでない依頼が 11 件 |
| 4 | 起動テストをユーザーに頼む（[実行のコマンド](#eval-commands)）。結果を読んで `test-report.md` に書く | [合格の基準](#eval-criteria) |
| 5 | 一時リンクをユーザーに頼む: `ln -s ~/dotfiles/.claude/worktrees/pm-assist/claude/skills/pm-assist ~/.claude/skills/pm-assist` | このセッションのスキル一覧に `pm-assist` が出る。出なければユーザーが `/reload-skills` を実行する |
| 6 | このセッションで、出力を 2 件確かめる（[出力の確認](#output-check)） | 基準を満たす。`test-report.md` に書く |
| 7 | sync-skill-docs の手順で文書を合わせる。スナップショットの作り直しをユーザーに頼む | `mise run claude:skills-check` が終了コード 0 |
| 8 | リポジトリの検査を実行する（[一覧](#repo-checks)） | すべて通る |
| 9 | `/review` で差分をレビューし、指摘に対応する | 対応が決まる |
| 10 | `/crit-review` でブランチの差分を開く。承認後に commit・`cc-safe-push`・`cc-safe-pr`・`gh pr checks` | `approved: true`、CI が通る |
| 11 | マージの後の手順をユーザーに示す（[マージの後](#after-merge)） | — |

起動テストで基準を満たさないときは、`run_eval.py` の `--description` で description の案を試し、合格した案を `SKILL.md` に書く。直すのは 2 回まで。起動すべきでない依頼の誤起動が残れば、明示だけ（C2）への切り替えを、`brainstorming` などに取られる依頼が残れば、SKILL_ROUTING への 1 行の追加を、ユーザーに確かめる。

<a name="trigger-queries"></a>

## 起動テストの依頼文

依頼文には、description の例と同じ言い回しを使わない。例をなぞると合格しやすくなり、言い回しが違うときに起動するかを測れないため。

起動すべき依頼（10 件）:

1. 来月から新規プロダクトの立ち上げプロジェクトが始まる。メンバーは私を含めて 4 人、3 月末にβ版を出すのがゴール。何から手をつければいい？（`brainstorming` と競合する）
2. 来週、関係部署を集めて初回の打ち合わせをする。6 月の契約更新までに終える案件で、目的と体制とスケジュールをどう説明するか一緒に詰めたい
3. 決済基盤の移行が予定より 3 週間遅れていて、残りは 2 か月。スコープを削るか期限を交渉するか、どう進めるべきか相談したい
4. 社内の基幹システム刷新（3 部署・ベンダー 2 社、期間 1 年）で、起こりうる問題と、その備えを一覧にしたい
5. 進行中のプロジェクトの状況をまとめた。設計は完了、実装は 6 割、外部 API の仕様がまだ確定していない。この後の進め方と、判断が必要なことを整理して
6. 前回整理したプロジェクトの状況を見直したい。先週から仕様変更が 1 件入り、担当者が 1 人抜けた
7. 4 月リリースのモバイルアプリ刷新プロジェクトの全体のタスクを洗い出して、マイルストーンを置いて
8. 経営からの依頼で、半年で新しい SaaS を立ち上げることになった。PM としてまず何を決めるべきか整理したい
9. 3 社合同のデータ連携プロジェクト（期限は来年度の頭）で関係者が多く、誰に何をいつ共有すべきか整理できていない。共有の計画を作りたい
10. プロジェクトの終わりに向けて、残作業の棚卸しと引き継ぎに抜けがないか見てほしい

起動すべきでない依頼（11 件）:

1. このチケットを実装のタスクに分解して。「ユーザー一覧に CSV エクスポートを追加する。対象は管理者のみ」
2. 今日やることを整理したい。レビュー 2 件、障害の調査、定例の資料づくり。優先順位をつけて
3. この PR の変更のリスクは？ マイグレーションで既存データが壊れないか心配
4. この API の設計案のリスクを洗い出して。認証のヘッダーと、ページネーションの方式を変える案
5. テストが通るようになった。この後何をすべき？
6. 新しい社内ツールを作るべきか迷っている。そもそも作る価値があるか一緒に考えて（`/office-hours` の担当）
7. ユーザー招待機能の要件を整理して、設計まで進めたい（`brainstorming` の担当）
8. この設計書をもとに実装の計画を書いて（`writing-plans` の担当）
9. 先週のコミットと PR を振り返りたい（`/retro` の担当）
10. 三点見積もりの式と、PERT との違いを教えて
11. このプロジェクトのコードベースのセキュリティ上のリスクを洗い出して（「このプロジェクト」がリポジトリを指す）

<a name="eval-criteria"></a>

## 合格の基準

`run_eval.py` は 1 件を 3 回実行し、起動した割合が 0.5 以上なら「起動した」と判定する。

- 起動すべきでない依頼: 11 件すべてが割合 0.5 未満。1 回でも起動した依頼は、割合とともに記録する。
- 起動すべき依頼: 8 件以上が割合 0.5 以上。
- `run_eval.py` は最初のツール呼び出しだけを見るので、ほかのスキルを先に起動した依頼は「起動しない」と数える。どのスキルに取られたかは結果から分からないので、外れた依頼は、リンクの後にユーザーに新しいセッションで 1 回試してもらう（任意）。

<a name="eval-commands"></a>

## 実行のコマンド

ユーザーが通常のターミナルで実行する。`claude -p` が sandbox の中では動かない見込みのため。`run_eval.py` は Python 3.10 以上の書き方を使うので、`/usr/bin/python3`（3.9）ではなく PATH の `python3` を使う。一時ファイルは、カレントディレクトリから上にたどって最初に `.claude/` がある場所に書かれる。そのため、sandbox から書けない専用のディレクトリ（`~/pm-assist-eval`）から実行する。

1. 準備と、2 件だけの試し（`claude -p` が止まらずに動くかを確かめる）:

   ```sh
   mkdir -p ~/pm-assist-eval/.claude
   cd ~/pm-assist-eval && WT=~/dotfiles/.claude/worktrees/pm-assist && SC=$(ls -d ~/.claude/skills/synced/*/skill-creator | head -1) && [ -n "$SC" ] \
     && jq '.[0:1] + .[10:11]' "$WT/docs/work/20261126_pm-assist-skill/assets/trigger-eval.json" > smoke.json \
     && PYTHONPATH="$SC" python3 -B -P -m scripts.run_eval --eval-set smoke.json --skill-path "$WT/claude/skills/pm-assist" --model claude-opus-5-5 --runs-per-query 1 --num-workers 1 --timeout 90 --verbose > smoke-result.json
   ```

2. 本番（21 件 × 3 回）:

   ```sh
   cd ~/pm-assist-eval && WT=~/dotfiles/.claude/worktrees/pm-assist && SC=$(ls -d ~/.claude/skills/synced/*/skill-creator | head -1) && [ -n "$SC" ] \
     && PYTHONPATH="$SC" python3 -B -P -m scripts.run_eval --eval-set "$WT/docs/work/20261126_pm-assist-skill/assets/trigger-eval.json" --skill-path "$WT/claude/skills/pm-assist" --model claude-opus-5-5 --runs-per-query 3 --num-workers 1 --timeout 90 --verbose > result-2.json
   ```

   どちらの手順も、単独で実行できるように `cd` と変数の定義から始め、skill-creator が見つからなければ止める。`-P`（Python 3.11 以上）は、カレントディレクトリを読み込み先から外す。`-m` は既定でカレントディレクトリを `PYTHONPATH` より先に探すので、sandbox から書けるディレクトリ（worktree など）で実行すると、そこに置かれた `scripts/run_eval.py` が sandbox の外で動くため（`/review` の敵対的レビューの指摘）。実際の実行は、`-P` のない形で `~/pm-assist-eval`（`scripts/` はない）から行った。

   `--num-workers` は 1 にする。2 以上にすると、並行して動くプロセスがそれぞれの一時コマンドを同じ `.claude/commands/` に置くので、各回のスキル一覧に同じ内容のコマンドが ID 違いで並ぶ。Claude がほかのプロセスのコマンドを選ぶと、起動したのに「起動しない」と数えられる（1 回目の本番を `--num-workers 5` で実行して分かった。[test-report.md](test-report.md) に記録する）。

Claude は `~/pm-assist-eval/*.json` を読んで記録する。ここで実行されるのは `~/.claude/skills/synced/` の skill-creator のコード（sandbox から書けない）と `claude` だけで、リポジトリの中のファイルは JSON と SKILL.md をデータとして読むだけ。

<a name="output-check"></a>

## 出力の確認

リンクの後、このセッションで `pm-assist` を起動して、次の 2 件を試す。起動の判定ではなく、中身の形を見る。

| 依頼 | 見ること |
| --- | --- |
| 3 人で 2 か月の社内ツールの立ち上げ。ゴールは経理部の月次作業の半減 | 軽量型と判定する。WBS・RACI・ステークホルダー登録簿を出さない。リスクの節がある。質問が 5 件以内。次のアクションが 3〜7 個。判断事項に、元に戻せるかと決める人がある |
| ベンダー 2 社と 3 部署が関わる刷新が 3 週間遅れている | 立て直しのフェーズと判定する。課題・依存がリスクと分かれている。権限の外のリスクにエスカレーションを挙げる |

<a name="repo-checks"></a>

## リポジトリの検査

リポジトリの CLAUDE.md の「規約」のうち、設定ファイル・Markdown を変えたときのもの。フックとスクリプトは変えないので、それらのテストは対象外。

- `python3 -B .github/scripts/check-repo.py`
- `python3 -B .github/scripts/test-check-repo.py`
- `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' | xargs -0 shellcheck -S warning`
- `actionlint`
- `zizmor --offline .`
- `mise run claude:skills-check`

<a name="commits"></a>

## コミットの分け方

1. `docs: add research and plan for the pm-assist skill`（調査と plan）
2. `feat(claude): add pm-assist skill`（3 つのファイルと `trigger-eval.json`）
3. `docs(claude): sync skill docs with pm-assist`（棚卸し・チートシート・スナップショット）
4. `docs: record pm-assist trigger and output tests`（`test-report.md`。作業文書の `status` を `done` にする）

<a name="after-merge"></a>

## マージの後

ユーザーが通常のターミナルで行う。

1. リンクを張る: `ln -s ~/dotfiles/claude/skills/pm-assist ~/.claude/skills/pm-assist`（`~/dotfiles` を main に更新した後。一時リンクは `/review` の後に外したので、張り替えではなく新しく張る）
2. 新しいセッションを始め、`/pm-assist` が `/` のメニューに出ることと、[起動すべき依頼](#trigger-queries)の 1 番で起動することを確かめる。
3. 確かめてから worktree を消す。

<a name="risks"></a>

## リスクと戻し方

- **誤起動**: 起動テストで測る。残れば明示だけ（C2）に切り替える。
- **一時リンクで守りの境界が動く**: リンク先の worktree の `claude/` は、`~/dotfiles` で起動したセッションからは書き込みを止められていない見込み（`/review` の Red Team と敵対的レビューの指摘。未検証）。dotfiles の denyWrite（`./claude`）と Edit の ask は `~/dotfiles/claude` にしか当たらないため。書き換えられると、全セッションで自動起動するスキルに指示を仕込める。出力の確認の後にリンクを外して閉じ、マージの直後に `~/dotfiles` に張る（2026-11-26 にユーザーが判断）。恒久策（worktree の `claude/` を守る設定）は、設定の変更なので別の Issue で扱う。
- **起動テストの費用**: `claude -p` を 65 回実行する。description を直すと、1 回につき 63 回増える（最大 191 回）。並行の不具合で本番が 2 回（126 回）無効になったので、実際は試しを含めて 191 回動いた。
- **測定の期間との重なり**: 規則の効果の測定（〜2026-12-07）の途中で、自動で起動するスキルを足す。`brainstorming` に行くはずの依頼を取ると、計画系のスキルの起動の数が変わりうるので、棚卸しの測定の節に日付とともに 1 文残す（前例: 2026-11-23 の `modern-web-guidance`）。
- **skill-creator の助言を採らない点**: 起動しにくいので description を押しの強い書き方にする、という助言は、誤起動を避けたいので採らない。棚卸しの重複と裁定では、Claude Code の改善の補完は `writing-skills` だが、起動を測る手段がないので、今回は `run_eval.py` だけを使う（[F1](research-improvements.md#f1)）。表は変えない。
- **戻し方**: ユーザーが `rm ~/.claude/skills/pm-assist` でリンクを消し、PR を revert する。設定ファイルは変えないので、ほかに戻すものはない。

PR の中身はスキルの文面と文書で、設定・フック・権限は変えない。一時リンクで守りの境界が動く点は、リンクを外して閉じた。そのため Codex のレビューは提案しない。
