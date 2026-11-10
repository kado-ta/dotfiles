#!/bin/bash -e

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
AWS_CONFIG_DIR="$HOME/.aws"

echo "SCRIPT_DIR:     $SCRIPT_DIR"
echo "AWS_CONFIG_DIR: $AWS_CONFIG_DIR"

# リンク先が実体（シンボリックリンク以外）のときは止める。
# ln -snf は実ファイルを黙って削除するため、既存の認証情報が失われる。
link() {
  local src="$1" dest="$2"
  if [ -e "${dest}" ] && [ ! -L "${dest}" ]; then
    echo "Not a symlink: ${dest}. Move it to ${src}, then rerun." >&2
    exit 1
  fi
  ln -snfv "${src}" "${dest}"
}

if [ ! -d $AWS_CONFIG_DIR ]; then mkdir $AWS_CONFIG_DIR; fi

if [ ! -e "$SCRIPT_DIR/config" ]; then
  cat <<'EOF' >"$SCRIPT_DIR/config"
[default]
region = ap-northeast-1
EOF
fi

if [ ! -e "$SCRIPT_DIR/credentials" ]; then
  touch "$SCRIPT_DIR/credentials"
  chmod 600 "$SCRIPT_DIR/credentials"
fi

AWS_CONFIG_FILE="$SCRIPT_DIR/config"
if [ -e $AWS_CONFIG_FILE ]; then
  link "$AWS_CONFIG_FILE" "$AWS_CONFIG_DIR/config"
fi

AWS_CREDS_FILE="$SCRIPT_DIR/credentials"
if [ -e $AWS_CREDS_FILE ]; then
  link "$AWS_CREDS_FILE" "$AWS_CONFIG_DIR/credentials"
fi

echo "Success!"
