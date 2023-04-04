#!/bin/bash -e

IGNORE_PATTERN="^\.(git|travis|circleci)"

echo "Create dotfile links."

# ~/dotfiles/ 下の . ではじまるファイル全てのシンボリックリンクを ~/ 下に作成する。
for dotfile in .??*; do
    [[ $dotfile =~ $IGNORE_PATTERN ]] && continue
    #
    # ln : ハード・リンク／シンボリック・リンクを作成する。 `ln [オプション] ファイル名 リンク名`
    # -s : シンボリック・リンクを作成する。
    # -n : リンクの作成場所として指定したディレクトリがシンボリック・リンクだった場合、参照先にリンクを作るのではなく、シンボリックリンクそのものを置き換える。 （-f と組み合わせて使用する。）
    # -f : リンクファイルと同じ名前のファイルがあっても強制的に上書きする。
    # -v : リンク作成の途中経過を表示する。
    ln -snfv "$(pwd)/$dotfile" "$HOME/$dotfile"
done

echo "Success"
