# Java（mise 管理）

Salesforce Extensions for VS Code（Apex Language Server）を動かすための JDK を mise で管理するための、手順と判断の記録。

## 目次

- [概要](#overview)
- [バージョン選定](#version-selection)
  - [JDK バージョン](#jdk-version)
  - [ディストリビューション](#distribution)
  - [見直しの条件](#review-triggers)
- [前提条件](#prerequisites)
- [インストール](#install)
- [JavaVirtualMachines へのリンク作成](#jvm-symlink)
- [VS Code の設定](#vscode-settings)
- [動作確認](#verification)
- [更新](#update)
- [アンインストール](#uninstall)
- [トラブルシューティング](#troubleshooting)
- [参考資料](#references)

<a name="overview"></a>

## 概要

| 項目                       | 内容                                                                                                |
| -------------------------- | --------------------------------------------------------------------------------------------------- |
| 用途                       | Salesforce Extensions for VS Code（Apex Language Server）の実行環境                                 |
| ディストリビューション     | Eclipse Temurin                                                                                     |
| バージョン                 | 21（LTS）                                                                                           |
| mise での指定              | `java = "temurin-21"`                                                                               |
| dotfiles で管理するもの    | mise のグローバル設定（`~/.config/mise/config.toml`）                                               |
| マシンごとに手動で行うもの | `/Library/Java/JavaVirtualMachines` へのリンク作成、VS Code の設定（dotfiles で管理していない場合） |
| 選定日                     | 2026-10-30                                                                                          |

<a name="version-selection"></a>

## バージョン選定

<a name="jdk-version"></a>

### JDK バージョン

**21（LTS）を採用。**

| 候補           | 判断   | 理由                                                                                                                                                                   |
| -------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 21（LTS）      | 採用   | Salesforce 公式の推奨バージョン。Temurin 21 は少なくとも 2029 年 12 月までサポートされる                                                                               |
| 25（LTS）      | 見送り | 最新の LTS だが、Salesforce の公式情報で 25 での動作が明記されていない。拡張機能は Java のバージョンをチェックしており、過去に未対応のバージョンが拒否された事例がある |
| 26 / 27        | 不採用 | 非 LTS のため、サポート期間が約 6 か月と短い                                                                                                                           |
| 11 / 17（LTS） | 不採用 | サポート対象ではあるが、推奨は 21                                                                                                                                      |

<a name="distribution"></a>

### ディストリビューション

**Eclipse Temurin を採用。**

| 候補                       | 判断   | 理由                                                                                            |
| -------------------------- | ------ | ----------------------------------------------------------------------------------------------- |
| Eclipse Temurin            | 採用   | Salesforce のドキュメントで入手先として Adoptium が案内されている。提供元が特定企業に依存しない |
| Amazon Corretto            | 代替可 | 機能的な差はほぼない。AWS 上の本番で Java を動かす場合は、そちらに揃える選択肢もある            |
| Oracle JDK 21              | 不採用 | 2026 年 10 月以降の更新は Java SE OTN ライセンスでの提供になった                                |
| mise の省略形（`java@21`） | 不採用 | ベンダーが OpenJDK（jdk.java.net のビルド）になり、次のリリースが出ると更新が止まる             |

<a name="review-triggers"></a>

### 見直しの条件

次のいずれかに当てはまったら、バージョンを見直す。

- Salesforce Extensions が Java 25 以降を公式に推奨、またはサポートを明記したとき
- Temurin 21 のサポート終了（少なくとも 2029 年 12 月まで）が近づいたとき
- 拡張機能の更新後に、Java のバージョンに関するエラーが出るようになったとき

<a name="prerequisites"></a>

## 前提条件

- macOS であること
- mise がインストール済みで、シェルの rc ファイルで `mise activate` が設定されていること
- `~/.config/mise/config.toml` が dotfiles からリンクされていること
- mise のデータディレクトリが既定値（`~/.local/share/mise`）であること。`MISE_DATA_DIR` を変更している場合は、以降のパスを読み替える

<a name="install"></a>

## インストール

1. インストールできるバージョンを確認する。

   ```bash
   mise ls-remote java | grep '^temurin-21'
   ```

2. dotfiles 側の mise 設定に追記する。

   ```toml
   [tools]
   java = "temurin-21"
   ```

   `mise use -g java@temurin-21` を実行しても、同じ内容がグローバル設定に書き込まれる。その場合は、dotfiles リポジトリで `git diff` を実行し、変更が反映されていることを確認してからコミットする。

3. インストールする。

   ```bash
   mise install java
   ```

4. インストール結果を確認する。

   ```bash
   mise ls java
   java -version

   # temurin-21 という短い名前のリンクが、最新の 21.0.x を指していることを確認
   ls -la ~/.local/share/mise/installs/java/
   readlink ~/.local/share/mise/installs/java/temurin-21

   # macOS 向けのディレクトリ構成になっていることを確認
   ls ~/.local/share/mise/installs/java/temurin-21/Contents/Home/bin/java
   ```

<a name="jvm-symlink"></a>

## JavaVirtualMachines へのリンク作成

この手順はマシンごとに 1 回だけ、手動で行う（dotfiles の管理対象外）。

### なぜリンクが必要か

- mise のインストール先のディレクトリ名にはパッチ番号まで含まれるため、更新するとパスが変わってしまう。
- Dock から起動した VS Code には、mise が設定する `JAVA_HOME` が渡らないことがある。
- `/Library/Java/JavaVirtualMachines` の下に置けば、パスが固定され、`/usr/libexec/java_home` からも認識される。

### 手順

```bash
# 同じ名前の JDK（brew cask の temurin@21 など）が既にないか確認
ls -la /Library/Java/JavaVirtualMachines/

sudo mkdir -p /Library/Java/JavaVirtualMachines/temurin-21.jdk
sudo ln -sfnv ~/.local/share/mise/installs/java/temurin-21/Contents \
  /Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents
```

リンクは次のように辿られる。途中の `temurin-21` は mise が最新のパッチ版に張り替えるので、更新後も張り直す必要はない。

```text
/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents
  → ~/.local/share/mise/installs/java/temurin-21/Contents
    → ~/.local/share/mise/installs/java/temurin-21.0.x+y.../Contents
```

> **`-n` を付ける理由**
> `ln -s` だけで再実行すると、既にあるリンク（`Contents`）をディレクトリとして辿り、mise のインストール先の中に `Contents/Contents` という不要なリンクを作ってしまう。`-sfn` を付けておけば、既存のリンクを置き換えるだけで済み、何度実行しても結果が変わらない。

<a name="vscode-settings"></a>

## VS Code の設定

ユーザー設定（`settings.json`）に、JDK のホームディレクトリを指定する。`java` の実行ファイルではなく、ディレクトリを指定すること。

```json
{
  "salesforcedx-vscode-apex.java.home": "/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home"
}
```

- このパスはユーザー名を含まないため、すべてのマシンでこの手順を実施していれば、VS Code の設定を dotfiles で共通管理できる。
- チームで共有する Salesforce DX リポジトリの `.vscode/settings.json` には書かない。この手順を実施していない人の環境が壊れるため。

<a name="verification"></a>

## 動作確認

```bash
/usr/libexec/java_home -V
/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home/bin/java -version
```

1. VS Code を再起動する。
2. Salesforce DX プロジェクト（`sfdx-project.json` がある場所）をルートフォルダとして開く。
3. 「表示 > 出力」を開き、ドロップダウンから **Apex Language Server** を選ぶ。起動エラーが出ていなければ完了。

<a name="update"></a>

## 更新

```bash
mise upgrade java
readlink ~/.local/share/mise/installs/java/temurin-21   # 新しいパッチ版を指していることを確認
/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home/bin/java -version

# 任意：使われなくなった古いバージョンを削除
mise prune java
```

更新後は VS Code を再起動する。`/Library` 側のリンクを張り直す必要はない。

<a name="uninstall"></a>

## アンインストール

参照先が消えてリンクが壊れないよう、リンク → mise の順で削除する。

```bash
# 1. /Library 側のリンクを削除
sudo rm /Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents
sudo rmdir /Library/Java/JavaVirtualMachines/temurin-21.jdk

# 2. dotfiles の mise 設定から java の行を削除し、インストール済みのバージョンを削除
mise ls java
mise uninstall java@<mise ls で表示されたバージョン>
```

最後に、VS Code の設定から `salesforcedx-vscode-apex.java.home` を削除する。

<a name="troubleshooting"></a>

## トラブルシューティング

| 症状                                                     | 確認・対処                                                                                                                     |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 「unsupported Java version」と表示される                 | `salesforcedx-vscode-apex.java.home` が 21 を指しているか確認する。そのパスにある `bin/java -version` を実行して確かめる       |
| 出力のドロップダウンに Apex Language Server が出てこない | `sfdx-project.json` があるディレクトリを、ルートフォルダとして開いているか確認する                                             |
| `/usr/libexec/java_home -V` に temurin-21 が出てこない   | `ls -la /Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/` で、リンク先が存在するか確認する                           |
| mise のインストール先に `Contents/Contents` ができている | `-n` を付けずに `ln -s` を再実行したことが原因。`rm ~/.local/share/mise/installs/java/temurin-21/Contents/Contents` で削除する |
| ターミナルの `java` が 21 ではない                       | `mise ls java`、`which java` で確認する。プロジェクトの `mise.toml` などで別のバージョンが指定されていないか確認する           |

<a name="references"></a>

## 参考資料

以下はすべて 2026-10-30 に確認。

- [Java Setup - Salesforce Extensions for VS Code](https://developer.salesforce.com/docs/platform/sfvscode-extensions/guide/java-setup.html)
- [Salesforce Extension Pack - Visual Studio Marketplace](https://marketplace.visualstudio.com/items?itemName=salesforce.salesforcedx-vscode)
- [forcedotcom/salesforcedx-vscode Issue #5636](https://github.com/forcedotcom/salesforcedx-vscode/issues/5636)（未対応の Java バージョンが拒否された事例）
- [mise - Java](https://mise.jdx.dev/lang/java.html)
- [Temurin Support - Adoptium](https://adoptium.net/support)
- [Oracle Java SE Support Roadmap](https://www.oracle.com/java/technologies/java-se-support-roadmap.html)
