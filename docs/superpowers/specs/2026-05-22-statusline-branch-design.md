# Statusline ブランチ表示の追加 設計

- 日付: 2026-05-22
- 対象ファイル: `.claude/scripts/statusline.sh`
- 関連 PR: #65（chore/statusline-show-rate-limits-and-model）の後続作業
- 目的: Claude Code のステータスラインに「カレントディレクトリの git ブランチ名」を追加し、複数リポジトリを跨ぐ作業中でも現在位置を把握しやすくする

## 背景

`.claude/scripts/statusline.sh` は Claude Code が stdin に流す JSON を読み、`cwd | ctx% | 5h% | 7d% | model | effort` を色付きで表示するシェルスクリプト。

[Claude Code 公式ドキュメント](https://code.claude.com/docs/en/statusline) の "Available data" を確認した結果、statusline JSON は以下を提供する:

- `workspace.current_dir` / `workspace.project_dir` / `workspace.added_dirs`
- `workspace.repo.{host,owner,name}`（origin remote 由来）
- `workspace.git_worktree`（linked worktree 内のときのみ）
- `worktree.branch`（`--worktree` セッション中のみ）

通常のメインワーキングツリーで作業しているときの「現在チェックアウトしているブランチ名」は JSON では提供されない。よってシェル側で `git` コマンドを呼ぶ必要がある。

## 振る舞い仕様

| カレントディレクトリの状態 | 表示内容 |
|---|---|
| git 管理下 + 通常ブランチ | ブランチ名そのもの（例: `main`、`chore/foo`） |
| git 管理下 + detached HEAD | `(detached)` |
| 非 git ディレクトリ | ブランチセグメントを省略 |
| `workspace.current_dir` が空／取得失敗 | ブランチセグメントを省略 |

`(detached)` を選んだ理由: ユーザーの意図は「ローカルブランチ名」だが、PR チェックアウトや `git rebase` 中など detached 状態でも「何かが見える」方が利用シーンの一貫性が出る。短縮 SHA を出すとブランチ名と視覚的に紛れるため、状態を明示する文字列にとどめる。

## 表示位置・色

- **位置**: `cwd` の直後。「現在位置」をひとまとめの情報として読めるようにする。
- **色**: cwd と同じ `CYAN`。
  - 残った標準色（GREEN/YELLOW/RED）は閾値色（ctx/5h/7d）と意味的に被るため避ける。
  - BLUE は `model`、MAGENTA は `effort` で使用済み。
  - cwd と branch を同色にすることで「ペアの情報」であることを示す。
- **セパレータ**:
  - dir と branch の間のみ ` ⎇ `（U+2387）を使い、ペアとして視覚的にまとめる。
  - branch と以降のセグメントの間は既存の ` │ ` を維持する。

### 出力例

通常時:
```
~/dotfiles ⎇ chore/statusline-show-rate-limits-and-model │ ctx 32% │ 5h 12% │ 7d 45% │ Opus 4.7 (1M) │ xhigh
```

非 git ディレクトリ:
```
~/some/non-git-dir │ ctx 32% │ 5h 12% │ 7d 45% │ Opus 4.7 (1M) │ xhigh
```

detached HEAD:
```
~/dotfiles ⎇ (detached) │ ctx 32% │ 5h 12% │ 7d 45% │ Opus 4.7 (1M) │ xhigh
```

## 実装方針

### ブランチ取得ロジック

`DIR=$(.workspace.current_dir)` を取得した直後に、以下を追加する:

```bash
GIT_BRANCH=""
if [ -n "$DIR" ]; then
    GIT_BRANCH=$(git -C "$DIR" symbolic-ref --short HEAD 2>/dev/null)
    if [ -z "$GIT_BRANCH" ] && git -C "$DIR" rev-parse --git-dir >/dev/null 2>&1; then
        GIT_BRANCH="(detached)"
    fi
fi
```

- `symbolic-ref --short HEAD`: 通常ブランチなら短縮名（`refs/heads/` プレフィックス無し）を返す。detached / 非 git なら非ゼロで終了。
- `rev-parse --git-dir`: detached HEAD と非 git ディレクトリを区別するための判定。
- `2>/dev/null`: git CLI が無い／git ディレクトリでない場合のエラーを抑止する。

### 出力組み立ての変更

既存の `parts` 配列ロジックを尊重しつつ、`cwd` セグメントの直後にブランチを差し込む。`SHORT_DIR` と `GIT_BRANCH` を1セグメントに連結し、内部だけ ` ⎇ ` で区切る:

```bash
if [ -n "$GIT_BRANCH" ]; then
    parts=("${CYAN}${SHORT_DIR} ⎇ ${GIT_BRANCH}${RESET}")
else
    parts=("${CYAN}${SHORT_DIR}${RESET}")
fi
```

これにより、以降の `parts+=(...)` ロジックには手を入れずに済む。

### ヘッダコメント更新

```bash
# Status line displaying: cwd ⎇ branch | ctx% | 5h% | 7d% | model | effort
# Percent segments (ctx / 5h / 7d) use threshold colors;
# cwd / branch / model / effort use fixed colors.
# Branch is shown only when the current directory is inside a git repository.
```

## 取り扱わない事柄（YAGNI）

- **ブランチ名の切り捨て（truncation）**: 長いブランチ名で statusline が圧迫されるが、運用してから判断する。閾値・記号は決め打ち過剰になりやすい。後日の追加コストは低い。
- **dirty 状態の表示（`*` / `+` などのインジケータ）**: 表示量が増え、git status 呼び出しコストもかかる。要件外。
- **upstream との差分（ahead/behind）**: 同上。
- **`worktree.branch` JSON 優先のハイブリッド**: git CLI で同じ結果が得られるので、二重実装を避ける。

## エラー処理

| 事象 | 振る舞い |
|---|---|
| `git` コマンドが PATH にない | `2>/dev/null` でエラー抑止、`GIT_BRANCH=""` のままセグメント省略 |
| `$DIR` が空 | git 呼び出し自体をスキップし、既存の `SHORT_DIR="-"` フォールバック動作と整合 |
| 一時的な git ロック等で `symbolic-ref` が遅延 | statusline は debounce 300ms 駆動で、in-flight 実行は次の更新で cancel される。実害なし |

## パフォーマンス考慮

- 追加コスト: `git -C "$DIR" symbolic-ref` と（必要時のみ）`rev-parse --git-dir` の最大2回呼び出し
- 1回 < 10ms 程度（ローカル `.git/HEAD` の参照のみ）。statusline の debounce は 300ms なので無視できる
- jq 呼び出しは既存の1回のみで増えない

## 検証計画

実装後に以下のスモークテストを `bash .claude/scripts/statusline.sh < fixture.json` で実施する:

1. **通常ブランチ**: 現在の dotfiles 環境（`chore/...` ブランチ）でブランチ名が表示される
2. **非 git ディレクトリ**: `workspace.current_dir` を `/tmp` 等にした JSON で省略される
3. **detached HEAD**: 一時的に `git checkout <SHA>` した状態で `(detached)` が出る
4. **既存ケースの退行なし**: PR #65 のレビュー時に確認した3パターン（フル入力 / rate_limits 欠落 / 空オブジェクト）の出力が、追加セグメント以外で変わらない

## 変更ファイル

- `.claude/scripts/statusline.sh`（編集のみ、新規ファイルなし）

## 完了条件

- 上記4ケースのスモークテストが想定通り
- ヘッダコメントが新しい出力フォーマットを正確に説明している
- PR #65 のレビュー指摘（ヘッダコメント整合）と同じ品質基準を満たす
