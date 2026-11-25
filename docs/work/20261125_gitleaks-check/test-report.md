---
status: in-progress
created: 2026-11-25
---

# 試験記録: check-repo.py の gitleaks 検査

<a name="related"></a>

## 関連

- [design.md](design.md)
- [plan.md](plan.md)

<a name="environment"></a>

## 環境

- macOS（Claude Code の sandbox の中）、gitleaks 8.30.1（Homebrew）、PATH の `python3`。

<a name="task-1"></a>

## Task 1: 検査 `secret-content`

<a name="tdd"></a>

### テストの失敗と成功

| 段階 | コマンド | 結果 |
| --- | --- | --- |
| 実装前 | `python3 -B .github/scripts/test-check-repo.py` | 102 件中 5 件が失敗（FAIL を期待する 5 件が終了コード 0）。34.7 秒 |
| 実装後 | 同上 | 102 件すべて OK。41.0 秒（足す前は 93 件で 32.1 秒） |

<a name="mutation"></a>

### テストが誤りを捕まえるかの確認

検査スクリプトの写しをわざと壊し、対応するテストを実行した（本物のファイルは変えていない）。

| 壊し方 | テスト | 結果 |
| --- | --- | --- |
| 環境変数 `GITLEAKS_CONFIG` を除かない | `test_gitleaks_config_env_is_ignored` | 失敗した（捕まえた） |
| symlink を写す | `test_symlink_is_not_followed` | 失敗した（捕まえた） |
| 出力に `Match` を足す | `test_secret_in_tracked_file_fails` | 通った。`--redact` で報告の値が伏せられるため |
| 出力に `Secret` を足す | 同上 | 通った。理由は同上 |
| `--redact` を外し、出力に `Secret` を足す | 同上 | 失敗した（捕まえた） |
| `--config` を渡さない | `test_repo_gitleaks_config_allowlist_passes` | 通った。gitleaks が対象のパスの `.gitleaks.toml` を自分で読むため |

値を伏せる守りは 2 重（`--redact` と、出力に値を出さないこと）で、両方を外すとテストが失敗する。

<a name="real-repo"></a>

### 今のリポジトリへの実行

| 確認 | 結果 |
| --- | --- |
| `python3 -B .github/scripts/check-repo.py` | すべて PASS。`secret-content` の見つかった件数は 0。0.49 秒（足す前は 0.25 秒） |
| 調べた範囲 | 239 ファイル、2,575,880 バイトを写し、gitleaks は約 2.57 MB を 71.6 ミリ秒で調べた |
| 未追跡の偽の秘密（`canary-gitleaks.txt`）を置いて実行 | `FAIL secret-content` と `canary-gitleaks.txt:1: github-pat`。値は出力に出なかった。ファイルは同じスクリプトで消した |

誤検知が 0 件だったので、`.gitleaks.toml` と `gitleaks:allow` は使っていない。

<a name="task-2"></a>

## Task 2: CI に gitleaks を入れる

| 確認 | 結果 |
| --- | --- |
| `gitleaks_8.30.1_checksums.txt` の `linux_x64` の行 | CI に書いた SHA256 と一致 |
| tar.gz を取得して照合・一覧 | `shasum -a 256 -c` が OK、アーカイブのルートに `gitleaks` がある |
| `actionlint` | 出力なし |

<a name="review"></a>

## `/review` の指摘と修正

専門レビュー 5 件（テスト・保守性・セキュリティ・性能・単純化）と敵対的レビューを実行した。保守性・性能・単純化は指摘なし。Codex のパスは gstack の設定（`codex_reviews` が無効）で実行していない。

| 指摘 | 扱い |
| --- | --- |
| allowlist の `paths` が一時ディレクトリの絶対パスに当たり、`(?:^|/)src/`・`(?:^|/)tmp/` のような除外で全ファイルが外れる（セキュリティと敵対的レビューが独立に検出） | 修正。写した先を cwd にして `.` を調べる |
| `GITLEAKS_CONFIG_TOML` を除く処理のテストがない | テストを追加 |
| `--config` を外すと `.gitleaks.json` が `.gitleaks.toml` より先に読まれ、秘密を見逃す（実測）のに、テストがない | テストと理由のコメントを追加 |
| 「見つかった」の終了コード 2 が Go の panic と重なる。0 と 2 以外の分岐のテストがない。stderr に色の制御文字が出る | 終了コードを 42 に変更し、`NO_COLOR=1` を渡す（`--no-color` では設定の読み込みのログの色が消えないことを実測）。テストを 2 件追加 |
| 通常のファイルがないと写した先が作られず gitleaks が失敗する | 写した先をループの前に作る |
| 作業ツリーと HEAD・index のずれ、既定の除外の種類、`.gitleaks.toml` の中身 | ユーザーの判断で受け入れ、design.md の残るリスクに追記 |

修正の検証:

| 確認 | 結果 |
| --- | --- |
| 修正前に足したテストを実行 | 107 件中 4 件が失敗（相対パスの 2 件・色・終了コード） |
| 修正後 | 107 件すべて OK（45.1 秒） |
| 守りを外した写しで各テストを実行（`GITLEAKS_CONFIG_TOML` を除かない、`--config` を渡さない、絶対パスを渡す、`NO_COLOR` を外す、報告が空の分岐を消す） | 5 件ともテストが失敗した（捕まえた） |
| 絶対パスと相対パスで、今のリポジトリを調べたバイト数 | どちらも 2,577,698 バイト。検査の範囲は変わっていない |
