---
paths:
  - "**/*.tf"
  - "**/*.tfvars"
---

# Terraform

- 実行してよいのは `terraform fmt` / `validate` / `plan` まで。`apply` / `destroy` / `state` 変更系は手順の提示に留める。
- 変更後は `terraform fmt -recursive` と `terraform validate` を実行する。
- `plan` 結果を報告する際は、destroy / replace が含まれるリソースを必ず明示する。
