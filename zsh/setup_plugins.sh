#!/bin/bash -e

# NOTE: 先に ./setup.sh を実行しておくこと。
# Sheldon をインストールしたら、シェル起動の度に自動チェック → インストールされるのでは？
# 手動インストールの悪影響はないので、ここに置いておいて問題ないでしょう。
sheldon lock --reinstall
