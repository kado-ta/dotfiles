# コマンドのエイリアス定義
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
