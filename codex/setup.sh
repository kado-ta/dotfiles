#!/bin/bash -e
# curl | bash で、curl の失敗を検出するため。
set -o pipefail

if [ "$(uname)" != "Darwin" ] ; then
    echo "This is not macOS! codex setup is failed ;("
    exit 1
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

# worktree の中から実行すると、リンクが worktree を指し、worktree を消すと警告なしに切れる。
# worktree では .git がファイルになるので、git を使わずに判定する。
if [ -f "$SCRIPT_DIR/../.git" ]; then
    echo "$SCRIPT_DIR is in a git worktree. Run this script from the main checkout (~/dotfiles) instead." >&2
    exit 1
fi

CODEX_DIR="$HOME/.codex"

echo "SCRIPT_DIR: $SCRIPT_DIR"
echo "CODEX_DIR: $CODEX_DIR"

if [ ! -d $CODEX_DIR ]; then mkdir -p $CODEX_DIR; fi
ln -snfv "$SCRIPT_DIR/AGENTS.md" "$CODEX_DIR/AGENTS.md"

# execpolicy の規則。Codex はリンクを読まないので、通常のファイルとしてコピーする。
# default.rules は TUI の「今後は聞かない」の書き込み先なので、別の名前にする。
# 検査とコピーは同じ一時の写しで行い、作業ツリーのファイルが途中で書き換えられても、検査していない中身を入れない。
# 写しは書き込める権限にする（読み取り専用の写しがあると、最後の rm が確認を求める）。
RULES_SRC="$SCRIPT_DIR/rules/dotfiles.rules"
RULES_DEST="$CODEX_DIR/rules/dotfiles.rules"
RULES_TMP=$(mktemp -d "${TMPDIR:-/tmp}/codex-rules.XXXXXX")
trap 'rm -r "$RULES_TMP" || true' EXIT
mkdir "$RULES_TMP/rules"
RULES_NEW="$RULES_TMP/rules/dotfiles.rules"
install -m 0600 "$RULES_SRC" "$RULES_NEW"

# allow は当たったコマンドを sandbox の外で確認なしに動かすので、入れない。decision を省くと allow になるので、
# コメントを除いて、prefix_rule の数と decision = "prompt" / "forbidden" の数が合うことも確かめる。
RULES_CODE=$(sed 's/#.*//' "$RULES_NEW")
RULE_COUNT=$(printf '%s\n' "$RULES_CODE" | awk '{ n += gsub(/prefix_rule[[:space:]]*\(/, "") } END { print n + 0 }')
DECIDED_COUNT=$(printf '%s\n' "$RULES_CODE" | awk '{ n += gsub(/decision[[:space:]]*=[[:space:]]*"(prompt|forbidden)"/, "") } END { print n + 0 }')
if printf '%s\n' "$RULES_CODE" | grep -nE "[\"']allow[\"']" || [ "$RULE_COUNT" -ne "$DECIDED_COUNT" ]; then
    echo "$RULES_SRC has an allow rule, or a prefix_rule without decision = \"prompt\" or \"forbidden\" (an omitted decision means allow). The rules are not installed." >&2
    exit 1
fi

# codex exec と codex review は承認が never なので、git の読み取りに当たる規則があると、レビューで拒否される。
for GIT_CMD in status diff log show; do
    if ! RULES_RESULT=$(codex execpolicy check --resolve-host-executables --rules "$RULES_NEW" -- git "$GIT_CMD"); then
        echo "codex execpolicy check failed on $RULES_SRC (is codex installed?). The rules are not installed." >&2
        exit 1
    fi
    if [ "$RULES_RESULT" != '{"matchedRules":[]}' ]; then
        echo "A rule in $RULES_SRC matches \`git $GIT_CMD\`, which Codex reviews use: $RULES_RESULT. The rules are not installed." >&2
        exit 1
    fi
done

# Codex は ~/.codex/rules の、拡張子が rules の通常のファイル（リンクを除き、. で始まる名前も含む）を
# バイト順に全部読み、1 つでも読めないと codex exec と codex review が止まる。入れた後と同じ組み合わせと順で、
# 読み込めることを確かめる（find -type f はリンクを含めない。.rules という名前だけのファイルは Codex が読まない）。
if [ -d "$CODEX_DIR/rules" ]; then
    find "$CODEX_DIR/rules" -maxdepth 1 -type f -name '*.rules' ! -name .rules ! -name dotfiles.rules \
        -exec install -m 0600 {} "$RULES_TMP/rules/" \;
fi
RULES_ARGS=()
while IFS= read -r RULES_FILE; do
    RULES_ARGS+=(--rules "$RULES_FILE")
done < <(find "$RULES_TMP/rules" -maxdepth 1 -type f -name '*.rules' | LC_ALL=C sort)
if ! codex execpolicy check "${RULES_ARGS[@]}" -- git status > /dev/null; then
    echo "The rules in $CODEX_DIR/rules cannot be loaded together with $RULES_SRC (the file name in the error above is the one in $CODEX_DIR/rules). The rules are not installed." >&2
    exit 1
fi

# 絶対パスで書かれた規則は、実行ファイル名で照らす規則より先に当たる。先頭が絶対パスの allow があると、
# dotfiles.rules が候補に入れていない場所では、その実行ファイルが確認なしに動く。入れるのは止めずに警告する。
if grep -rnE 'pattern[[:space:]]*=[[:space:]]*\[[[:space:]]*"/.*decision[[:space:]]*=[[:space:]]*"allow"' "$RULES_TMP/rules"; then
    echo "WARNING: the allow rules above in $CODEX_DIR/rules start with an absolute path. They run that program outside the sandbox without asking, and win over dotfiles.rules for paths it does not list. Remove them unless you meant it." >&2
fi

# 作業ツリーのファイルをそのまま入れるので、今入っているものとの差分を表示する。
if [ -f "$RULES_DEST" ]; then
    diff -u "$RULES_DEST" "$RULES_NEW" || true
else
    echo "new file: $RULES_DEST"
fi
mkdir -p "$CODEX_DIR/rules"
install -m 0644 "$RULES_NEW" "$RULES_DEST"
echo "installed: $RULES_DEST"

# superpowers プラグイン
# codex plugin list はオンラインだとリモートのカタログを返し、インストール済みでもこのプラグインを含まない。
# そのため、codex plugin add が作るインストール先の有無で判定する。
if [ -d "$CODEX_DIR/plugins/cache/openai-curated/superpowers" ]; then
  echo "superpowers plugin already installed, skipping"
else
  codex plugin add superpowers@openai-curated
fi

# Understand Anything スキルをインストールする。
# Codex 用のスキルのリンクと、install.sh が最後に作る ~/.understand-anything-plugin の両方を完了の目印にする。
# ~/.understand-anything-plugin は他のホスト向けのインストールでも作られるため、それだけでは判定しない。
# -e はリンク先をたどるので、リンク切れは未インストールとみなし、install.sh で張り直す。
if [ -e "$HOME/.agents/skills/understand" ] && [ -e "$HOME/.understand-anything-plugin" ]; then
  echo "Understand Anything already installed, skipping"
else
  curl -fsSL https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.sh | bash -s codex
fi

# Claude Code でインストール済みの gstack を Codex でも使用できるようにする。
# 先に Claude Code で gstack をインストールしていることを前提とする。
cd ~/.claude/skills/gstack
./setup --host codex

echo "codex setup is succeeded!"
