---
paths:
  - "**/*.tf"
  - "**/*.tfvars"
---

# Terraform

- 実行してよいのは `terraform fmt` / `validate` / `plan` まで。`apply` / `destroy` / `state` 変更系は手順の提示に留める。
- 変更後は、変更したファイルだけを `terraform fmt <ファイル>...` で整形し、`terraform validate` を実行する。ファイルを指定しない実行（カレントディレクトリ全体が対象）と `-recursive` は、変更していないファイルまで書き換えるので使わない。
- `plan` 結果を報告する際は、destroy / replace が含まれるリソースを必ず明示する。
- 既存のリソースは `import` ブロックで取り込む。`plan` が `N to import, 0 to add, 0 to change, 0 to destroy` になることを確かめてから、apply の手順を示す。`0 to change` でないときは、apply で実際のリソースが書き換わる。apply の後は `import` ブロックを削除する。
- `removed` ブロックには `count` / `for_each` を書けず、`from` にもインスタンスのキー（`[0]` など）を付けられない。条件分岐で一部の環境やインスタンスだけを外す用途には使えない。
- `plan` は設定値の意味までは確かめない（CloudWatch Metrics Insights のクエリ構文、Chatbot が扱えるイベントなど）。こうした値は、apply の手順を示す前に公式ドキュメントで確かめる。
