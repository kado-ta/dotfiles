#!/bin/bash -e

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
AWS_CONFIG_DIR="$HOME/.aws"

echo "SCRIPT_DIR:     $SCRIPT_DIR"
echo "AWS_CONFIG_DIR: $AWS_CONFIG_DIR"

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
  ln -snfv $AWS_CONFIG_FILE "$AWS_CONFIG_DIR/"
fi

AWS_CREDS_FILE="$SCRIPT_DIR/credentials"
if [ -e $AWS_CREDS_FILE ]; then
  ln -snfv $AWS_CREDS_FILE "$AWS_CONFIG_DIR/"
fi

echo "Success!"
