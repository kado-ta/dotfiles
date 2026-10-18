#!/usr/bin/env -S uv run --script

"""Codex CLI の設定ファイルを同期する。

dotfiles の config.base.toml と ~/.codex/config.local.toml を、
既存の ~/.codex/config.toml にマージして書き込む。
config.base.toml 内の ~/ は実行環境のホームディレクトリの絶対パスへ展開する。
[projects] などの信頼設定は Codex 側の管理に任せ、既存の値を保持する。
書き込み前にバックアップを作成し、--dry-run では差分の表示だけを行う。
"""

# インラインスクリプトメタデータ (依存関係の定義)
# このスクリプトを uv run で実行すると、tomlkit を一時的な環境へインストールした上で実行する。
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "tomlkit>=0.13,<1",
# ]
# ///

import argparse
import copy
import difflib
import os
import re
import shutil
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

import tomlkit
from tomlkit.items import String, Table


# 設定ファイルのパス
DOTFILES_DIR = Path(__file__).resolve().parent
BASE_CONFIG = DOTFILES_DIR / "config.base.toml"

CODEX_DIR = Path(
    os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
).expanduser()

LOCAL_CONFIG = CODEX_DIR / "config.local.toml"
TARGET_CONFIG = CODEX_DIR / "config.toml"

# パスの途中ではない ~/ (文字列の先頭や : などの区切り文字の直後) に一致する
HOME_DIR = str(Path.home())
TILDE_PATTERN = re.compile(r"(?<![\w.~/-])~(?=/)")


def load_config(path):
    """TOML を読み込む。存在しなければ空の設定を返す。"""
    if not path.exists():
        return tomlkit.document()

    return tomlkit.parse(path.read_text(encoding="utf-8"))


def expand_home(text):
    """文字列内の ~/ をホームディレクトリの絶対パスに置き換える。"""
    return TILDE_PATTERN.sub(lambda _: HOME_DIR, text)


def map_strings(value, convert):
    """TOML の値に含まれる文字列を、引用符の種類を保ったまま変換する。"""
    if isinstance(value, Mapping):
        for key in list(value.keys()):
            converted = map_strings(value[key], convert)
            if converted is not value[key]:
                value[key] = converted
        return value

    if isinstance(value, list):
        for index, item in enumerate(value):
            converted = map_strings(item, convert)
            if converted is not item:
                value[index] = converted
        return value

    if isinstance(value, String):
        converted = convert(str(value))
        if converted == str(value):
            return value
        return tomlkit.string(
            converted,
            literal=value.type.is_literal(),
            multiline=value.type.is_multiline(),
        )

    return value


def merge_config(destination, source):
    """source の設定を destination に再帰的に上書きする。"""
    for key, value in source.items():
        if (
            key in destination
            and isinstance(destination[key], Table)
            and isinstance(value, Table)
        ):
            merge_config(destination[key], value)
        else:
            destination[key] = copy.deepcopy(value)


def atomic_write(path, content):
    """一時ファイルを経由して設定を更新する。"""
    fd, tmp_path = tempfile.mkstemp(
        prefix=".config.toml.",
        dir=path.parent,
    )

    try:
        os.fchmod(fd, 0o600)

        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())

        os.replace(tmp_path, path)

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main():
    """Codex設定をマージし ~/.codex/config.toml を更新する。"""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="変更内容を表示するだけで書き込まない",
    )
    args = parser.parse_args()

    if not BASE_CONFIG.is_file():
        raise FileNotFoundError(BASE_CONFIG)

    if TARGET_CONFIG.is_symlink():
        raise RuntimeError(
            "config.toml がシンボリックリンクです。"
            "通常ファイルに変更してください。"
        )

    CODEX_DIR.mkdir(parents=True, exist_ok=True)

    # 各設定を読み込む
    base = load_config(BASE_CONFIG)
    local = load_config(LOCAL_CONFIG)
    current = load_config(TARGET_CONFIG)

    # 共通設定の ~/ を実行環境の絶対パスへ展開
    map_strings(base, expand_home)

    # 信頼設定は Codex の管理に限定する
    for name, config in [
        ("config.base.toml", base),
        ("config.local.toml", local),
    ]:
        if "projects" in config:
            raise ValueError(
                f"{name} に [projects] を記述しないでください"
            )

    # 既存の設定をベースに共通設定、ローカル設定を適用
    merged = current
    merge_config(merged, base)
    merge_config(merged, local)

    # 出力を生成し、TOML 構文を検証
    result = tomlkit.dumps(merged)
    tomlkit.parse(result)

    original = (
        TARGET_CONFIG.read_text(encoding="utf-8")
        if TARGET_CONFIG.exists()
        else ""
    )

    if original == result:
        print("変更なし")
        return

    # dry-run なら差分を表示
    if args.dry_run:
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            result.splitlines(keepends=True),
            fromfile="config.toml (current)",
            tofile="config.toml (merged)",
        )
        print("".join(diff), end="")
        return

    # 同期直前の変更を検出
    if TARGET_CONFIG.exists():
        if TARGET_CONFIG.read_text(encoding="utf-8") != original:
            raise RuntimeError(
                "同期中に config.toml が変更されました"
            )

        # 更新前の設定をバックアップ
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = CODEX_DIR / f"config.toml.backup-{timestamp}"

        shutil.copy2(TARGET_CONFIG, backup)
        backup.chmod(0o600)

        print(f"Backup: {backup}")

    # 実ファイルを更新
    atomic_write(TARGET_CONFIG, result)

    print(f"Updated: {TARGET_CONFIG}")


if __name__ == "__main__":
    main()
