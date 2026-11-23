---
status: accepted
date: 2026-11-20
decision-makers: kado-ta
---

# ADR 0001: Claude Code を専用のクローンで動かし、cc-checkout-guard は採用しない

<a name="context"></a>

## 背景と課題

sandbox は、作業ディレクトリの `.git` のほとんど（objects・index・HEAD・`refs/heads`・`refs/remotes/origin`）を書ける（[前の作業の research の 3.1](../work/20261118_git-route-writes/research-git-route.md#results-sandbox)）。

sandbox の外で動く git が、その中身を作業ツリーに書くことがある。sandbox の外で git を動かすのは、次のものである。
- 人間の git（通常のターミナルと `!`）
- `claude -w`
- Claude Code 自身
- sandbox の外で動くフック

すると、自動で読み込まれたり動いたりするファイルが書き換わり、sandbox の外でコードが動く。対象は次のファイルである。
- `.claude/settings*.json`・hooks
- `.mcp.json`
- `.env*`
- mise の設定
- IDE の設定（`.vscode/`・`.idea/`）
- dotfiles のリンク先

2026-11-18〜20 に、この経路を塞ぐ cc-checkout-guard を作った。
- 人間の zsh の `git` を関数で包む。
- root 所有の Python のガードが、git が作業ツリーに書く中身を先に計算する。上のファイルが変わるなら、確認（y/N）を出す。
- `claude -w` には、WorktreeCreate のフックで同じ確認をする。

<a name="drivers"></a>

## 判断の要因

- 守れるかどうかを、確かに言えること
- 人間の git の速さと、確認の手間
- 作るものと、保守し続けるものの量
- Claude の普段の流れ（人間に `! git` で続きを頼む手間）

<a name="options"></a>

## 検討した案

- **A:** cc-checkout-guard を仕上げる。
- **B:** Claude Code を、人間のチェックアウトと `.git` を共有しない専用のクローンだけで動かす。Claude の変更は、GitHub の PR を通してだけ人間のチェックアウトに入れる。

<a name="decision"></a>

## 決定

B を採る（2026-11-20、人間の判断）。A は中止した。

- **A は、守れるかどうかが、git の振る舞いをどこまで再現できるかで決まる。** レビューのたびに新しい経路が見つかった。70 コミットのうち 39 が fix で、受け入れたリスクは 20 項目になった。
- **A は、人間のすべての `git` を遅くし、確認も出す。** `git status` は、関数を通すと約 68 ms 増えた（2026-11-20 の計測。早道を入れる前は約 142 ms）。
- **A は、追従し続ける必要がある。** git の版と、`claude -w` の内部の作りが変わるたびに直すことになる。
- **A は大きい。** ガードは 2,620 行、テストは約 2,960 行になった。
- **B は、sandbox が作業ディレクトリの外に書けないことに頼る。** git の振る舞いを再現しなくてよい。

段階的に移す（2026-11-21、人間の判断）。
- dotfiles を先に移す。
- 業務のリポジトリは、人間が選んだ時に 1 つずつ移す。
- クローンの置き場所は `~/ClaudeWork/<repo>` にする（2026-11-23、人間の判断）。

<a name="consequences"></a>

### 結果

**良いこと**
- 境界を、OS の sandbox が強制する。
- 人間のチェックアウトの git に、確認も遅れも足さない。
- 移したリポジトリでは、人間に `! git` で続きを頼む場面がなくなる。複数のセッションが 1 つのチェックアウトを共有して、ブランチを切り替え合うこともなくなる。
- 作るものは、クローンを作るスクリプトと、設定と規則で済む。

**悪いこと**
- 移すたびに手間がかかる。クローンの作成、フォルダーの信頼、`mise trust`、許可リストの編集、人間のチェックアウトの作り直しがある。
- アプリのリポジトリでは、Claude の変更を手元で試すのに、push したブランチを一時的な場所に clone する必要がある。
- 人間がクローンで git・IDE・codex を動かさないことは、規則に頼る。
- 入れ子のリポジトリの設定からコードが動く経路は、クローンでは開いたままになる。Claude Code 自身とフックが、sandbox の外で git を動かすため。次の作業で扱う。
- 移していないリポジトリでは、今と同じく経路が開いている。

<a name="more"></a>

## 関連

- 実装: [#75](https://github.com/kado-ta/dotfiles/issues/75)
- 前の作業の文書: [research](../work/20261118_git-route-writes/research-git-route.md)・[design](../work/20261118_git-route-writes/design.md)・[plan](../work/20261118_git-route-writes/plan.md)・[test-report](../work/20261118_git-route-writes/test-report.md)
- 前の作業のコードとテスト: ブランチ [`archive/git-route-writes`](https://github.com/kado-ta/dotfiles/tree/archive/git-route-writes) に残した（先端 `bb73bb8`。PR にはしていない）。sandbox の中で書いたコードなので、そのままインストールしない。流用するときは、必要なところだけを新しい PR で入れ直し、レビューを通す。流用の候補は次のとおり。
  - rerere と mise の検査。別の PR で入れる。
  - ガードの対象の一覧と、危ない `.gitattributes` の属性。#75 で、人間が PR を読むときに確かめる一覧にする。
  - `.git` を指す場所を探す処理と、危ない状態を作るテスト。次の作業（入れ子のリポジトリの経路）で使う。
