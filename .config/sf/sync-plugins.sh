#!/usr/bin/env bash
# plugins.txt に従って sf のユーザープラグインを入れる。一覧にないプラグインは削除しない。
# mise のグローバルタスクから呼ばれる（mise/mise_config.toml 参照）。手動実行も可。
set -euo pipefail

list="${XDG_CONFIG_HOME:-$HOME/.config}/sf/plugins.txt"
spec_re='^(@?[^@[:space:]]+)(@([^@[:space:]]+))?$'
failed=()

# bash 3.2 では、下の while のリダイレクトに失敗しても set -e で止まらない。
if [[ ! -r $list ]]; then
  echo "not found: $list" >&2
  exit 1
fi

# 未インストールの JIT プラグインも version 付きで出力されるため除外する。
# 除外しないと、入っていないプラグインを `ok:` と誤判定する。
installed="$(sf plugins --json | jq -r '.[] | select(.type != "jit") | "\(.name)\t\(.version)"')"

# sf が標準入力を読んでも一覧を消費しないよう、fd 3 で読む。
while read -r spec <&3 || [[ -n $spec ]]; do
  [[ -z $spec || $spec == \#* ]] && continue

  if [[ ! $spec =~ $spec_re ]]; then
    echo "invalid: $spec" >&2
    failed+=("$spec")
    continue
  fi
  name="${BASH_REMATCH[1]}"
  want="${BASH_REMATCH[3]:-}"

  have="$(awk -F'\t' -v n="$name" '$1 == n { print $2 }' <<<"$installed")"
  # `4` は 4.2.0 に一致し、40.0.0 には一致しない。
  if [[ -n $have && (-z $want || $have == "$want" || $have == "$want".*) ]]; then
    echo "ok: $name $have"
    continue
  fi

  echo "install: $spec"
  sf plugins install "$spec" || failed+=("$spec")
done 3<"$list"

# bash 3.2 の set -u では空配列の展開がエラーになるため、件数を先に確認する。
if ((${#failed[@]} > 0)); then
  echo "failed:" >&2
  printf '  %s\n' "${failed[@]}" >&2
  exit 1
fi
