# Obsidian Vault の同期とバックアップ

対象 Vault: `~/Obsidian/main/`（すべての端末で同じパスを使う）

- [方針](#policy)
- [端末間同期（Cloudflare R2 + Remotely Save）](#sync)
- [Git/GitHub によるバックアップ](#backup)
- [新しい端末のセットアップ手順](#new-device)
- [参考リンク](#references)

<a name="policy"></a>
## 方針

| 目的 | 手段 | 対象 |
|---|---|---|
| 端末間同期 | Remotely Save + Cloudflare R2 | ノート・添付ファイル |
| ローカルでの意図しない変更（誤削除・誤編集・同期事故）からの復旧 | Git（obsidian-git プラグイン）+ GitHub | ノート・添付ファイル |
| Obsidian 設定（`.obsidian/`）の共有 | この dotfiles リポジトリの `.obsidian/setup.sh` | 設定ファイル・CSS スニペット |

- 同期の仕組みは Remotely Save の 1 つだけにする。Git は同期には使わない。
- Remotely Save の同期はバックアップの代わりにならない（削除や競合結果もそのまま他端末へ伝播するため）。
- `.obsidian/` は Remotely Save でも Git でも扱わず、dotfiles で管理する。

```text
MacBook A                                   MacBook B
~/Obsidian/main/                            ~/Obsidian/main/
  ├── notes, attachments ── Remotely Save ── notes, attachments
  │                           ↕ S3 API
  │                       Cloudflare R2 (obsidian-sync)
  ├── .git/ ── obsidian-git ─┐          ┌─ obsidian-git ── .git/
  │                          └─ GitHub ─┘
  └── .obsidian/ ← dotfiles/.obsidian/setup.sh (symlink) → .obsidian/
```

<a name="sync"></a>
## 端末間同期（Cloudflare R2 + Remotely Save）

<a name="sync-r2"></a>
### Cloudflare R2

Bucket（初回のみ）:

| 設定項目 | 設定値 |
|---|---|
| Bucket name | `obsidian-sync` |
| Location | Automatic |
| Storage Class | Standard（無料枠 10 GB-month は Standard のみ対象） |
| Public Access | 無効 |
| Lifecycle Rules | 自動削除なし |

API Token（`Manage R2 API Tokens` から作成）:

| 設定項目 | 設定値 |
|---|---|
| Token name | `obsidian-remotely-save` |
| Permissions | Object Read & Write |
| Bucket scope | `obsidian-sync` のみ |

発行した Access Key ID / Secret Access Key / S3 API Endpoint（`https://<ACCOUNT_ID>.r2.cloudflarestorage.com`）は 1Password に保管する。

> [!WARNING]
> Access Key・Secret Access Key・暗号化パスワードを、ノートやこのリポジトリに書かない。

<a name="sync-remotely-save"></a>
### Remotely Save の設定

`Settings → Remotely Save` で設定する。全端末で同じ値にする。

| 設定項目 | 設定値 |
|---|---|
| Remote Service | S3 |
| Endpoint | R2 の S3 API Endpoint |
| Region | `us-east-1` |
| Access Key ID / Secret Access Key | R2 で発行した値 |
| Bucket | `obsidian-sync` |
| Bypass CORS | 有効 |
| Remote Prefix | 空欄（専用 Bucket のため） |
| Scheduled Auto Sync / Sync on Save / Sync on Startup | 無効（手動同期） |
| Sync Config Dir | 無効（`.obsidian/` は dotfiles で管理） |
| Encryption | 有効（パスワードは 1Password に保管） |

設定後に `Check Connectivity` で接続を確認する。設定項目名は Remotely Save のバージョンで変わることがある。

> [!IMPORTANT]
> - 暗号化の方式とパスワードは初回同期前に決め、全端末で揃える。後から変えるとリモートデータの再構築が必要になる場合がある。
> - パスワードを紛失すると R2 上のデータを復号できない。

<a name="sync-plugin-secrets"></a>
### Remotely Save の認証情報の保存場所

接続情報は `~/Obsidian/main/.obsidian/plugins/remotely-save/data.json` に保存される。このファイルは dotfiles の管理対象外で、Vault の `.gitignore` でも `.obsidian/` ごと除外している。端末ごとに手動で設定する。

<a name="sync-operation"></a>
### 日常の運用

- 作業開始時と作業終了時に手動で同期する（左サイドバーの同期アイコン、またはコマンドパレットで `Remotely Save` の同期コマンド）。
- 端末を切り替えるときは、前の端末で同期が完了したことを確認し、次の端末で同期してから編集を始める。
- 頻繁に使う場合は `Settings → Hotkeys` で同期コマンドにショートカットを割り当てる（既存ショートカットとの競合に注意）。

<a name="sync-excluded"></a>
### Remotely Save で同期されないファイル

Remotely Save は、名前が `.`（ドット）または `_`（アンダースコア）で始まるファイル・フォルダを隠しファイルとして同期しない（Sync Config Dir を有効にした場合の `.obsidian/` を除く）。そのため次のファイルは R2 経由では他端末に届かない。

- `.git/`（Git リポジトリは端末ごとに持つ。[Git/GitHub によるバックアップ](#backup) を参照）
- `.gitignore`（GitHub のリポジトリから復元する。[新しい端末のセットアップ手順](#new-device) を参照）
- `_` で始まるノート・フォルダ（同期したいものには `_` を付けない）

挙動はバージョンで変わる可能性があるため、初回同期後に R2 の Bucket に `.git/` が上がっていないことを確認する。上がっている場合は Remotely Save の除外設定（Ignore Paths 等）で `.git` を除外する。

<a name="backup"></a>
## Git/GitHub によるバックアップ

<a name="backup-purpose"></a>
### 目的と範囲

- 目的は、ローカルでの意図しない変更（誤削除・誤編集・Remotely Save の競合や削除の伝播）からの復旧。端末間同期は Remotely Save が担う。
- 対象はノートと添付ファイル。`.obsidian/` は Vault の `.gitignore` で除外する（端末固有の設定やプラグインの認証情報を含むため）。

Vault の `.gitignore`:

```gitignore
# Obsidian device-specific settings and plugin secrets
.obsidian/

# OS and Obsidian temporary files
.DS_Store
.trash/

# Temporary files
*.tmp
*.swp
```

<a name="backup-github"></a>
### GitHub リポジトリ

- **Private** リポジトリにする。R2 上のデータは Remotely Save で暗号化されるが、GitHub 上のデータは平文で保存される点に注意する。
- 機密性の高い内容（業務情報など）を Vault に置く場合は、GitHub に置いてよいかを事前に判断する。

<a name="backup-obsidian-git"></a>
### obsidian-git プラグインの設定

`Settings → Community plugins → Git` で設定する。

| 設定項目 | 推奨値 | 理由 |
|---|---|---|
| Auto commit-and-sync interval | 任意（例: 30 分） | 変更履歴を定期的に残す |
| Push on commit-and-sync | 有効 | GitHub にもバックアップを残す |
| Pull on commit-and-sync | 無効 | 他端末の変更は Remotely Save で受け取るため |
| Pull on startup | 無効 | 同上 |
| Auto pull interval | 0（無効） | 同上 |

設定項目名は obsidian-git のバージョンで変わることがある。

> [!WARNING]
> **Git で pull しない**
> Remotely Save と Git の両方が他端末の変更を Vault に書き込むと、二重同期になり競合やファイル消失の原因になる。Git は「この端末の状態を記録して GitHub に送る」用途に限定する。

<a name="backup-branch"></a>
### 端末ごとのブランチ

各端末は Remotely Save 経由で同じ内容を受け取り、それぞれ独立にコミットする。全端末が同じブランチに push すると履歴が分岐して push が失敗するため、端末ごとにブランチを分ける。

| 端末 | push 先ブランチ（例） |
|---|---|
| MacBook A | `backup/macbook-a` |
| MacBook B | `backup/macbook-b` |

```sh
cd ~/Obsidian/main
git switch -c backup/<device-name>
git push -u origin backup/<device-name>
```

<a name="backup-restore"></a>
### 復旧手順

1. Obsidian を閉じる（Remotely Save が復旧途中の状態を同期しないように）。
2. 変更履歴を確認する。

   ```sh
   cd ~/Obsidian/main
   git log --oneline -- '<path/to/note.md>'
   ```

3. 必要なファイルだけを過去のコミットから戻す。

   ```sh
   git restore --source=<commit> -- '<path/to/note.md>'
   ```

   ローカルの履歴が失われている場合は、GitHub の各端末のブランチから取り出す（`git fetch origin` → `git restore --source=origin/backup/<device-name> -- '<path>'`）。

4. Obsidian を起動して内容を確認し、Remotely Save で手動同期して他端末に反映する。
5. 戻した状態をコミットする。

> [!CAUTION]
> `git reset --hard` や `git checkout .` で Vault 全体を戻すと、まだコミットしていない変更が失われ、その削除も Remotely Save で他端末に伝播する。戻すのは必要なファイルに限定する。

<a name="new-device"></a>
## 新しい端末のセットアップ手順

1. Obsidian で `~/Obsidian/main/` に**空の** Vault を作成し、いったん Obsidian を閉じる（`.obsidian/` ディレクトリが作られる）。
   - 初回同期時に既存ファイルがあると、意図しない統合や競合が起きる。
2. この dotfiles リポジトリの `.obsidian/setup.sh` を実行し、設定ファイルと `snippets/` をシンボリックリンクする。
3. Obsidian を起動し、`community-plugins.json` に記載のコミュニティプラグイン（Remotely Save, obsidian-git など）を `Settings → Community plugins → Browse` からインストールする。
   - dotfiles が管理するのは有効化リストだけで、プラグイン本体と各プラグインの `data.json` は管理しない。
4. Remotely Save を [Remotely Save の設定](#sync-remotely-save) のとおり設定し、`Check Connectivity` を実行する。
5. Remotely Save で手動同期し、ノート・添付ファイルが取得できたことを確認する。
6. Obsidian を閉じ、GitHub のリポジトリを Vault に取り込む。

   ```sh
   cd ~/Obsidian/main
   git init -b backup/<device-name>
   git remote add origin <repository-url>
   git fetch origin
   # Point the branch at an existing backup without touching the working tree
   git reset origin/backup/<existing-device-name>
   # .gitignore is not synced by Remotely Save, so restore it from Git
   git restore -- .gitignore
   git status   # Remotely Save で取得した内容との差分を確認する
   git push -u origin backup/<device-name>
   ```

   - 作業ツリーには Remotely Save で取得したファイルが既にあるため、`git clone` や `git switch` ではなく `git reset`（作業ツリーを変更しない）で履歴だけを取り込む。
   - `git status` で差分が出た場合は、Remotely Save 側（R2）を最新として扱い、その内容をコミットする。
7. Obsidian を起動し、obsidian-git を [obsidian-git プラグインの設定](#backup-obsidian-git) のとおり設定する。

<a name="references"></a>
## 参考リンク

- Remotely Save: [GitHub](https://github.com/remotely-save/remotely-save) / [Cloudflare R2 設定ガイド](https://github.com/remotely-save/remotely-save/blob/master/docs/remote_services/s3_cloudflare_r2/README.md)
- Cloudflare R2: [ドキュメント](https://developers.cloudflare.com/r2/) / [API Tokens](https://developers.cloudflare.com/r2/api/tokens/) / [料金・無料枠](https://developers.cloudflare.com/r2/pricing/)
- obsidian-git: [GitHub](https://github.com/Vinzent03/obsidian-git) / [ドキュメント](https://publish.obsidian.md/git-doc/)
- 元ノート: `~/Obsidian/main/30_Knowledge/Tools/Obsidian同期(CloudflareR2+RemotelySave).md`
