#!/bin/bash -e

if [ "$(uname)" != "Darwin" ] ; then
	echo "This is not macOS!"
	exit 1
fi

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
echo "SCRIPT_DIR is $SCRIPT_DIR"

for dotfile in "${SCRIPT_DIR}"/.??* ; do
    # シンボリック・リンク作成から除外するファイル／ディレクトリを指定する。
    [[ "$dotfile" == "${SCRIPT_DIR}/.env" ]] && continue
    [[ "$dotfile" == "${SCRIPT_DIR}/.git" ]] && continue
    [[ "$dotfile" == "${SCRIPT_DIR}/.gitignore" ]] && continue
    [[ "$dotfile" == "${SCRIPT_DIR}/.github" ]] && continue
    [[ "$dotfile" == "${SCRIPT_DIR}/.DS_Store" ]] && continue

    # ln : ハード・リンク／シンボリック・リンクを作成する。 `ln [オプション] ファイル名 リンク名`
    # -s : シンボリック・リンクを作成する。
    # -n : リンクの作成場所として指定したディレクトリがシンボリック・リンクだった場合、
    #        参照先にリンクを作るのではなく、シンボリックリンクそのものを置き換える。 （-f と組み合わせて使用する。）
    # -f : リンクファイルと同じ名前のファイルがあっても強制的に上書きする。
    # -v : リンク作成の途中経過を表示する。
    ln -snfv "$dotfile" "$HOME"
done

echo "Success!"
