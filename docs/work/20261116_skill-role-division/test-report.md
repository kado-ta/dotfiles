---
status: done
created: 2026-11-16
---

# 検証記録

[plan](plan.md) の手順 3・7・8 の記録。依頼の 6 節（ケース A〜I の机上検証）と 10 節（10 項目）に答える。

- **机上:** このセッションで、文書・設定・実物を照らし合わせて確かめた。
- **実動作:** 規則を読んだ新しいセッションで、Claude が期待どおりに選ぶか。このセッションの中からは試せないので、[試すためのプロンプト](#behavioral)を残し、未検証とする。

<a name="baseline"></a>

## 1. 基準値（規則を置く前）

[効果の測定](plan.md#measurement)の「前」の期間。規則（`claude/rules/SKILL_ROUTING.md`）を置く直前に集計した。スクリプトは [SKILL_INVENTORY.md](../../../claude/SKILL_INVENTORY.md#measurement) にある。

- 期間: 2026-10-27〜2026-11-16（21 日間。`python3 -I skill_usage.py 2026-10-27 2026-11-17`）
- セッション数: 233

| 指標 | 値 |
| --- | --- |
| Claude が起動したスキル（回数 / セッション数）の上位 | `verify` 65 / 35、`salesforce-development:platform-soql-query` 27 / 18、`superpowers:systematic-debugging` 24 / 24、`superpowers:test-driven-development` 14 / 14、`salesforce-development:platform-metadata-retrieve` 13 / 10、`codex` 12 / 10、`superpowers:writing-plans` 11 / 11、`crit-review` 10 / 8、`superpowers:executing-plans` 8 / 8 |
| レビュー系 | `review` 1 / 1、`code-review` 1 / 1、`superpowers:requesting-code-review` 0 |
| 計画系 | `superpowers:brainstorming` 4 / 4、`superpowers:writing-plans` 11 / 11（どちらかを起動したセッションは 15） |
| ユーザーが入力したコマンドの上位 | `commit-staged-pr` 48、`sandbox` 17、`gstack-upgrade` 14、`understand-anything:understand-chat` 5、`understand-anything:understand` 2、`pstack:bro`・`pstack:how`・`pstack:why` 各 1 |
| 1 つのセッションで 2 つ以上のレビュー系のスキルを使った回数 | 0 |
| Claude の発言で `/pstack:` を含むもの | 8 |

- 計画系のスキルを起動した 15 セッションが、軽微な作業での起動だったかは見ていない。セッションの ID は公開リポジトリに載せない。前の期間のトランスクリプトは測定のときには消えているので、前後の比較はセッション数で行い、後の期間の一覧だけを人が見る。
- `/pstack:` を含む発言には、この作業と前の作業で Claude がスキルの名前を書いた分が入っている（推測）。

<a name="settings-change"></a>

## 2. `skillOverrides` の変更

| 確認 | 結果 |
| --- | --- |
| `jq` で読めるか、値が入ったか | `document-release`・`document-generate`・`spec` がいずれも `user-invocable-only` |
| 差分が `skillOverrides` の 3 行だけか | `git diff claude/settings.json` で、`design-motion` の行末のカンマと 3 行の追加だけ |
| gstack の状態の数 | 有効 25、`user-invocable-only` 7、`off` 31（計 63） |
| 新しいセッションで、3 件がスキルの一覧から消えるか | 未検証（このセッションのスキル一覧は起動時のもの） |

<a name="name-check"></a>

## 3. 名前の実在と状態の一致

規則・チートシート・棚卸しに出てくるスキルの名前が実在するか、棚卸しの状態が設定と一致するかを、次のスクリプトで照合した。プラグインやスキルを更新したときにも使う（[更新したときの見直し](../../../claude/SKILL_INVENTORY.md#upgrade)）。

```text
$ python3 -I check_names.py ~/dotfiles
missing references: none
gstack states from settings: {'off': 31, 'on': 25, 'user-invocable-only': 7} total 63
gstack enabled: doc 25, settings 25, diff none
gstack user-invocable-only: doc 7, settings 7, diff none
gstack off: doc 31, settings 31, diff none
pstack: 58 skills, 57 with disable-model-invocation
understand-anything: 9 skills, 0 with disable-model-invocation
pstack names not in the inventory: none
```

- 照合が働くことの確認: 規則のコピーで次のように書き換えると、それぞれ検出した。
  - `/review` を `/no-such-skill` に: `missing references: [('claude/rules/SKILL_ROUTING.md', '/no-such-skill')]`
  - `/pstack:how` を `/how` に（プラグインの接頭辞の抜け）: `missing references: [('claude/rules/SKILL_ROUTING.md', '/how')]`
- 最終レビューの前は、スラッシュ付きの名前でも接頭辞のない短い名前を通していたため、正しくない呼び出し名 `/understand`（正しくは `/understand-anything:understand`）を見逃していた。照合を厳しくし、棚卸しと research-routing.md の該当箇所を直した。
- superpowers 15、understand-anything 9、crit 3、claude-code-setup 1、個人スキル 4 が、すべて棚卸しに載っていることを別に確かめた。
- `/plan-eng-review`・`/investigate`（廃止されたことを書くために出している）、`/tmp`、`crit:profile-test`（mise のタスク）は、スキルではないと分かって書いているので除外した。

```python
"""Check skill names in the routing docs against the installed skills and settings.

Usage: python3 -I check_names.py <dotfiles root>
"""
import glob
import json
import os
import re
import sys

root = sys.argv[1]
home = os.path.expanduser("~")
settings = json.load(open(os.path.join(root, "claude/settings.json"), encoding="utf-8"))
overrides = settings.get("skillOverrides", {})


def frontmatter(path):
    text = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def plugin_skills(prefix, pattern):
    found = {}
    for path in glob.glob(os.path.join(home, ".claude/plugins/cache", pattern, "skills/*/SKILL.md")):
        name = os.path.basename(os.path.dirname(path))
        found[f"{prefix}:{name}"] = "disable-model-invocation: true" in frontmatter(path)
    return found


known = {}
for prefix, pattern in [
    ("superpowers", "claude-plugins-official/superpowers/*"),
    ("claude-code-setup", "claude-plugins-official/claude-code-setup/*"),
    ("crit", "crit/crit/*"),
    ("understand-anything", "understand-anything/understand-anything/*"),
    ("pstack", "cursor-plugins/pstack/*"),
]:
    known.update(plugin_skills(prefix, pattern))

user_skills = {}
for entry in os.listdir(os.path.join(home, ".claude/skills")):
    path = os.path.join(home, ".claude/skills", entry, "SKILL.md")
    if os.path.isfile(path):
        real = os.path.realpath(os.path.dirname(path))
        user_skills[entry] = "personal" if os.sep + "dotfiles" + os.sep in real else "gstack"
known.update({name: False for name in user_skills})

builtins = {
    "code-review", "simplify", "security-review", "init", "update-config", "fewer-permission-prompts",
    "loop", "schedule", "run", "claude-api", "workflow-authoring", "plugin-authoring", "keybindings-help",
    "claude-in-chrome", "dataviz", "artifact-design", "artifact-diagramming", "artifact-capabilities",
    "doctor", "skill-doctor", "plugin",
}
anthropic = {f"anthropic-skills:{n}" for n in (
    "built-in-browser", "chrome-browser", "computer-use", "deep-research", "docs", "docx",
    "google-workspace", "import-memory", "morning", "pdf", "pptx", "skill-creator", "xlsx")}
names = set(known) | builtins | anthropic
short = {n.split(":", 1)[1] for n in known if n.startswith(("superpowers:", "understand-anything:"))}

# Named on purpose although they are not skills: removed gstack skills, a path, a mise task.
NOT_SKILLS = {"plan-eng-review", "investigate", "tmp", "crit:profile-test"}

docs = ["claude/rules/SKILL_ROUTING.md", "claude/SKILL_CHEATSHEET.md", "claude/SKILL_INVENTORY.md"]
missing = []
for doc in docs:
    text = open(os.path.join(root, doc), encoding="utf-8").read()
    text = text.split("```python")[0]  # skip the embedded measurement script
    # `/plugin:<name>` and a bare `/plugin:` prefix are not references to a skill.
    refs = {m.group(1) for m in re.finditer(r"`/([a-z0-9_-]+(?::[a-z0-9_-]+)?)(:<|:`)?", text) if not m.group(2)}
    refs |= set(re.findall(r"\b((?:superpowers|understand-anything|pstack|crit|claude-code-setup|anthropic-skills):[a-z0-9_-]+)", text))
    for ref in sorted(refs - NOT_SKILLS):
        # A slash command needs the full name: plugin skills keep their prefix (`/understand` is not valid).
        if ref not in names:
            missing.append((doc, "/" + ref))
    bare = set(re.findall(r"`([a-z][a-z0-9-]+)`", text)) | set(re.findall(r"(?<![`/:\w-])([a-z]+(?:-[a-z]+){1,4})(?![`\w:-])", text))
    for word in sorted(bare & {
        "brainstorming", "writing-plans", "executing-plans", "test-driven-development", "systematic-debugging",
        "requesting-code-review", "finishing-a-development-branch", "subagent-driven-development",
        "verification-before-completion", "writing-skills", "understand-chat", "understand-explain",
        "understand-onboard", "understand-diff",
    }):
        if word not in short:
            missing.append((doc, word))

print("missing references:", missing or "none")

# State consistency for gstack.
gstack = sorted(n for n, src in user_skills.items() if src == "gstack")
state = {n: overrides.get(n, "on") for n in gstack}
state["gstack"] = overrides.get("gstack", "on")  # the root skill directory
counts = {}
for value in state.values():
    counts[value] = counts.get(value, 0) + 1
print("gstack states from settings:", dict(sorted(counts.items())), "total", len(state))

inv = open(os.path.join(root, "claude/SKILL_INVENTORY.md"), encoding="utf-8").read()


def section(anchor):
    start = inv.index(f'<a name="{anchor}"></a>')
    end = inv.index("<a name=", start + 1)
    return inv[start:end]


enabled_doc = set(re.findall(r"^\| `([a-z0-9-]+)` \|", section("gstack-enabled"), re.M))
limited_doc = set(re.findall(r"^\| `([a-z0-9-]+)` \|", section("gstack-limited"), re.M))
off_text = section("gstack-off").split("\n\n")[2]
off_doc = {w.split("（")[0].strip().strip("`") for w in off_text.rstrip("。\n").split("、")}
for label, doc_set, want in [
    ("enabled", enabled_doc, "on"),
    ("user-invocable-only", limited_doc, "user-invocable-only"),
    ("off", off_doc, "off"),
]:
    actual = {n for n, v in state.items() if v == want}
    print(f"gstack {label}: doc {len(doc_set)}, settings {len(actual)}, diff {sorted(doc_set ^ actual) or 'none'}")

pstack_dmi = sum(1 for n, dmi in known.items() if n.startswith("pstack:") and dmi)
pstack_total = sum(1 for n in known if n.startswith("pstack:"))
ua_dmi = sum(1 for n, dmi in known.items() if n.startswith("understand-anything:") and dmi)
print(f"pstack: {pstack_total} skills, {pstack_dmi} with disable-model-invocation")
print(f"understand-anything: {sum(1 for n in known if n.startswith('understand-anything:'))} skills, {ua_dmi} with disable-model-invocation")
pstack_listed = set(re.findall(r"`([a-z-]+)`", section("pstack").split("- 依存")[0])) & {n.split(":")[1] for n in known if n.startswith("pstack:")}
rest = section("pstack").split("- 依存")[1]
pstack_listed |= {w.strip().strip("`") for w in re.split(r"[、。:：]", rest) if w.strip().strip("`") in {n.split(":")[1] for n in known if n.startswith("pstack:")}}
print("pstack names not in the inventory:", sorted({n.split(":")[1] for n in known if n.startswith("pstack:")} - pstack_listed) or "none")
```

<a name="cases"></a>

## 4. ケース A〜I（机上）

規則（R）とチートシート（C）のどの行で決まるかを、それぞれの末尾に書いた。

<a name="case-a"></a>

### A. Rails のキャッチアップ

- **利用するスキルと順序:**
  1. Claude が README・`config/routes.rb`・`db/schema.rb` を読み、全体像を答える（スキルなし）。
  2. 続けて触るリポジトリなら、`/understand-anything:understand` を提案する（`.ua/` を `.gitignore` に足すことも提案する）。
  3. グラフができたら `understand-onboard`・`understand-chat`。特定の領域は `/pstack:how` を提案する。
- **理由:** 1 回の概観なら読解で足りる。グラフは作るのが重いが、何度も聞くなら安くなる。
- **使わないスキル:** `brainstorming`・`writing-plans`（変更しない）、`/review`（差分がない）、`/office-hours`（作るものを決める場面ではない）。
- **終了条件:** ルーティング → コントローラ → サービス → モデルの流れを、ファイルの場所を付けて説明できる。
- 根拠: R「Overlapping skills」5 つ目、R の提案の表 1 行目、C の A「大きいリポジトリのキャッチアップ」。

<a name="case-b"></a>

### B. Rails API と React の新機能

- **利用するスキルと順序:**
  1. `brainstorming` → `writing-plans` → `/crit-review`
  2. OpenAPI の spec を先に更新し、`redocly lint`
  3. `test-driven-development`（Rails の request spec、React のテスト）。独立したタスクが多ければ `subagent-driven-development`。
  4. `/review` → Codex レビューの提案 → `/crit-review` → PR（CLAUDE.md の Git 節）
- **理由:** 仕様と設計を決める必要がある「複雑」。公開 API なら高リスクも重なる。
- **使わないスキル:**
  - `/office-hours`: 何を作るかは決まっている。
  - `/spec`: 明示だけで、Issue 作成が止まる。
  - `/code-review`・`requesting-code-review`: `/review` と重なる。
  - `/pstack:architect`: 設計の案が 1 つに決まっているなら使わない。
  - `/qa`: ブラウザが sandbox で動かなければ使わない。API は request spec で確かめる。
- **終了条件:** plan の完了条件、テストと lint が通る、`/review` の指摘に対応した、Crit の承認。
- 根拠: R「Size and risk」の複雑、C の A「新機能開発」と D「複雑な機能開発」。

<a name="case-c"></a>

### C. 共通の認証・認可基盤の変更（OIDC・SAML・Cognito、複数のアプリ）

- **利用するスキルと順序:**
  1. `brainstorming`。既存の設計の意図が分からなければ `/pstack:why` を提案する。
  2. 案が複数なら `/pstack:architect with checkpoint` を提案する。
  3. `writing-plans`（アプリごとの互換性、段階的な切り替え、ロールバック）→ `/crit-review`
  4. 実装の前に `/pstack:blast-radius` を提案する。
  5. `test-driven-development` → `/review` → `/security-review`
  6. 検証可能な不変条件（トークンの検証、ロールの対応付け）が残れば `/pstack:interrogate` を提案する。
  7. Codex レビュー（ユーザーが `!` で実行）→ `/crit-review` → PR
- **理由:** 複雑かつ高リスクで、セキュリティの境界に触れる。影響が複数のアプリに及び、元に戻しにくい。
- **使わないスキル:**
  - `/cso`: 保存先に書けない。
  - `/pstack:arena`: `architect` の中で使われるので重ねない。
  - `/code-review`: `/review` と重なる。
- **終了条件:** アプリごとの互換性の表とロールバックの手順がある。`/security-review` と Codex の指摘について、採用か不採用かを整理した。
- 根拠: R「Size and risk」の高リスクとセキュリティの境界、R の提案の表、C の E の OIDC の例。

<a name="case-d"></a>

### D. 数行の軽微なバグ修正

- **利用するスキル:** なし。失敗する再現テストを書き、直し、テストを実行する。PR にするなら `/crit-review`（CLAUDE.md）。
- **理由:** 軽微の 5 つの条件をすべて満たす。
- **使わないスキル:**
  - brainstorming: R の原則 1 つ目と、`brainstorming` 自身の軽微な作業の例外。
  - systematic-debugging: 原因が分かっている。
  - `/review`・Codex: 頼まれなければ使わない。
- **終了条件:** 再現テストが、失敗から成功に変わる。
- **注意:** 認証認可に触れる数行は軽微ではない。高リスクとして `/security-review` などを足す。
- 根拠: R「Principles」1 つ目、R「Size and risk」の軽微、C の D「軽微な修正」。

<a name="case-e"></a>

### E. 原因不明の本番障害

- **利用するスキルと順序:**
  1. `systematic-debugging`。ログ・メトリクス・コードを読み取りだけで調べる。
  2. 最近の変更が疑わしければ `/pstack:why` を提案する。本番に近い環境で調べる前に `/careful` を提案する。
  3. 原因と修正案、当面の回避策を報告する。
  4. 修正は別の作業として行う（再現テスト → 修正 → `/review`）。
- **調査と変更の分離:**
  - 本番への書き込みと、DB・AWS の変更は、明示の指示なしに実行しない（CLAUDE.md の Safety）。
  - `validate-command.sh` は `prod` を含むコマンドを止める。その操作はユーザーが行う。
- **使わないスキル:**
  - `/qa`: 直して commit する。
  - `/canary`: デプロイ後の監視であり、原因調査ではない。
  - `brainstorming`
- **終了条件:** 原因を根拠（ログ・コードの場所）付きで説明でき、再現の手順かテストがある。
- 根拠: C の A「原因不明の障害調査」と D「障害調査」、R の提案の表の `/careful`。

<a name="case-f"></a>

### F. DB スキーマの変更（既存データ、API の互換性、マイグレーション、ロールバック）

- **利用するスキルと順序:**
  1. `writing-plans`。expand / contract の段階、データの移し替え、ロールバック、API の互換性を書く。
  2. `/crit-review` → `/pstack:blast-radius` を提案する。
  3. `test-driven-development`（マイグレーションのテスト）→ `/review` → Codex レビューの提案 → `/crit-review`
  4. `/review` は、マイグレーションがあると Data Migration の専門家を起動する。
- **理由:** 常に高リスク。元に戻しにくい。
- **使わないスキル:**
  - `/security-review`: データの公開範囲が変わらなければ使わない。セキュリティの境界に触れないため。
  - `/pstack:architect`: 案が 1 つなら使わない。
- **終了条件:** マイグレーションの up と down を手元の DB で確かめた。ロールバックの手順がある。OpenAPI が変わらないか、互換を保って版を分けた。
- 根拠: R「Size and risk」の高リスク、C の A「DB スキーマ」と E の enum の例。

<a name="case-g"></a>

### G. 大規模なリファクタリング

- **利用するスキルと順序:**
  1. `writing-plans`。確かめられる単位に分ける。
  2. `/crit-review`。共通基盤に触れるなら `/pstack:blast-radius` を提案する。
  3. `executing-plans` か `subagent-driven-development`。各段階でテストが通ることを確かめる。
  4. `/review` → Codex レビューの提案
- **理由:** 複雑（大規模で、複数のモジュールにまたがる）。
- **使わないスキル:**
  - brainstorming: 目的が決まっていれば使わない。案が複数なら `/pstack:architect with checkpoint` を提案する。
  - `/simplify`: `/review` と同じ差分に重ねない。
  - `/test-audit`: テストの整理が範囲外なら使わない。
- **終了条件:** 前後で振る舞いが変わらない（各段階でテストが通る）。plan の手順を終えた。
- 根拠: R「Size and risk」の複雑、C の A「リファクタリング」。

<a name="case-h"></a>

### H. PR のレビュー

- **利用するスキル:** `/review`。
- **追加するかの判断:**
  - 高リスクなら、`/pstack:blast-radius` か `/pstack:interrogate` を提案する。
  - セキュリティの境界に触れるなら `/security-review` を使う。
  - 複雑か高リスクなら Codex レビューを提案する。
  - 軽微や通常の PR では、どれも足さない。
- **使わないスキル:**
  - `/code-review`・`requesting-code-review`: `/review` と重なる。
  - `/codex`: Bash から拒否される。
- **終了条件:** 指摘を「直した・直さない（理由）」に分けた。Codex は 1 PR あたり 5 回まで。push の前に `/crit-review`（CLAUDE.md）。
- 根拠: R「Overlapping skills」3 つ目、R「Exit criteria」、C の C「`/review` と `interrogate`」と D「独立レビュー」。

<a name="case-i"></a>

### I. Terraform による AWS・Cloudflare の変更

- **利用するスキルと順序:**
  1. `writing-plans`。対象のリソース、state、権限、既存のリソースへの影響、ロールバックを書く。
  2. `/crit-review`。インフラの変更なので、CLAUDE.md で plan の承認が必須。
  3. 編集して、`terraform fmt`・`validate`・`plan` まで行う（rules/TERRAFORM.md）。destroy と replace は報告で明示する。
  4. `/security-review`（IAM、セキュリティグループ、ALB のリスナー、S3 のポリシー、Cloudflare）
  5. Codex レビューの提案 → `/crit-review` → PR
- **apply の扱い:** apply はユーザーが行う。共有のリソース（VPC、共有の ALB）に触れるなら `/pstack:blast-radius` を提案する。
- **使わないスキル:**
  - `/cso --infra`: 保存先に書けない。
  - `/qa`
  - brainstorming: 要件が決まっていれば使わない。
- **終了条件:** `terraform plan` に予期しない destroy や replace がない。state を変えていない。apply の手順が書いてある。
- 根拠: R「Size and risk」の高リスクとセキュリティの境界、C の A「インフラ・Terraform」と E の ALB の例。

<a name="ten-checks"></a>

## 5. 依頼の 10 節の 10 項目

| # | 項目 | 結果 | 根拠 |
| --- | --- | --- | --- |
| 1 | 棚卸しに漏れがない | 机上で確認 | [3 節](#name-check)。プラグイン・gstack・pstack・個人スキルを、実物の一覧と突き合わせた |
| 2 | 実在しないスキルやコマンドを書いていない | 机上で確認 | [3 節](#name-check)の照合で `none` |
| 3 | 状態が設定と一致する | 机上で確認 | gstack の 63 件の状態と `skillOverrides`、pstack の `disable-model-invocation` 57 件、deny の 3 件（`setup-pstack` と 2 つのエージェント）。pstack の 2 つのエージェントは、このセッションの Agent の一覧に出ないことを確かめた |
| 4 | 重複の優先順位が明確 | 机上で確認 | [research-routing.md](research-routing.md#pairs) の 8 組すべてに優先順位がある |
| 5 | タスクの分類に漏れがない | 机上で確認 | チートシートの A に、依頼の 5 節の 20 行すべてと、追加の 4 行（大きいリポジトリのキャッチアップ、企画、作業の中断と再開、Salesforce）がある |
| 6 | 軽微な修正で不要なスキルを使わない | 机上で確認 | [ケース D](#case-d)。実動作は[未検証](#behavioral) |
| 7 | 高リスクの検証が決まっている | 机上で確認 | 規則の高リスクの行、[ケース C・F・I](#case-c) |
| 8 | CLAUDE.md・rules と整合する | 机上で確認 | 下の表 |
| 9 | Sandbox・Permissions・Hooks・Git の制御を変えていない | 確認 | `git diff --stat` で、`settings.json` の差分は `skillOverrides` の 3 行だけ。`permissions`・`sandbox`・`hooks` と `claude/hooks/` に差分がない。commit・push はしていない |
| 10 | チートシートと規則が一致する | 机上で確認 | 下の表。照合の途中で、チートシートのリファクタリングの行に `/simplify` が `/review` と重なっていたので外した |

<a name="consistency"></a>

### CLAUDE.md と規則・チートシートの整合

| CLAUDE.md・rules | 規則・チートシート | 結果 |
| --- | --- | --- |
| Tools: 差分のレビューは `/review` | 差分のレビューは `/review` だけ | 一致 |
| Tools: E2E は `/qa`、個別のブラウザ操作は `/browse` | チートシートの A「E2E・ブラウザ QA」 | 一致。sandbox でブラウザが動かない可能性を書き足した |
| Tools: plan の承認と push・PR の前に `/crit-review` | 複雑の構成、D の各行 | 一致 |
| Cross-model review: 設計判断を含む変更、大規模変更、セキュリティ関連の変更で Codex を提案。1 PR あたり 5 回まで | 複雑と高リスクで Codex を提案 | 一致。最初の案は複雑に入れておらず、2 回目のレビューで直した |
| Safety: 本番への書き込み、`terraform apply` をしない | ケース E・I | 一致 |
| DOCUMENTS.md: スキルの既定の保存先より優先する | 棚卸しの `brainstorming`・`writing-plans`・`/office-hours` の行 | 一致 |
| rules/TERRAFORM.md: plan まで、destroy・replace を明示 | ケース I | 一致 |

<a name="behavioral"></a>

## 6. 実動作の確認（未検証）

規則を読んだ新しいセッションで、次を試す。いずれも未検証。

| プロンプト | 期待する動き |
| --- | --- |
| 「README の誤字を 1 か所直して」 | スキルを起動しない |
| 「この関数の nil チェック漏れを直して。原因は分かっている」 | `brainstorming` を起動しない。再現テストを書いて直す |
| 「この PR をレビューして」 | `/review` だけ。`/code-review` を重ねない |
| 「共通認証基盤に SAML の IdP を 1 つ足したい」 | `brainstorming` → `writing-plans`。`/pstack:blast-radius` などを 1 回提案し、Codex レビューを提案する |
| 「このリポジトリを初めて触る。全体像をつかみたい」 | 読んで答え、`/understand-anything:understand` を提案する（自分では起動しない） |
| 「リリースに合わせてドキュメントを更新して」 | 通常の編集で行い、`/document-release` を起動しない |
| 「セキュリティ監査をして」 | `/security-review`。`/cso` の制約に触れる |

- 新しいセッションのスキル一覧に、`document-release`・`document-generate`・`spec` が出ないことも確かめる。

<a name="commands"></a>

## 7. 実行した検査

| コマンド | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | 8 項目すべて PASS（この文書を書く前は、この文書へのリンク先がなく `markdown-links` だけが失敗していた） |
| `python3 -B .github/scripts/test-check-repo.py` | 43 tests OK |
| `git ls-files -z '*.sh' '*.command' ':!:claude/hooks/herdr-agent-state.sh' \| xargs -0 shellcheck -S warning` | exit 0 |
| `actionlint` | exit 0 |
