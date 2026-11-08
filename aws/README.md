# aws

AWS CLI の設定を管理するディレクトリ。このリポジトリは公開しているので、`config` と `credentials` は Git で管理しない。

| ファイル      | Git 管理 | 内容                                                            |
| ------------- | -------- | --------------------------------------------------------------- |
| `link.sh`     | する     | `config` と `credentials` を `~/.aws/` にシンボリックリンクする |
| `README.md`   | する     | このファイル                                                    |
| `config`      | しない   | AWS CLI のプロファイル設定                                      |
| `credentials` | しない   | AWS のアクセスキー                                              |

<a name="setup"></a>

## 運用

`config` と `credentials` はマシンごとにこのディレクトリで作成し、`~/.aws/` にシンボリックリンクする。

1. `link.sh` を実行する。`config`（`[default]` の `region` だけ）と空の `credentials` がなければ作成し、`~/.aws/` にリンクする。`setup.command` からも実行される。

   ```sh
   ~/dotfiles/aws/link.sh
   ```

2. このディレクトリの `config` と `credentials` を編集する。

<a name="config-example"></a>

## `aws/config` の例

```text
[profile {org}-iam]
region = ap-northeast-1
output = json

[profile {org}-{name}-{env}]
region = ap-northeast-1
source_profile = {org}-iam
role_session_name = {user}
role_arn = arn:aws:iam::XXXXXXXXXXXX:role/{org}-{name}-{env}-administrator-switch-role
mfa_serial = arn:aws:iam::XXXXXXXXXXXX:mfa/{user}

[default]
region = ap-northeast-1
```
