# 少し凝った .zshrc
# License : MIT
# http://mollifier.mit-license.org/

########################################
# 環境変数
########################################
export LANG=ja_JP.UTF-8
export PATH=/usr/local/bin:/usr/ilocal/sbin:$PATH

########################################
# アプリケーション設定
########################################
# asdf 本体
. /opt/homebrew/opt/asdf/libexec/asdf.sh
# asdf 補完
fpath=(${ASDF_DIR}/completions $fpath)

# gloud (GCP CLI)
source '/opt/homebrew/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/completion.zsh.inc'
source '/opt/homebrew/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.zsh.inc'

########################################
# zsh 設定
########################################
# 色を使用出来るようにする
autoload -Uz colors
colors

# emacs 風キーバインドにする
bindkey -e

# ヒストリーの設定
HISTFILE=~/.zsh_history
HISTSIZE=100000  # メモリ上に保存する履歴のサイズ
SAVEHIST=1000000 # HISTFILE に保存する履歴のサイズ

# プロンプト
# 1行表示
# PROMPT="%~ %# "
# 2行表示
PROMPT="%{${fg[green]}%}[%n@%m]%{${reset_color}%} %~
%# "

# 単語の区切り文字を指定する
autoload -Uz select-word-style
select-word-style default
# ここで指定した文字は単語区切りとみなされる
# / も区切りと扱うので、^W でディレクトリ１つ分を削除できる
zstyle ':zle:*' word-chars " /=;@:{},|"
zstyle ':zle:*' word-style unspecified

# 補完機能を有効にする
autoload -Uz compinit && compinit

# 補完で小文字でも大文字にマッチさせる
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'

# ../ の後は今いるディレクトリを補完しない
zstyle ':completion:*' ignore-parents parent pwd ..

# sudo の後ろでコマンド名を補完する
zstyle ':completion:*:sudo:*' command-path /usr/local/sbin /usr/local/bin \
                              /usr/sbin /usr/bin /sbin /bin /usr/X11R6/bin

# ps コマンドのプロセス名補完
zstyle ':completion:*:processes' command 'ps x -o pid,s,args'

########################################
# zsh オプション
########################################
setopt interactive_comments # '#' 以降をコメントとして扱う
setopt ignore_eof           # Ctrl+D で zsh を終了しない
setopt print_eight_bit      # 日本語ファイル名を表示可能にする
setopt no_beep              # beep を無効にする
setopt no_flow_control      # フローコントロールを無効にする
setopt auto_cd              # ディレクトリ名だけでcdする
setopt auto_pushd           # cd したら自動的に pushd する
setopt pushd_ignore_dups    # 重複したディレクトリを追加しない
setopt inc_append_history   # 実行時に履歴をファイルにに追加していく
setopt hist_ignore_all_dups # 同じコマンドをヒストリに残さない
setopt share_history        # 同時に起動した zsh の間でヒストリを共有する
setopt hist_ignore_space    # スペースから始まるコマンド行はヒストリに残さない
setopt hist_reduce_blanks   # ヒストリに保存するときに余分なスペースを削除する
setopt extended_glob        # 高機能なワイルドカード展開を使用する

########################################
# キーバインド
########################################
# ^R で履歴検索をするときに * でワイルドカードを使用出来るようにする
bindkey '^R' history-incremental-pattern-search-backward

########################################
# エイリアス
########################################
case ${OSTYPE} in
    darwin*)
        # Mac用の設定
        export CLICOLOR=1
        alias ls='ls -G -F'
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

########################################
# Starship
########################################
eval "$(starship init zsh)"

########################################
# Sheldon (zsh プラグイン・マネージャー)
########################################
eval "$(sheldon source)"

# Sheldon で導入している zsh-users/zsh-autosuggestions の設定。
ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=242'
