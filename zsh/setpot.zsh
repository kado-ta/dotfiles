# zsh オプション
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
