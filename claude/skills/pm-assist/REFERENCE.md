# pm-assist の参照

[SKILL.md](SKILL.md) から、要る節だけを読む。

<a name="coverage"></a>

## 抜けを見つける問い

PMBOK ガイド第 8 版の 7 つのパフォーマンス領域を見出しにした。問いはこのスキルの言葉で、全部に答える必要はない。軽量型では Scope・Schedule・Stakeholders・Risk に絞ってよい。下の 3 行は第 8 版の領域にないが、抜けやすいので足した。

| 領域 | 問い |
| --- | --- |
| Governance | 誰が何を決めるか。変更が出たとき、誰がどう判断するか。報告はどう流れるか |
| Scope | 何を作り、何を作らないか。受け入れの基準と、受け入れる人 |
| Schedule | 依存とクリティカルパスが見えているか。余裕はどこにあるか |
| Finance | 予算の上限、超えそうなときの相談先。得られる効果と釣り合うか |
| Stakeholders | 反対しうる人、巻き込み忘れている人はいないか |
| Resources | 人・スキル・環境・ライセンス・外部の協力先は足りるか |
| Risk | リスクを見直す頻度と場はあるか。脅威だけでなく好機も見ているか |
| 品質 | 完了の定義はあるか。誰がいつ受け入れるか |
| コミュニケーション | 誰に、何を、どの頻度で、どこで伝えるか |
| 調達 | 契約・発注・審査にかかる日数が計画に入っているか |

<a name="uncertainty"></a>

## 不確実性の分類

Cynefin の考え方を簡略化した。答えの分かり方によって、進め方を変える。

| 分類 | 状態 | 進め方 |
| --- | --- | --- |
| 答えが分かっている | 前にやったことがあり、手順がある | 手順どおりに分解して計画する |
| 調べれば分かる | 専門家の分析や調査で答えが出る | 調べるタスクを先に置き、結果で計画を固める |
| やってみないと分からない | 新規プロダクト、経験のない市場や技術。答えは後から分かる | 仮説と、小さく安全に失敗できる検証を短い間隔で回し、検証の結果をマイルストーンにする。遠い先を細かく計画しない |
| すぐ止血が要る | 障害や炎上で、考える前に動く必要がある | まず止める手を打ち、落ち着いてから上の分類で見直す |

どれか分からないときは、そう示して、分類からユーザーと決める。

<a name="risk"></a>

## リスク

<a name="risk-viewpoints"></a>

### 観点

- 技術: 試していない技術、本番の負荷での性能、既存や外部のシステムとの統合、技術的負債、データの移行
- 外部: ベンダーや委託先の遅れ、他チームの成果物待ち、法令や規約の変更、外部の API やプラットフォームの変更
- 組織: 特定の人の離脱や異動、優先度の変更による人の引き上げ、予算の凍結、承認の長期化、体制の変更
- 運営: 初期の見積もりへのこだわり、範囲の膨張、曖昧な完了の基準、認識のずれ、進み具合が見えない
- 関係者: 決める人の不在や遅れ、利害の対立、現場の巻き込み不足、期待のずれ
- 好機: 早く出して得られる反応、使い回せる既存の資産、範囲を削る交渉の余地

<a name="risk-rating"></a>

### 評価

高・中・低の 3 段階で足りる。数値化に時間をかけない。

| | 影響: 低 | 影響: 中 | 影響: 高 |
| --- | --- | --- | --- |
| 確率: 高 | 中 | 高 | 最優先 |
| 確率: 中 | 低 | 中 | 高 |
| 確率: 低 | 低 | 低 | 中 |

<a name="risk-responses"></a>

### 対応の型

| 対象 | 型 |
| --- | --- |
| 脅威 | 回避（原因をなくす）、軽減（確率か影響を下げる）、転嫁（契約や保険で第三者に移す）、受容（予備の日数や費用を積んで備える）、エスカレーション（プロジェクトの権限の外にあるなら、決められる人に渡す） |
| 好機 | 活用（確実に起こす）、強化（確率か効果を上げる）、共有（活かせる相手と組む）、受容、エスカレーション |

「高」以上には、対応のタスクと担当を付けて、タスクに入れる。

<a name="premortem"></a>

### プレモーテム

Klein の手法。「期限の後、このプロジェクトは失敗していた」と仮定して、理由を挙げる。挙がった懸念は、Doshi の 3 つの言葉で分ける。

