#!/usr/bin/env -S uv run --script

"""Codex設定を dotfiles へ取り込む。

Codex が変更した ~/.codex/config.toml の内容を
選択的に ~/dotfiles/.codex/config.base.toml へ反映する。
ホームディレクトリの絶対パスは ~/ に置き換えて取り込む。

変更候補を確認(差分のみ表示)
codex-config-import

指定した設定のみインポート
codex-config-import --key model_reasoning_effort --apply

Git管理済みの設定項目をまとめてインポート
codex-config-import --all-managed --apply

Codex が新しく追加した設定を明示的にインポート
codex-config-import --key features.multi_agent --apply
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
import json
import os
import re
import shutil
import stat
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

import tomlkit
from tomlkit.items import String, Table


DOTFILES_DIR = Path(__file__).resolve().parent
BASE_CONFIG = DOTFILES_DIR / "config.base.toml"

CODEX_DIR = Path(
    os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
).expanduser()

LOCAL_CONFIG = CODEX_DIR / "config.local.toml"
SOURCE_CONFIG = CODEX_DIR / "config.toml"

MISSING = object()

# パスの途中ではない (文字列の先頭や : などの区切り文字の直後の) ホームディレクトリに一致する
HOME_DIR = str(Path.home())
HOME_PATTERN = re.compile(r"(?<![\w.~/-])" + re.escape(HOME_DIR) + r"(?=/)")

# Git 管理への取り込みを禁止する設定名
SENSITIVE_PATTERN = re.compile(
    r"secret|password|token|api[_-]?key|private[_-]?key",
    re.IGNORECASE,
)
SENSITIVE_KEYS = {
    "env",
    "headers",
    "http_headers",
    "env_http_headers",
    "authorization",
}


def load_config(path):
    """TOML を読み込み、解析結果と元のテキストを返す。"""
    if not path.exists():
        return tomlkit.document(), ""

    content = path.read_text(encoding="utf-8")
    return tomlkit.parse(content), content


def leaf_paths(node, prefix=()):
    """TOML の設定項目を階層パスとして列挙する。"""
    for key, value in node.items():
        path = prefix + (str(key),)

        if isinstance(value, Table):
            yield from leaf_paths(value, path)
        else:
            yield path


def lookup(node, path):
    """階層パスに対応する設定値を取得する。"""
    for key in path:
        if not isinstance(node, Mapping) or key not in node:
            return MISSING
        node = node[key]

    return node


def is_local_override(local, path):
    """ローカル設定が指定パスを管理しているか判定する。"""
    node = local

    for key in path:
        if not isinstance(node, Mapping):
            return True

        if key not in node:
            return False

        node = node[key]

    return True


def is_protected(path):
    """信頼設定や秘密情報に該当するパスを検出する。"""
    if path[0] == "projects":
        return True

    return any(
        key.lower() in SENSITIVE_KEYS
        or SENSITIVE_PATTERN.search(key)
        for key in path
    )


def parse_key(text):
    """TOML の dotted key を階層パスに変換する。"""
    document = tomlkit.parse(f"{text} = 0\n")

    path = []
    node = document

    while isinstance(node, Mapping):
        keys = list(node.keys())

        if len(keys) != 1:
            raise ValueError(f"不正な設定キー: {text}")

        key = keys[0]
        path.append(str(key))
        node = node[key]

    return tuple(path)


def format_key(path):
    """階層パスを TOML の dotted key として表示する。"""
    parts = []

    for key in path:
        if re.fullmatch(r"[A-Za-z0-9_-]+", key):
            parts.append(key)
        else:
            parts.append(json.dumps(key, ensure_ascii=False))

    return ".".join(parts)


def plain(value):
    """比較用に TOML の値を Python の値へ変換する。"""
    if value is MISSING:
        return MISSING

    return value.unwrap() if hasattr(value, "unwrap") else value


def contract_home(text):
    """文字列内のホームディレクトリの絶対パスを ~ に置き換える。"""
    return HOME_PATTERN.sub("~", text)


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


def set_value(document, path, value):
    """階層構造を保持して設定値を書き込む。"""
    node = document

    for key in path[:-1]:
        if key not in node:
            node[key] = tomlkit.table()

        node = node[key]

        if not isinstance(node, Table):
            raise ValueError(
                f"テーブルではない項目: {format_key(path)}"
            )

    node[path[-1]] = copy.deepcopy(value)


def atomic_write(path, content):
    """元のファイル権限を保持してアトミックに書き込む。"""
    mode = stat.S_IMODE(path.stat().st_mode)

    fd, tmp_path = tempfile.mkstemp(
        prefix=".config.base.",
        dir=path.parent,
    )

    try:
        os.fchmod(fd, mode)

        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())

        os.replace(tmp_path, path)

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main():
    """# Codex が変更した ~/.codex/config.toml の内容を
    ~/dotfiles/.codex/config.base.toml へ反映する。"""

    parser = argparse.ArgumentParser(
        description="Codex の設定変更を dotfiles に取り込む"
    )

    parser.add_argument(
        "--key",
        action="append",
        default=[],
        help="取り込む設定キー。複数指定可能",
    )

    parser.add_argument(
        "--all-managed",
        action="store_true",
        help="Git 管理済みの設定項目をすべて比較・取り込む",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="変更内容を config.base.toml に書き込む",
    )

    args = parser.parse_args()

    if args.apply and not (args.key or args.all_managed):
        parser.error(
            "--apply には --key または --all-managed が必要です"
        )

    if not BASE_CONFIG.is_file():
        parser.error(f"共通設定が存在しません: {BASE_CONFIG}")

    if BASE_CONFIG.is_symlink():
        parser.error("共通設定は通常ファイルにしてください")

    if not SOURCE_CONFIG.is_file():
        parser.error(f"Codex 設定が存在しません: {SOURCE_CONFIG}")

    base, base_text = load_config(BASE_CONFIG)
    local, local_text = load_config(LOCAL_CONFIG)
    source, source_text = load_config(SOURCE_CONFIG)

    if "projects" in base or "projects" in local:
        parser.error(
            "[projects] は config.toml だけで管理してください"
        )

    managed = set(leaf_paths(base))

    # 明示指定がなければ Git 管理済み項目を比較
    if args.key:
        selected = {parse_key(key) for key in args.key}
    else:
        selected = set(managed)

    if args.all_managed:
        selected |= managed

    changes = []

    for path in sorted(selected):
        name = format_key(path)

        if is_protected(path):
            print(f"SKIP (protected): {name}")
            continue

        if is_local_override(local, path):
            print(f"SKIP (local): {name}")
            continue

        current_value = lookup(source, path)

        if current_value is MISSING:
            print(f"SKIP (missing): {name}")
            continue

        # テーブル全体の取り込みを禁止し、項目単位に限定
        if isinstance(current_value, Mapping):
            print(f"SKIP (table): {name}")
            continue

        # ホームディレクトリを ~/ に置き換えてから比較・取り込む
        current_value = map_strings(
            copy.deepcopy(current_value), contract_home
        )

        base_value = lookup(base, path)

        if plain(current_value) == plain(base_value):
            continue

        set_value(base, path, current_value)
        changes.append(name)

    # TOML の再生成と構文検証
    result = tomlkit.dumps(base)
    tomlkit.parse(result)

    # Git 管理対象外の新規設定を表示する
    unmanaged = sorted(
        path
        for path in set(leaf_paths(source)) - managed
        if not is_protected(path)
        and not is_local_override(local, path)
    )

    if unmanaged:
        print("\nGit 管理されていない設定:")
        for path in unmanaged:
            print(f"  {format_key(path)}")

    if not changes:
        print("\n取り込む変更はありません")
        return

    print("\n変更対象:")
    for name in changes:
        print(f"  {name}")

    print("\n差分:")

    diff = difflib.unified_diff(
        base_text.splitlines(keepends=True),
        result.splitlines(keepends=True),
        fromfile="config.base.toml (current)",
        tofile="config.base.toml (imported)",
    )

    print("".join(diff), end="")

    if not args.apply:
        print("\nDry Run: ファイルは変更していません")
        return

    # 読み込み後にファイルが変更された場合は中止する
    for path, original in [
        (BASE_CONFIG, base_text),
        (LOCAL_CONFIG, local_text),
        (SOURCE_CONFIG, source_text),
    ]:
        current = (
            path.read_text(encoding="utf-8")
            if path.exists()
            else ""
        )

        if current != original:
            raise RuntimeError(
                f"実行中に設定が変更されました: {path}"
            )

    # バックアップは Git リポジトリ外に保存する
    backup_dir = CODEX_DIR / "config-import-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.chmod(0o700)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = backup_dir / f"config.base-{timestamp}.toml"

    shutil.copy2(BASE_CONFIG, backup)
    backup.chmod(0o600)

    print(f"\nBackup: {backup}")

    atomic_write(BASE_CONFIG, result)

    print(f"Updated: {BASE_CONFIG}")


if __name__ == "__main__":
    main()
