# コマンドのエイリアス定義
case ${OSTYPE} in
    darwin*)
        # Mac用の設定
        export CLICOLOR=1
        alias ls='ls -G -F'
        # Typora でファイルを開く（例: typora hoge.md）
        alias typora='open -a Typora'
        ;;
    linux*)
        # Linux用の設定
        alias ls='ls -F --color=auto'
        ;;
esac

alias la='ls -al'
alias ll='ls -l'

alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'

alias mkdir='mkdir -p'

alias be='bundle exec'

# sudo の後のコマンドでエイリアスを有効にする
alias sudo='sudo '

# グローバルエイリアス
alias -g L='| less'
alias -g G='| grep'

# Codex 設定を ~/dotfiles/.codex で管理する設定と同期するコマンド
# - 同期実行: codex-config-sync
# - Dry Run: codex-config-sync --dry-run
alias codex-config-sync='uv run --no-project --with "tomlkit>=0.13,<1" python "$HOME/dotfiles/.codex/sync.py"'

# Codex が変更した ~/.codex/config.toml の内容を
# 選択的に ~/dotfiles/.codex/config.base.toml へ反映する。
# - 変更候補を確認(差分のみ表示): codex-config-import
# - 指定した設定のみインポート: codex-config-import --key model_reasoning_effort --apply
# - Git管理済みの設定項目をまとめてインポート: codex-config-import --all-managed --apply
# - Codex が新しく追加した設定を明示的にインポート: codex-config-import --key features.multi_agent --apply
alias codex-config-import='uv run --no-project --with "tomlkit>=0.13,<1" python "$HOME/dotfiles/.codex/import.py"'

# Claude Code / Codex の起動なしに Understand Anything スキルのダッシュボードを起動する。
function ua-dashboard() {
  npx https://github.com/Egonex-AI/Understand-Anything/releases/latest/download/understand-anything-viewer.tgz "${1:-.}"
}

# gstack を最新版へ fast-forward し、./setup --refresh-registered を実行する（/gstack-upgrade の CLI 版）。
# git リポジトリ内で実行するとそのリポジトリの検査も走るため、ホームディレクトリから実行する。
# - アップグレード: gstack-upgrade
# - 確認のみ: gstack-upgrade --check
function gstack-upgrade() {
  (cd ~ && "$HOME/.claude/skills/gstack/bin/gstack-upgrade" "$@")
}
