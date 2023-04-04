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
# zi
########################################
if [[ ! -f $HOME/.zi/bin/zi.zsh ]]; then
  print -P "%F{33}▓▒░ %F{160}Installing (%F{33}z-shell/zi%F{160})…%f"
  command mkdir -p "$HOME/.zi" && command chmod g-rwX "$HOME/.zi"
  command git clone -q --depth=1 --branch "main" https://github.com/z-shell/zi "$HOME/.zi/bin" && \
    print -P "%F{33}▓▒░ %F{34}Installation successful.%f%b" || \
    print -P "%F{160}▓▒░ The clone has failed.%f%b"
fi
source "$HOME/.zi/bin/zi.zsh"
autoload -Uz _zi
(( ${+_comps} )) && _comps[zi]=_zi
# examples here -> https://z-shell.pages.dev/docs/gallery/collection
zicompinit # <- https://z-shell.pages.dev/docs/gallery/collection#minimal

########################################
# zi プラグイン
########################################
# 補完
# zinit ice wait lucid
# zi light zsh-users/zsh-completions

zinit ice wait lucid atload '_zsh_autosuggest_start'
zi light zsh-users/zsh-autosuggestions
ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=242'

# シンタックスハイライト
zinit ice wait lucid
zi light zdharma/fast-syntax-highlighting

# Ctrl-R で、コマンド履歴を複数キーワードの AND で検索する
zinit ice wait lucid
zi light z-shell/H-S-MW

# 作業ディレクトリの .env から環境変数をロードする
zinit ice wait lucid
zi snippet 'https://github.com/johnhamelink/env-zsh/blob/master/env.plugin.zsh'
