---
status: done
created: 2026-11-26
---

# pm-assist スキルの改善点と参照の検討

参考元の pm-assist スキルをそのまま入れず、直すところと、足す・削る参照を決めるための調査。各候補に、根拠・得られること・増える重さ・推奨を書く。

<a name="related"></a>

## 関連

- 参考元: ローカルにある他の dotfiles の pm-assist スキル。非公開の見込みで LICENSE もないので、この文書には中身の詳細（行番号・文面・定義）を載せず、考え方と構成だけを参考にする。
- [Issue #121 Notion の公式 MCP サーバーの導入](https://github.com/kado-ta/dotfiles/issues/121)
- [スキルの規則](../../../claude/rules/SKILL_ROUTING.md)、[文書の置き場所](../../../claude/rules/DOCUMENTS.md)、[スキルの棚卸し](../../../claude/SKILL_INVENTORY.md)

<a name="summary"></a>

## 推奨の一覧

| ID | 候補 | 推奨 |
| --- | --- | --- |
| [A1](#a1) | PMBOK を第 8 版に合わせる。原則の列挙と第 6 版の知識エリアを削り、第 8 版の 7 領域に沿った自前の問いにする | 入れる |
| [A2](#a2) | リスク対応の型にエスカレーションを足す | 入れる |
| [A3](#a3) | プレモーテムの出典を書き、Paper Tiger の定義を直す | 入れる |
| [A4](#a4) | 見積もりの幅は、決めることを決めないと狭まらないと書く（不確実性コーン。数値は入れない） | 入れる |
| [B1](#b1) | 不確実性の性質で進め方を選ぶ（Cynefin を簡略化して使う） | 入れる |
| [B2](#b2) | リスクの節を RAID の分類で組み直し、課題と依存を足す | 入れる |
| [B3](#b3) | 判断事項に「元に戻せるか」と「決める人は 1 人」を足す | 入れる（DACI の 4 役割は入れない） |
| [B4](#b4) | 見積もりでは、先に類似案件の実績を聞く（参照クラス予測） | 入れる |
| [B5](#b5) | RICE を削り、MoSCoW を DSDM の定義に合わせる | 入れる |
| [C1](#c1) | description を「プロジェクトの運営」に絞り、起動しない例を書く | 入れる |
| [C2](#c2) | 明示でしか起動しないようにする（`disable-model-invocation: true`） | 入れない（起動テストで誤起動が残れば切り替える） |
| [C3](#c3) | SKILL_ROUTING の Overlapping skills に境界を足す | 入れない（棚卸しの「重複と裁定」に書く） |
| [D1](#d1) | 資料の読み方を一般化する（Slack とチケットを前提にしない） | 入れる |
| [D2](#d2) | 保存は頼まれたときだけにし、置き場所は DOCUMENTS.md の作業文書にする | 入れる |
| [D3](#d3) | グローバルの CLAUDE.md と重なる原則をスキルに書かない | 入れる |
| [E1](#e1) | 雛形を 3 つから 2 つにまとめる | 入れる |
| [E2](#e2) | セルフチェックを、現状把握の確認項目にまとめる | 入れる |
| [E3](#e3) | フェーズ別の重点成果物の表を削る | 入れる |
| [E4](#e4) | リスクの節を省かない規則は残し、量を案件の大きさに合わせる | 入れる |
| [F1](#f1) | 起動の検証に skill-creator の `run_eval.py` だけを使う | 入れる |
| [G1](#g1) | リンクを worktree に一時的に張り、マージの後に張り替える | 入れる |

すべて入れた場合の見込みの行数は、`SKILL.md` が約 90 行、`REFERENCE.md` が約 90 行、`TEMPLATES.md` が約 70 行。

<a name="freshness"></a>

## A. 参照の新しさ

<a name="a1"></a>

### A1. PMBOK を第 8 版に合わせる

- **根拠**:
  - 参考元では、PMBOK の 2 つの版の枠組みが混ざっていた。第 7 版で、第 6 版の知識エリアはパフォーマンス領域に置き換わっている。
  - PMI の公式ページによると、現行は第 8 版で、6 つの原則と 7 つのパフォーマンス領域（governance・scope・schedule・finance・stakeholders・resources・risk）からなる。第 7 版の原則と領域の土台を保ちつつ、プロセスの指針を規範的でない形で戻し、AI・PMO・調達の記述を広げた（[PMBOK Guide](https://www.pmi.org/standards/pmbok)。ページは WebFetch とブラウザのどちらでも 403 で、内容は pmi.org に絞った検索結果の抜粋で確かめた）。第 2 刷の正誤表も出ている（[errata](https://www.pmi.org/-/media/pmi/documents/public/pdf/pmbok-standards/pg8-errata---second-printing.pdf)）。
  - 7 つの領域の名前は、ユーザーがブラウザで PMI の公式ページを開いて確かめた（2026-11-26）。
  - 6 つの原則の英語名（Adopt a holistic view・Focus on value・Embed quality・Lead accountably・Integrate sustainability・Build empowered teams）と、2025 年 11 月の発行は、PMI の公式ページを出典にした企業のブログで確かめた（[RJC、2026-10-07](https://www.r-jc.jp/news-blog/4673/pmbok%E7%AC%AC7%E7%89%88%E3%81%A8%E7%AC%AC8%E7%89%88%E3%81%AE%E4%B8%80%E8%A6%A7%E5%8E%9F%E5%89%87%E3%83%91%E3%83%95%E3%82%A9%E3%83%BC%E3%83%9E%E3%83%B3%E3%82%B9%E9%A0%98%E5%9F%9F%E3%81%AE%E5%AF%BE%E5%BF%9C%E8%A1%A8/)）。日本語の名前は、どのブログも独自の訳（仮訳）。
  - 第 7 版から第 8 版への対応（不確実性の領域はリスクの領域に、チームは資源に入った、など）は、2 つのブログが整理した目安で、PMI の公式の対応表ではないと明記されている（同上、[ビジネクスト、2026-08-12](https://www.busi-next.com/blog/pmbok8-performance-domains)）。品質は原則（Embed quality）に入り、コミュニケーションを扱う領域はない、とする整理もブログのもの。
  - 5 つの Focus Areas（と 40 のプロセス）は、二次情報だけで確かめた（ビジネクスト、[シドニー大学の記事](https://cce.sydney.edu.au/article/project-management-is-changing) など）。
- **得られること**: 版の混在がなくなる。原則の名前の一覧は行動に結びつかないので、削っても判断は変わらない。
- **増える重さ**: 減る。
- **推奨**: 入れる。第 8 版の 7 領域の名前を見出しにして、抜けを見つける問いを自分の言葉で書く。品質（完了の定義）・コミュニケーション・調達は 7 領域の名前にないが、実務で抜けやすいので、自前の問いとして残す。6 原則の名前は書かない（行動に結びつかず、確かめたのも二次情報のため）。第 8 版の本文は著作物なので、用語の名前のほかは引用しない。

<a name="a2"></a>

### A2. リスク対応の型にエスカレーションを足す

- **根拠**: 参考元の対応の型には、エスカレーションがなかった。PMBOK 第 6 版でエスカレーション（プロジェクトの権限の外にあるリスクを、上の判断者に渡す）が加わり、5 つになった（二次情報: [projectmanagement.com のブログ](https://www.projectmanagement.com/blog-post/36882/pssst--sustainability-is-hiding-in-the-sixth-edition---part-2-of-2-)、[4PMTI](https://www.4pmti.com/?p=1005819)）。
- **得られること**: 他部署や経営の判断が要るリスクの扱い先を書ける。チームマネジメントと組織づくりを担う PM には、ここがいちばん効く。
- **増える重さ**: 表に 1 行。
- **推奨**: 入れる。好機への対応（活用・強化・共有・受容・エスカレーション）も 1 行で書く。

<a name="a3"></a>

### A3. プレモーテムの出典を書き、Paper Tiger の定義を直す

- **根拠**:
  - プレモーテムは Klein の手法で、計画の段階で「このプロジェクトは失敗した」と仮定し、もっともらしい理由を挙げる（[HBR 2007 年 9 月号](https://hbr.org/2007/09/performing-a-project-premortem)。有料の壁の手前の要約で確かめた）。参考元には出典がなかった。
  - Tiger / Paper Tiger / Elephant の分類は Doshi が示したもの（[Medium、2020-04-02](https://medium.com/@shreyashere/how-to-use-pre-mortems-to-prevent-problems-blunders-and-disasters-6ecc6df6e22a)。WebFetch は 403 だったので、ユーザーがブラウザで保存した PDF の本文で確かめた）。記事は Klein の HBR の記事を必読として挙げている。
  - Paper Tiger は、ほかの人は心配しているかもしれないが、挙げた本人は心配していない脅威で、たいていは本人が担当し、抑えられていると強く確信しているもの。Elephant は、脅威とは限らないが、誰も話題にしていないことが心配なもの。参考元の Paper Tiger の定義には、挙げた本人の確信という観点がなかった。3 つの定義の表は画像で、本文の文字には入っていないので、Tiger の定義は本文の「重大な問題」という書き方から読み取った。
  - 記事は、対策を上位の Tiger と Elephant に絞り、1 件ごとに責任者を 1 人決め、プロジェクトの計画に組み込んで追うとしている。参考元にあった Tiger の緊急度の区分は、記事の本文にはなかった。
- **得られること**: 出典どおりの使い方になる。Paper Tiger を、データで否定して片づけるものとして扱うと、ほかの人の心配を切り捨てる使い方になりやすい。本人の確信として扱えば、担当と根拠を示して、ほかの人の心配に答えられる。
- **増える重さ**: なし。
- **推奨**: 入れる。出典を Klein と Doshi と書き、Paper Tiger の定義を記事に合わせる。緊急度の区分は、出典がないので入れない。

<a name="a4"></a>

### A4. 見積もりの幅は、決めることを決めないと狭まらない

- **根拠**:
  - 参考元にも、不確実な段階の見積もりを幅で示す考え方はあった。
  - McConnell は、コーンは決めごとで変動の元を取り除いたときにだけ狭まり、そうしないと終わりまで不確実さが雲のように残ると書いている（[Construx の白書、2010 年](https://www.construx.com/wp-content/uploads/2019/02/CxWhitePaper_ConeOfUncertainty.pdf)。保存した PDF から本文を抜き出して確かめた）。
  - Little は、実際のプロジェクトの記録では見積もりの誤差の幅が期間を通してほぼ変わらなかったと報告している（IEEE Software 23(3), 2006, [doi:10.1109/MS.2006.82](https://doi.org/10.1109/MS.2006.82)。抄録を検索結果で確かめた）。
- **得られること**: 幅を示すだけでなく、幅を狭めるために決めること・調べることをタスクとして挙げられる。
- **増える重さ**: `REFERENCE.md` に 1〜2 行。
- **推奨**: 入れる。コーンの図や「初期は 0.25 倍〜4 倍」の数値は入れない。最善の場合の値で、実データでは合わないという報告があるため。

<a name="better-references"></a>

## B. よりよい参照

<a name="b1"></a>

### B1. 不確実性の性質で進め方を選ぶ

- **根拠**:
  - 参考元のテーラリングは規模の軸だけで、答えが事前に分かるかどうかの軸がなかった。
  - Cynefin は、状況を Clear・Complicated・Complex・Chaotic・Confused（Aporetic）に分け、領域ごとに取る手を変える。Complex では、パターンは行動とつながりから現れ、後から見て分かることが多いので、探り・感じ取り・対応する（[The Cynefin Co、2024 年](https://thecynefin.co/effective-decision-making-support-tool/)。本文で確かめた）。原典は Snowden と Boone（[HBR 2007 年 11 月号](https://hbr.org/2007/11/a-leaders-framework-for-decision-making)。有料の壁で要約しか読めなかった）。
- **得られること**: 新規プロダクトの立ち上げのように、やってみないと分からない案件で、細かいタスク分解より、仮説と小さな検証をマイルストーンにする案を出せる。ユーザーの担当（新規プロダクトの立ち上げ）に直接効く。
- **増える重さ**: `SKILL.md` に 3〜4 行、`REFERENCE.md` に短い表。
- **推奨**: 入れる。5 つの領域名と手順の名前は使わず、「答えが分かっている」「調べれば分かる」「やってみないと分からない」「すぐ止血が要る」の 4 つで判定する。規模の軸（軽量型・エンプラ型）とは別の軸として足す。

<a name="b2"></a>

### B2. リスクの節を RAID の分類で組み直す

- **根拠**:
  - 参考元の分類では、すでに起きている問題（課題）と、ほかのチームや外部への待ち（依存）が、独立していなかった。
  - RAID（Risks・Assumptions・Issues・Dependencies）は実務の慣習で、単一の一次出典は見つからなかった（二次情報: [Rework](https://resources.rework.com/libraries/project-management/raid-log)、[Asana](https://asana.com/resources/raid-log)。D を Decisions とする流儀もある）。
- **得られること**: 進行中や立て直しのときに、起きている問題と待ちを、まだ起きていないリスクと分けて追える。
- **増える重さ**: 雛形の見出しが 2 つ増える。
- **推奨**: 入れる。RAID という名前には頼らず、リスク・前提・課題・依存に、「分かっていないこと」を加えた 5 つで書く。決めることは [B3](#b3) の判断事項に分ける。

<a name="b3"></a>

### B3. 判断事項に「元に戻せるか」と「決める人は 1 人」を足す

- **根拠**:
  - Bezos は、元に戻せない決定（one-way door。Type 1）は慎重にゆっくり決め、戻せる決定（two-way door。Type 2）は判断力のある個人か小さなグループがすばやく決めるべきで、すべてに重い手順を使うと遅くなり、試すことが減ると書いている（[Amazon の 2015 年度の株主への手紙](https://ir.aboutamazon.com/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF)。PDF の本文で確かめた）。翌年の手紙では、多くの決定は欲しい情報の 7 割ほどで決めるべきとしている（[2016 年度の手紙](https://www.aboutamazon.com/news/company-news/2016-letter-to-shareholders)。本文で確かめた）。
  - DACI では、決める人（Approver）を 1 人にすると強調している（[Atlassian Team Playbook](https://www.atlassian.com/team-playbook/plays/daci)。本文で確かめた）。
  - 参考元の判断事項には、元に戻せるかの観点がなかった。
- **得られること**: 判断事項ごとに、どこまで調べてから決めるかを変えられる。決める人が複数いる、あるいはいない状態を見つけられる。
- **増える重さ**: 判断事項の表に 1 列と、説明 1 行。
- **推奨**: 入れる。DACI の 4 役割すべては入れない（チームをまたぐ決定のときの選択肢として、`REFERENCE.md` で 1 行触れる）。Atlassian のページが McKinsey の調査として挙げる「成功率が 25% 高い」は確かめられないので使わない。

<a name="b4"></a>

### B4. 見積もりでは、先に類似案件の実績を聞く

- **根拠**:
  - 参照クラス予測は、似たプロジェクトの群の実績をもとに予測し、楽観バイアスと戦略的な虚偽を避ける（Flyvbjerg, Project Management Journal 37(3), 2006。[著者による公開版の抄録](https://arxiv.org/abs/1302.3642) を検索結果で確かめた。PMI の版は 403）。
  - 参考元では、似た案件の実績は、見積もりの技法の 1 つとして挙げるだけだった。
- **得られること**: 見積もりの相談で「過去の似た案件はどれくらいかかったか」を最初に聞く、という具体的な行動になる。
- **増える重さ**: `REFERENCE.md` に 1〜2 行。
- **推奨**: 入れる。三点見積もりは残す。

<a name="b5"></a>

### B5. RICE を削り、MoSCoW を DSDM の定義に合わせる

- **根拠**:
  - RICE は製品のロードマップの優先度付けの手法として書かれている（[Intercom、2018 年](https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers)。本文で確かめた）。何を作るかの判断は `/office-hours` の担当（[SKILL_ROUTING](../../../claude/rules/SKILL_ROUTING.md#overlapping-skills)）。
  - MoSCoW の W は「今回はやらない（Won't Have this time）」で、Must の工数は全体の 6 割以下が目安とされる（[Agile Business Consortium](https://www.agilebusiness.org/resource/what-is-moscow-prioritization/)。本文で確かめた）。参考元には、割合の目安がなかった。
- **得られること**: 製品の判断に踏み込まない。「今回は」と 6 割の目安で、スコープを交渉する根拠が具体的になる。
- **増える重さ**: 減る。
- **推奨**: 入れる。Impact × Effort は残す。

<a name="triggering"></a>

## C. 起動条件

<a name="c1"></a>

### C1. description を「プロジェクトの運営」に絞る

- **根拠**:
  - 参考元の description は日本語の文章で、開発中の会話にもふつうに出てくる汎用の言い回しを起動語に入れていた。
  - Claude は description で自動起動を判断し、description と `when_to_use` を合わせて 1,536 文字で切られる（[Claude Code の Skills](https://code.claude.com/docs/en/skills)。原文で確かめた）。
  - `superpowers:brainstorming` の description は「planning anything new, in software or out of it (a talk, a business, a renovation)」を含み、新規の立ち上げの相談と競合する。
  - 近くの個人スキルの description は、英語の「Use when …」に日本語の例を添える形（`salesforce-help`・`commit-staged-pr` など）。
- **得られること**: 開発中の会話での誤起動が減る。
- **増える重さ**: なし。
- **推奨**: 入れる。近くのスキルに合わせて英語で書き、日本語の例を添える。起動しない例（チケット 1 枚や日々のタスクの分解、開発中のコード変更のリスク、何を作るか、機能の要件、実装の計画）を書く。たたき台は次のとおり（plan で詰める）。

  ```text
  Use when the user asks for help running a project — a time-boxed effort with a goal and a deadline — such as organizing a new project or product launch, preparing a kickoff, reviewing progress, recovering a slipping project, or listing a project's risks and next steps (e.g. 「ローンチまでの進め方を整理したい」「キックオフまでに決めておくことを洗い出して」「遅れている案件の立て直しを相談したい」). Not for breaking down a single ticket or daily tasks, the risks of a code change under development, deciding what to build (/office-hours), feature requirements (brainstorming), or implementation plans (writing-plans).
  ```

<a name="c2"></a>

### C2. 明示でしか起動しないようにする

- **根拠**: `socratic-tutor` は、日本語での誤起動を避けるため `disable-model-invocation: true` にしている（[棚卸し](../../../claude/SKILL_INVENTORY.md#crit)）。この項目を true にすると、Claude は自動で読み込まない（[Claude Code の Skills](https://code.claude.com/docs/en/skills)）。
- **得られること**: 誤起動がなくなる。スキルの一覧のコンテキストも減る。
- **失うこと**: 「プロジェクトの進め方を相談したい」と書いても起動しない。`/pm-assist` を覚えて打つ必要がある。
- **推奨**: 入れない。自動起動を基本にし、[C1](#c1) で絞る。[F1](#f1) の起動テストで、起動すべきでない依頼が閾値（3 回中 2 回以上）を超えて起動し、description の修正で直らなければ、こちらに切り替える。

<a name="c3"></a>

### C3. SKILL_ROUTING に境界を足す

- **根拠**: SKILL_ROUTING は全プロジェクトで毎回読み込まれるので、変える行を最小にする（[sync-skill-docs の手順 6](../../../.claude/skills/sync-skill-docs/SKILL.md#steps)）。棚卸しの「重複と裁定」は毎回は読み込まれない（[棚卸し](../../../claude/SKILL_INVENTORY.md#overlaps)）。
- **得られること（足した場合）**: `brainstorming` や `/office-hours` との振り分けを、毎回の規則で強められる。
- **増える重さ（足した場合）**: 全セッションで 1 行。
- **推奨**: 最初は入れない。境界は description（[C1](#c1)）と、棚卸しの「重複と裁定」に書く。[F1](#f1) の起動テストで、`brainstorming`・`/office-hours`・`writing-plans` に取られる依頼があったときに 1 行足す。

<a name="environment"></a>

## D. 環境との整合

<a name="d1"></a>

### D1. 資料の読み方を一般化する

- **根拠**:
  - 参考元は、特定のツールの資料を MCP で読む前提で書かれていた。
  - この環境では、Notion MCP は検討中で入っていない（[Issue #121](https://github.com/kado-ta/dotfiles/issues/121)）。sandbox の `gh` は読み取り専用のトークンで動く（読むには足りる）。ログインの要るページは WebFetch で読めない。
- **得られること**: 読めない資料を推測で埋めない。
- **増える重さ**: なし（書き換えのみ）。
- **推奨**: 入れる。「渡されたリンクは、使える手段（`gh`・MCP・WebFetch）で読む。読めなければ要点の貼り付けを頼む」と書く。Notion の名前は書かない（#121 で入れば、そのまま読めるようになる）。

<a name="d2"></a>

### D2. 保存は頼まれたときだけにする

- **根拠**:
  - 参考元は保存先を決めていなかった。2 回目以降に前回との差分を見るには、前回の結果が要る。
  - DOCUMENTS.md では、作業完了までの文書は `docs/work/<ID>_<slug>/` に置き、ファイル名は種別だけ（`plan.md` など）にする（[文書の置き場所](../../../claude/rules/DOCUMENTS.md)）。
- **得られること**: 頼まれない限りファイルを増やさない。保存するときは既存の規則に乗る。
- **増える重さ**: `SKILL.md` に 2 行。
- **推奨**: 入れる。既定はチャットに出すだけにする。保存を頼まれたら、リポジトリの規則に従い、なければ `docs/work/<ID>_<slug>/plan.md`（`status: in-progress`。見直しは日付つきの節を足す）に置く。2 回目以降で前回の結果が手元になければ、貼り付けを頼む。DOCUMENTS.md には「生きたプロジェクト管理の記録」の種別がないので、新しいファイル名の種別は作らない。

<a name="d3"></a>

### D3. グローバルの CLAUDE.md と重なる原則を書かない

- **根拠**: グローバルの CLAUDE.md は毎回読み込まれ、推奨案と理由を示すことと、事実・推測・提案を分けることを定めている。参考元の原則のうち 2 つ（補佐に徹すること、事実と推測を分けること）は、これと重なる。
- **得られること**: `SKILL.md` が短くなる。規則が 2 か所に分かれて食い違うことがない。
- **増える重さ**: 減る。
- **推奨**: 入れる。このスキルに固有の原則（リスクを出さずに終わらない、目的を問う、プロセスを押し付けない、2 回目以降は差分から見る、先回りして共有する）だけを残す。判断事項の雛形の「推奨と理由」の欄は、構造として残す。

<a name="trim"></a>

## E. 削るもの

<a name="e1"></a>

### E1. 雛形を 3 つから 2 つにまとめる

- **根拠**: 参考元の軽量型とエンプラ型の雛形は、節の大半が同じだった。
- **得られること**: 雛形の重複がなくなり、軽い案件で重い節を出しにくくなる。
- **増える重さ**: 減る（雛形が 1 つ減る）。
- **推奨**: 入れる。1 つの雛形に「エンプラ型で足す節」を注記し、2 回目以降の見直し用の雛形を残す。

<a name="e2"></a>

### E2. セルフチェックを現状把握の確認項目にまとめる

- **根拠**: 参考元のセルフチェックは、現状把握の確認項目とほぼ同じ内容だった。
- **得られること**: 同じことを 2 回書かない。
- **増える重さ**: 減る。
- **推奨**: 入れる。現状把握の表を「出す前にも確かめる」と 1 行添える。

<a name="e3"></a>

### E3. フェーズ別の重点成果物の表を削る

- **根拠**: 参考元のフェーズ別の成果物の表は、フェーズごとの焦点の表と雛形と重なっていた。
- **得られること**: 参照ファイルが短くなる。
- **増える重さ**: 減る。
- **推奨**: 入れる。

<a name="e4"></a>

### E4. リスクの節を省かない規則は残し、量を合わせる

- **根拠**: 参考元は、タスクの整理だけを頼まれてもリスクの節を省かない一方で、プロセスを押し付けないことも原則にしていた。
- **得られること**: このスキルの価値の中心（タスクの整理だけで終わらない）を保ちつつ、軽い依頼で長いリスクの表を出さない。
- **増える重さ**: なし。
- **推奨**: 入れる。軽い依頼では上位 3 件と次のアクションだけにする。

<a name="verification"></a>

## F. 検証の方法

<a name="f1"></a>

### F1. 起動の検証に skill-creator の `run_eval.py` だけを使う

- **根拠**:
  - `run_eval.py` は、description を一時的なコマンド（`<名前>-skill-<乱数>.md`）にして、カレントディレクトリから上にたどって最初に `.claude/` がある場所の `.claude/commands/` に置く。そのうえで `claude -p` に依頼文を渡し、最初のツール呼び出しがそのスキルの起動かで判定する。既定は 1 件 3 回、閾値 0.5、モデルは `--model` で指定する（anthropic-skills の skill-creator の `scripts/run_eval.py`）。
  - `superpowers:writing-skills` は、サブエージェントに圧力をかけて規則を守るかを確かめる手法で、スキルの一覧からの選択（起動）は測らない。
  - SKILL_ROUTING は、同じ目的のスキルを重ねないとしている。
- **得られること**: ユーザーのスキル・CLAUDE.md・SessionStart のフックが全部入った本物の Claude Code で、起動すべき依頼と起動すべきでない依頼を 3 回ずつ測れる。リンクを作る前でも測れる。
- **増える重さ・制約**:
  - `claude -p` は認証に Keychain を読む見込みで、sandbox の中では動かない（推測）。通常のターミナルで実行してもらう。
  - 一時ファイルの置き場所がカレントディレクトリで決まる。リポジトリやホームで実行すると、そこの `.claude/commands/` に書く。`.claude/` だけを置いた専用のディレクトリから実行する。
  - 20 件 × 3 回 = 60 回の `claude -p` を実行する（最初のツール呼び出しで止める）。
  - 最初のツール呼び出ししか見ないので、先に `brainstorming` などを起動すると「起動しない」と数える。競合を測るにはむしろ合っている。
  - 一時ファイルはコマンドとして一覧に載り、名前も違う。本物のスキルとの差は、リンクの後の手動の確認で補う。
- **推奨**: 入れる。使うのは `run_eval.py` だけで、説明文の自動改善（`run_loop.py`）と閲覧画面は使わない。skill-creator の「起動しにくいので description を押しの強い書き方にする」という助言は、このスキルでは誤起動のほうを避けたいので採らない。起動すべき依頼には、`brainstorming` と競合する依頼（新規プロダクトの立ち上げ計画）を入れる。起動すべきでない依頼には、日々のタスク分解・チケットの分解・開発中の「リスクは？」・機能の要件・何を作るか・実装の計画を入れる。リンクの後に、このセッションで `/pm-assist` を明示して 2 件を試し、出力の形（リスクの節がある、軽い案件で WBS を出さない、質問が 5 件以内）を目で確かめる。

<a name="link-timing"></a>

## G. リンクの時期

<a name="g1"></a>

### G1. リンクを worktree に一時的に張る

- **根拠**:
  - `claude/setup.sh` は worktree の中では実行を拒む（`claude/setup.sh:19-23`）。個人スキルのリンクは `~/dotfiles` のファイルを指す（`claude/setup.sh:166-171`）ので、マージの前は `~/dotfiles` に pm-assist がない。
  - `mise run claude:skills-check` は入っている状態（`~/.claude/skills`）を見る。リンクがない間に文書へ `/pm-assist` と書くと「unknown name」で失敗する（`claude/scripts/skills-check.py:211-221`）。
  - `~/.claude/skills/` に足したスキルは、今のセッションでも読み込まれる。出ないときは `/reload-skills` を実行する（[Claude Code の Skills](https://code.claude.com/docs/en/skills)。原文で確かめた）。
- **案**:
  - A) worktree のパスに一時的にリンクする（推奨）。通常のターミナルで `ln -s <worktree>/claude/skills/pm-assist ~/.claude/skills/pm-assist` を 1 回実行してもらう。この PR の中で、`skills-check`・スナップショット・手動の確認まで済ませられる。マージの後、worktree を消す前に `ln -snf ~/dotfiles/claude/skills/pm-assist ~/.claude/skills/pm-assist` で張り替える。スナップショットはパスを持たないので、張り替えても変わらない。
  - B) マージしてから `~/dotfiles` でリンクし、文書とスナップショットと試験記録を別の PR にする。PR が 2 つになり、起動テストで description を直すと 3 つ目になりうる。
  - C) `~/dotfiles` をこのブランチに切り替える。ほかのセッションと作業ツリーを共有しているので採らない。
- **案 A のリスク**: 張り替える前に worktree を消すと、リンクが切れ、スキルが黙って消える。リンクの間は、worktree での編集が全セッションにすぐ反映される。
- **推奨**: 案 A。

<a name="unchanged"></a>

## 変えないもの

次の考え方は残す（自分の言葉で書く）。

- 6 つの段階（現状把握 → 形態の見極め → フェーズの判定 → タスク → リスク → アウトプット）。ただし決まった手順ではなく、確かめる順番として書く。
- 質問は不明で重要なものに絞り、5 件程度までにする。分かっている範囲で仮に組み、前提として示す。
- 成果物から分解する。遠い先は粗く、直近は細かくする。承認待ち・環境の準備・受け入れ・周知・リリース後の監視など、忘れられがちなタスクを確かめる。
- 確率と影響の 3 段階の評価。上位のリスクに次のアクションと担当を付ける。
- 権力 × 関心のグリッドは、エンプラ型か関係者が多いときだけ使う。
- アンチパターン（数人の案件に重い成果物を持ち込む、リスクを並べるだけで終わる、一点の見積もり、質問攻め）。

<a name="sources"></a>

## 出典と取得の状況

| 出典 | 取得 | 使った候補 |
| --- | --- | --- |
| [PMI の PMBOK Guide のページ](https://www.pmi.org/standards/pmbok) | Claude からは 403（WebFetch と Playwright）。7 つの領域の名前は、ユーザーがブラウザで確かめた | A1 |
| [RJC の第 7 版と第 8 版の対応表（2026-10-07）](https://www.r-jc.jp/news-blog/4673/pmbok%E7%AC%AC7%E7%89%88%E3%81%A8%E7%AC%AC8%E7%89%88%E3%81%AE%E4%B8%80%E8%A6%A7%E5%8E%9F%E5%89%87%E3%83%91%E3%83%95%E3%82%A9%E3%83%BC%E3%83%9E%E3%83%B3%E3%82%B9%E9%A0%98%E5%9F%9F%E3%81%AE%E5%AF%BE%E5%BF%9C%E8%A1%A8/) | 本文で確かめた（企業のブログ。PMI の公式ページを出典にしている） | A1 |
| [ビジネクストの第 8 版の領域の解説（2026-08-12）](https://www.busi-next.com/blog/pmbok8-performance-domains) | 本文で確かめた（企業のブログ） | A1 |
| [Klein、HBR 2007 年 9 月号](https://hbr.org/2007/09/performing-a-project-premortem) | 有料の壁。要約だけ | A3 |
| [Doshi のプレモーテムの記事（2020-04-02）](https://medium.com/@shreyashere/how-to-use-pre-mortems-to-prevent-problems-blunders-and-disasters-6ecc6df6e22a) | Claude からは 403。ユーザーがブラウザで保存した PDF の本文で確かめた（定義の表は画像で読めない） | A3 |
| [McConnell、Construx の白書（2010 年）](https://www.construx.com/wp-content/uploads/2019/02/CxWhitePaper_ConeOfUncertainty.pdf) | PDF の本文で確かめた | A4 |
| [Little、IEEE Software 2006](https://doi.org/10.1109/MS.2006.82) | 抄録を検索結果で確かめた | A4 |
| [The Cynefin Co（2024 年）](https://thecynefin.co/effective-decision-making-support-tool/) | 本文で確かめた | B1 |
| [Snowden と Boone、HBR 2007 年 11 月号](https://hbr.org/2007/11/a-leaders-framework-for-decision-making) | 有料の壁。要約だけ | B1 |
| [Amazon の 2015 年度の手紙](https://ir.aboutamazon.com/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF) | PDF の本文で確かめた | B3 |
| [Amazon の 2016 年度の手紙](https://www.aboutamazon.com/news/company-news/2016-letter-to-shareholders) | 本文で確かめた | B3 |
| [Atlassian の DACI](https://www.atlassian.com/team-playbook/plays/daci) | 本文で確かめた | B3 |
| [Flyvbjerg、PMJ 2006（著者の公開版）](https://arxiv.org/abs/1302.3642) | 抄録を検索結果で確かめた（PMI の版は 403） | B4 |
| [Intercom の RICE（2018 年）](https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers) | 本文で確かめた | B5 |
| [Agile Business Consortium の MoSCoW](https://www.agilebusiness.org/resource/what-is-moscow-prioritization/) | 本文で確かめた | B5 |
| [Claude Code の Skills](https://code.claude.com/docs/en/skills) | 原文で確かめた（`when_to_use`、1,536 文字、`disable-model-invocation`、500 行、セッション中の読み込み） | C1、C2、G1 |
| RAID の出典（Rework・Asana など） | 二次情報だけ。単一の一次出典は見つからなかった | B2 |
| PMBOK 第 6 版のエスカレーション（projectmanagement.com・4PMTI） | 二次情報だけ | A2 |

<a name="decisions"></a>

## 決めてほしいこと

1. 推奨の一覧のうち、採らないもの。
2. 自動起動（[C1](#c1)）と明示だけ（[C2](#c2)）のどちらを基本にするか。
3. リンクの方法（[G1](#g1) の案 A・B）。
4. 起動テスト（[F1](#f1)）を、通常のターミナルで実行してもらえるか。
