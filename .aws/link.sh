#!/bin/bash -e

SCRIPT_DIR=$(cd $(dirname $0) && pwd)
echo "SCRIPT_DIR: $SCRIPT_DIR"

AWS_CONFIG_DIR="$HOME/.aws"
echo "AWS_CONFIG_DIR: $AWS_CONFIG_DIR"

ln -snfv "$SCRIPT_DIR/config"      "$AWS_CONFIG_DIR/"
ln -snfv "$SCRIPT_DIR/credentials" "$AWS_CONFIG_DIR/"

echo "Success!"