- Tiger: 放っておくとプロジェクトを失敗させうる、本物の脅威
- Paper Tiger: ほかの人は心配しているかもしれないが、挙げた本人は担当として抑えられていると確信している脅威。担当と、抑えられている根拠を添える
- Elephant: 脅威とは限らないが、誰も話題にしていないことが心配なもの。言葉にして、扱いをユーザーに決めてもらう

対策は上位の Tiger と Elephant に絞り、1 件に担当を 1 人付けて、計画に組み込んで追う。全部を潰そうとしない。

<a name="decisions"></a>

## 判断

- 元に戻せない決定（one-way door）は、慎重に時間をかけて決める。元に戻せる決定（two-way door）は、小さな体制で速く決める。多くの決定は戻せる（Bezos）。
- 決める人は 1 人にする。複数いるか、いないなら、それ自体を判断事項にする。チームをまたぐ大きな決定では、DACI（推進役・承認者・意見を出す人・知らせる人）で役割を分けてもよい。

<a name="estimation"></a>

## 見積もり

- 先に、似た案件が実際にどれくらいかかったかを聞く（参照クラス予測、Flyvbjerg）。作業を内側から積み上げた数字は、楽観に寄る。
- 不確かな作業は、三点見積もりか、幅（例: 2〜4 週間）で示す。一点の数字を約束として扱わせない。三点見積もりの (楽観 + 4 × 最頻 + 悲観) ÷ 6 は PERT（ベータ分布）の重み付き平均で、三角分布の (楽観 + 最頻 + 悲観) ÷ 3 とは違う。どちらを使ったかを書く。
- 幅は、決めることを決めないと狭まらない（McConnell）。幅を狭めたいなら、決めること・調べることをタスクにする。
- チームの中での相対的な大きさで足りるなら、それを使う。

<a name="priority"></a>

## 優先度

- Impact × Effort の 2 × 2: 軽量型で、すばやく振り分けるとき。
- MoSCoW: 範囲を交渉するとき。W は「今回はやらない」。Must は工数の 6 割以下を目安にする（DSDM）。
- 点数は判断の材料で、答えではない。決めるのはユーザー。

<a name="stakeholders"></a>

## 関係者

エンプラ型か、関係者が 5 人を超えるときだけ使う。権力（決定への影響）と関心の 2 つの軸で 4 つに分ける。両方が高い人は密に巻き込む。権力だけが高い人には、驚かせないように要点を伝え続ける。関心だけが高い人には、情報を流し続ける。両方が低い人は様子を見る。今の態度（支持・中立・抵抗）と、望ましい態度との差を埋める手を書く。

<a name="anti-patterns"></a>

## 避けること

- 数人の案件に WBS や RACI を持ち込む
- リスクを並べるだけで、対応と担当を付けない
- 全部を同じ粒度で分解する（直近は細かく、遠い先は粗く）
- 質問攻めで前に進まない（分かる範囲で仮に組み、前提として示す）
- 根拠のない一点の見積もり

<a name="sources"></a>

## 出典

- [PMBOK Guide 第 8 版（PMI、2025 年）](https://www.pmi.org/standards/pmbok)
- [The Cynefin Co の Cynefin の説明](https://thecynefin.co/effective-decision-making-support-tool/)、Snowden と Boone「[A Leader's Framework for Decision Making](https://hbr.org/2007/11/a-leaders-framework-for-decision-making)」（HBR、2007 年）
- Klein「[Performing a Project Premortem](https://hbr.org/2007/09/performing-a-project-premortem)」（HBR、2007 年）
- Doshi「[How to Use Pre-mortems to Prevent Problems, Blunders, and Disasters](https://medium.com/@shreyashere/how-to-use-pre-mortems-to-prevent-problems-blunders-and-disasters-6ecc6df6e22a)」（2020 年）
- [Amazon の 2015 年度の株主への手紙](https://ir.aboutamazon.com/files/doc_financials/annual/2015-Letter-to-Shareholders.PDF)（Type 1 / Type 2 の決定）
- [Atlassian Team Playbook の DACI](https://www.atlassian.com/team-playbook/plays/daci)
- Flyvbjerg「[From Nobel Prize to Project Management: Getting Risks Right](https://arxiv.org/abs/1302.3642)」（Project Management Journal、2006 年）
- McConnell「[Software Development's Cone of Uncertainty](https://www.construx.com/wp-content/uploads/2019/02/CxWhitePaper_ConeOfUncertainty.pdf)」（Construx、2010 年）
- [Agile Business Consortium の MoSCoW](https://www.agilebusiness.org/resource/what-is-moscow-prioritization/)
