# Sheldon で導入している zsh-users/zsh-autosuggestions の設定。
export ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=242'
# bin/.zshrc の atuin の初期化は、候補の出どころを atuin だけにする。atuin は Ctrl-R だけに使い、候補は zsh の履歴から出す。
ZSH_AUTOSUGGEST_STRATEGY=(history)
