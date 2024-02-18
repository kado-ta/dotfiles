########################################
# 環境変数
########################################
export LANG=ja_JP.UTF-8
export PATH=/usr/local/bin:/usr/sbin:$PATH

########################################
# zsh 本体設定
########################################
# プロンプト
# 1行表示
# PROMPT="%~ %# "
# 2行表示
PROMPT="%{${fg[green]}%}[%n@%m]%{${reset_color}%} %~
%# "

# ヒストリーの設定
HISTFILE=~/.zsh_history
HISTSIZE=100000  # メモリ上に保存する履歴のサイズ
SAVEHIST=1000000 # HISTFILE に保存する履歴のサイズ

########################################
# Starship
########################################
eval "$(starship init zsh)"

########################################
# Sheldon (zsh プラグイン・マネージャー)
########################################
eval "$(sheldon source)"

########################################
# asdf
########################################
. /opt/homebrew/opt/asdf/libexec/asdf.sh

########################################
# asdf-direnv
########################################
# `asdf direnv setup --shell zsh --version latest` 実行により、下の行と必要なファイル追加される。
# source "${XDG_CONFIG_HOME:-$HOME/.config}/asdf-direnv/zshrc"
# しかし、この行は Salesforce DataLoader 起動時にエラーを発生させてしまうため、下記の通り実行タイミングを制御する。
SCRIPT_NAME="$(basename -- "$0")"
if [[ $SCRIPT_NAME != "dataloader" && $SCRIPT_NAME != "dataloader_console" ]]; then
  source "${XDG_CONFIG_HOME:-$HOME/.config}/asdf-direnv/zshrc"
fi
