"""update-modern-web-guidance.py の単体テスト。

偽のリポジトリ（スクリプトの写し、mise の設定、取り込み済みのスキル、check-repo.py の偽物）と、
npm・skillspector の偽物を置いた PATH で、スクリプトをサブプロセスとして実行し、書き換えたファイル・出力・
終了コードを確かめる。npm の偽物は、テストで作った tarball を `npm pack` の結果として渡す。
スクリプトは、このテストを実行している Python で動かす（CI では macOS の /usr/bin/python3）。

実行: python3 -B claude/scripts/test-update-modern-web-guidance.py
"""
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
SCRIPT_NAME = "update-modern-web-guidance.py"

SKILL_VERSION = "2026_11_20-abcdef01"

# 上流の SKILL.md の要点をまねる（v1.0.1 の構成）。
UPSTREAM_SKILL = f"""---
name: modern-web-guidance
description: |
  Search tool for modern web development best practices.
---

# Modern Web Guidance

## Primary Workflow

### Step 1. Search Use Cases

Run `modern-web-guidance` directly with `npx` using a **2–5 word** query:

```sh
npx -y modern-web-guidance@latest search "<query>" --skill-version {SKILL_VERSION}
```

### Step 2. Retrieve Best Practices

```sh
npx -y modern-web-guidance@latest retrieve "<id>"
```

## Using npx / pnpx

- **Runner & Permissions**: Prefer `pnpx` over `npx` if `pnpm` is available. Allowlist `npx -y modern-web-guidance@latest *` (or `pnpx modern-web-guidance@latest *`).
- **Offline**: If the command hangs due to being offline, retry with `npx --offline …`.

## Guidelines

- Always search **first**.
"""

CHROME_SKILL = """---
name: chrome-extensions
description: >
  Build and publish Chrome Extensions using Manifest V3 best practices.
---

# Chrome Extensions

See `references/extensions/storage.md`.
"""

LICENSE = "Apache License\nVersion 2.0, January 2004\n"
PACKAGE_JSON = '{"name": "modern-web-guidance", "version": "1.0.2", "bin": {"modern-web-guidance": "skills/modern-web-guidance/modern-web.mjs"}}'

MISE_CONFIG = """[tools]
"npm:@salesforce/cli" = "latest"
# modern-web-guidance のコメント
"npm:modern-web-guidance" = "1.0.1"
uv = "latest"
"""

# npm の偽物。`npm view <pkg> version` は STUB_LATEST を返す。`npm pack <pkg>@<版> --pack-destination <dir> …` は、
# STUB_TGZ を <dir> に写し、本物と同じ形の JSON（filename を持つ配列）を返す。呼ばれた引数と作業ディレクトリを
# STUB_LOG に書く。
NPM_STUB = """#!/bin/sh
echo "npm $*" >> "$STUB_LOG"
echo "npm-cwd $1 $(pwd -P)" >> "$STUB_LOG"
if [ "$1" = "view" ]; then
  [ -n "$STUB_VIEW_FAIL" ] && exit 1
  echo "$STUB_LATEST"
  exit 0
fi
if [ "$1" = "pack" ]; then
  dest=""
  prev=""
  for a in "$@"; do
    [ "$prev" = "--pack-destination" ] && dest="$a"
    prev="$a"
  done
  cp "$STUB_TGZ" "$dest/pkg.tgz"
  echo '[{"filename": "pkg.tgz"}]'
  exit 0
fi
exit 1
"""

# skillspector の偽物。--output に、本物と同じ形の要約を書く。
SKILLSPECTOR_STUB = """#!/bin/sh
echo "skillspector $*" >> "$STUB_LOG"
out=""
prev=""
for a in "$@"; do
  [ "$prev" = "--output" ] && out="$a"
  prev="$a"
done
echo '{"risk_assessment": {"score": 20, "severity": "LOW", "recommendation": "SAFE"}, "issues": [{}]}' > "$out"
"""

# check-repo.py の偽物。呼ばれたことと引数を書き、STUB_CHECK_RC で終わる。
CHECK_REPO_STUB = ('import os, sys\n'
                   'with open(os.environ["STUB_LOG"], "a") as f:\n'
                   '    f.write("check-repo " + " ".join(sys.argv[1:]) + "\\n")\n'
                   'print("PASS stub")\n'
                   'sys.exit(int(os.environ.get("STUB_CHECK_RC", "0")))\n')

RUNNABLE = re.compile(r"\b(?:npx|pnpx|bunx)\b[^\n`]*?modern-web-guidance"
                      r"|\b(?:pnpm|bun|yarn|npm|deno)\b(?:\s+-\S+)*\s+(?:dlx|exec|x|run)\b[^\n`]*?modern-web-guidance"
                      r"|\b(?:pnpm|bun|yarn|npm|deno)\b[^\n`]*?modern-web-guidance[^\n`]*?\s(?:dlx|exec|x|run)\b")


def write_executable(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def make_tgz(path, files, extra=None):
    """files: {tarball の中のパス（package/ から下）: 中身}。extra: tarfile.TarInfo と中身の組の一覧。"""
    with tarfile.open(path, "w:gz") as tar:
        for name, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo("package/" + name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for info, data in extra or []:
            tar.addfile(info, io.BytesIO(data) if data is not None else None)


def member(name, data=b"x\n"):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    return info, data


def package_files(skill=UPSTREAM_SKILL, skill_version=SKILL_VERSION, chrome_skill=CHROME_SKILL,
                  package_json=PACKAGE_JSON):
    return {
        "LICENSE": LICENSE,
        "package.json": package_json,
        "skills/modern-web-guidance/SKILL.md": skill,
        "skills/modern-web-guidance/skill-version.txt": skill_version + "\n",
        "skills/modern-web-guidance/modern-web.mjs": "// cli\n",
        "skills/chrome-extensions/SKILL.md": chrome_skill,
        "skills/chrome-extensions/skill-version.txt": "2026_08_06-8570fe7c\n",
        "skills/chrome-extensions/references/extensions/storage.md": "# Storage\n",
    }


class UpdateModernWebGuidanceTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root)
        self.repo = self.root / "repo"
        self.stub = self.root / "stub"
        self.work = self.root / "work"
        self.log = self.root / "log"
        self.tgz = self.root / "pkg.tgz"
        script = self.repo / "claude" / "scripts" / SCRIPT_NAME
        script.parent.mkdir(parents=True)
        shutil.copy(SCRIPTS / SCRIPT_NAME, script)
        write_executable(self.repo / ".github" / "scripts" / "check-repo.py", CHECK_REPO_STUB)
        self.mise = self.repo / "mise" / "mise_config.toml"
        self.mise.parent.mkdir(parents=True)
        self.mise.write_text(MISE_CONFIG, encoding="utf-8")
        self.skills = self.repo / "claude" / "skills"
        # 取り込み済みの古い版。上流でなくなった参照ファイル（old.md）を含む。
        (self.skills / "modern-web-guidance").mkdir(parents=True)
        (self.skills / "modern-web-guidance" / "SKILL.md").write_text("old\n", encoding="utf-8")
        (self.skills / "chrome-extensions" / "references").mkdir(parents=True)
        (self.skills / "chrome-extensions" / "SKILL.md").write_text("old\n", encoding="utf-8")
        (self.skills / "chrome-extensions" / "references" / "old.md").write_text("old\n", encoding="utf-8")
        write_executable(self.stub / "npm", NPM_STUB)
        write_executable(self.stub / "skillspector", SKILLSPECTOR_STUB)
        # check-repo.py の偽物は PATH の python3 で動く。テストを動かしている Python を python3 として置く。
        (self.stub / "python3").symlink_to(sys.executable)
        self.work.mkdir()
        make_tgz(self.tgz, package_files())

    def run_script(self, *args, latest="1.0.2", env_extra=None):
        env = {
            "PATH": f"{self.stub}:/usr/bin:/bin",
            # スクリプトの一時ディレクトリを、テストの一時ディレクトリの下に作らせる（sandbox の中でも書ける場所）。
            "TMPDIR": str(self.root),
            "STUB_LOG": str(self.log),
            "STUB_LATEST": latest,
            "STUB_TGZ": str(self.tgz),
        }
        env.update(env_extra or {})
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(self.repo / "claude" / "scripts" / SCRIPT_NAME), *args],
            cwd=self.work, env=env, capture_output=True, text=True,
        )
        log = self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []
        return result, log

    def apply(self, **kwargs):
        result, log = self.run_script("--apply", **kwargs)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result, log

    def snapshot(self):
        """mise の設定とスキルのディレクトリの全ファイルの中身。書き込みがなかったことを確かめる。"""
        files = {p.relative_to(self.repo): p.read_bytes()
                 for p in sorted(self.skills.rglob("*")) if p.is_file()}
        files[Path("mise_config.toml")] = self.mise.read_bytes()
        return files

    def skill_text(self, *parts):
        return self.skills.joinpath(*parts).read_text(encoding="utf-8")

    def assert_apply_fails_without_writes(self, files=None, extra=None, reason=None):
        if files is not None or extra is not None:
            make_tgz(self.tgz, files if files is not None else package_files(), extra=extra)
        before = self.snapshot()
        result, _ = self.run_script("--apply")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)
        if reason:
            self.assertIn(reason, result.stderr)
        return result

    # --- 引数なし（update-skills.sh から呼ぶ）: 何も書かない

    def test_check_up_to_date(self):
        before = self.snapshot()
        result, log = self.run_script(latest="1.0.1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(line.startswith("npm pack") for line in log))
        self.assertIn("最新", result.stdout)

    def test_check_new_version_is_pending_without_writes(self):
        # 新しい版があっても書かない。取り込むまで、毎回 3 で知らせる。
        before = self.snapshot()
        for _ in range(2):
            result, log = self.run_script()
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(line.startswith("npm pack") for line in log))
        self.assertIn("1.0.2", result.stdout)
        self.assertIn("--apply", result.stdout)

    def test_check_older_latest_is_reported_as_failure(self):
        # レジストリの latest が固定している版より古い（取り下げ・非推奨など）。下げず、確かめるよう失敗で知らせる。
        before = self.snapshot()
        result, _ = self.run_script(latest="1.0.0")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("1.0.0", result.stderr)

    def test_npm_view_failure(self):
        before = self.snapshot()
        result, _ = self.run_script(env_extra={"STUB_VIEW_FAIL": "1"})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_missing_npm_is_a_failure(self):
        (self.stub / "npm").unlink()
        result, _ = self.run_script()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_non_release_latest(self):
        before = self.snapshot()
        result, _ = self.run_script(latest="1.1.0-beta.1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_pin_line_must_be_unique(self):
        for text in (MISE_CONFIG.replace('"npm:modern-web-guidance" = "1.0.1"\n', ""),
                     MISE_CONFIG + '"npm:modern-web-guidance" = "1.0.1"\n'):
            with self.subTest(text=text):
                self.mise.write_text(text, encoding="utf-8")
                before = self.snapshot()
                result, _ = self.run_script("--apply")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(self.snapshot(), before)

    def test_npm_runs_in_temporary_directory_with_private_cache(self):
        # npm は作業ディレクトリの .npmrc と共有のキャッシュ（~/.npm。sandbox の中から書ける）を読むので、
        # どちらも一時ディレクトリにする。
        _, log = self.run_script("--apply")
        cwds = [line.split(" ", 2) for line in log if line.startswith("npm-cwd ")]
        self.assertEqual([c[1] for c in cwds], ["view", "pack"], log)
        for _, _, cwd in cwds:
            self.assertNotEqual(cwd, str(self.work))
            self.assertNotIn(str(self.repo), cwd)
        for line in log:
            if line.startswith("npm view") or line.startswith("npm pack"):
                self.assertIn("--cache", line)
                self.assertIn("--prefix", line)
                self.assertIn("--registry=https://registry.npmjs.org/", line)
                self.assertNotIn(str(Path.home()), line)

    # --- --apply: 取り込む

    def test_apply_up_to_date_does_nothing(self):
        before = self.snapshot()
        result, log = self.run_script("--apply", latest="1.0.1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(line.startswith("npm pack") for line in log))

    def test_apply_bumps_pinned_version(self):
        self.apply()
        self.assertEqual(self.mise.read_text(encoding="utf-8"), MISE_CONFIG.replace('"1.0.1"', '"1.0.2"'))

    def test_apply_rewrites_commands_to_pinned_cli(self):
        self.apply()
        skill = self.skill_text("modern-web-guidance", "SKILL.md")
        self.assertIn(
            f'DISABLE_TELEMETRY=1 modern-web-guidance search "<query>" --skill-version {SKILL_VERSION}', skill)
        self.assertIn('DISABLE_TELEMETRY=1 modern-web-guidance retrieve "<id>"', skill)
        self.assertNotIn("npx -y modern-web-guidance@latest search", skill)

    def test_apply_replaces_npx_section_with_local_section(self):
        self.apply()
        skill = self.skill_text("modern-web-guidance", "SKILL.md")
        self.assertNotIn("## Using npx / pnpx", skill)
        self.assertNotIn("npx --offline", skill)
        self.assertNotIn("directly with `npx`", skill)
        self.assertIn("## Guidelines", skill)
        self.assertIn("## Running the CLI (local install)", skill)
        self.assertTrue(skill.rstrip().endswith("Google."), skill[-300:])

    def test_apply_leaves_no_runnable_npx(self):
        # 足したローカルの節も含め、npx 系で modern-web-guidance を動かす形を残さない（SkillSpector の RP1 にも当たる）。
        self.apply()
        runnable = RUNNABLE.search(self.skill_text("modern-web-guidance", "SKILL.md"))
        self.assertIsNone(runnable, runnable and runnable.group(0))

    def test_apply_marks_skill_as_modified(self):
        # Apache-2.0 の 4(b): 変更したファイルに、その旨を書く。frontmatter の直後に置く。
        self.apply()
        skill = self.skill_text("modern-web-guidance", "SKILL.md")
        frontmatter_end = skill.index("\n---\n", 4) + len("\n---\n")
        notice = skill[frontmatter_end:].lstrip("\n").splitlines()[0]
        self.assertTrue(notice.startswith("<!--"), notice)
        self.assertIn("modern-web-guidance@1.0.2", notice)
        self.assertIn("Apache-2.0", notice)
        self.assertTrue(skill.startswith("---\nname: modern-web-guidance\n"))

    def test_apply_copies_license(self):
        self.apply()
        self.assertEqual(self.skill_text("modern-web-guidance", "LICENSE.md"), LICENSE)
        self.assertEqual(self.skill_text("chrome-extensions", "LICENSE.md"), LICENSE)

    def test_apply_copies_chrome_extensions_as_is(self):
        self.apply()
        self.assertEqual(self.skill_text("chrome-extensions", "SKILL.md"), CHROME_SKILL)
        self.assertEqual(self.skill_text("chrome-extensions", "references", "extensions", "storage.md"),
                         "# Storage\n")
        self.assertEqual(self.skill_text("chrome-extensions", "skill-version.txt"), "2026_08_06-8570fe7c\n")

    def test_apply_removes_files_dropped_upstream(self):
        self.apply()
        self.assertFalse((self.skills / "chrome-extensions" / "references" / "old.md").exists())

    def test_apply_does_not_copy_cli_into_skill(self):
        # CLI は mise で入れるので、スキルのディレクトリには SKILL.md と LICENSE.md だけを置く。
        self.apply()
        names = sorted(p.name for p in (self.skills / "modern-web-guidance").iterdir())
        self.assertEqual(names, ["LICENSE.md", "SKILL.md"])

    def test_apply_leaves_no_staging_directory(self):
        self.apply()
        self.assertEqual(sorted(p.name for p in self.skills.iterdir()), ["chrome-extensions", "modern-web-guidance"])

    def test_apply_scans_both_skills_without_llm(self):
        result, log = self.apply()
        scans = [line for line in log if line.startswith("skillspector scan")]
        self.assertEqual(len(scans), 2, log)
        for line in scans:
            self.assertIn("--no-llm", line)
        self.assertIn("score=20", result.stdout)

    def test_apply_without_skillspector_still_applies(self):
        (self.stub / "skillspector").unlink()
        result, _ = self.apply()
        self.assertIn("skillspector", result.stdout)

    def test_apply_runs_check_repo(self):
        result, log = self.apply()
        self.assertIn(f"check-repo {self.repo}", log)
        self.assertIn("PASS stub", result.stdout)

    def test_apply_reports_check_repo_failure(self):
        result, _ = self.apply(env_extra={"STUB_CHECK_RC": "1"})
        self.assertIn("check-repo.py が失敗した", result.stdout)

    def test_apply_shows_exact_restore_commands(self):
        # 作業ツリーは共有なので、パスを付けた戻し方だけを示す（パスのない git clean は、ほかのファイルを消す）。
        result, _ = self.apply()
        self.assertIn("1.0.1 → 1.0.2", result.stdout)
        self.assertIn("mise install", result.stdout)
        paths = "mise/mise_config.toml claude/skills/modern-web-guidance claude/skills/chrome-extensions"
        self.assertIn(f"git -C {self.repo} restore --source=HEAD --staged --worktree -- {paths}", result.stdout)
        self.assertIn(f"git -C {self.repo} clean -fdx -- claude/skills/modern-web-guidance "
                      "claude/skills/chrome-extensions", result.stdout)

    def test_apply_script_itself_does_not_run_git(self):
        # スクリプト自身は git を動かさない（戻し方は表示するだけ）。本物の check-repo.py は git ls-files を使うが、
        # ここでは偽物なので、確かめているのはスクリプト自身だけ。
        write_executable(self.stub / "git", '#!/bin/sh\necho "git $*" >> "$STUB_LOG"\n')
        _, log = self.apply()
        self.assertFalse(any(line.startswith("git ") for line in log), log)

    # --- 書かずに失敗するとき（--apply）

    def test_runnable_npx_left_after_transform(self):
        renamed = UPSTREAM_SKILL.replace("## Using npx / pnpx", "## Runner notes")
        self.assert_apply_fails_without_writes(package_files(skill=renamed), reason="npx")

    def test_missing_search_command(self):
        changed = UPSTREAM_SKILL.replace("npx -y modern-web-guidance@latest search", "mwg find")
        self.assert_apply_fails_without_writes(package_files(skill=changed))

    def test_skill_version_mismatch(self):
        self.assert_apply_fails_without_writes(package_files(skill_version="2026_11_21-00000000"),
                                               reason="skill-version")

    def test_wrong_skill_name(self):
        self.assert_apply_fails_without_writes(
            package_files(skill=UPSTREAM_SKILL.replace("name: modern-web-guidance", "name: x")))

    def test_chrome_extensions_wrong_name(self):
        self.assert_apply_fails_without_writes(
            package_files(chrome_skill=CHROME_SKILL.replace("name: chrome-extensions", "name: x")))

    def test_unclosed_frontmatter(self):
        self.assert_apply_fails_without_writes(
            package_files(chrome_skill="---\nname: chrome-extensions\ndescription: x\n# no end\n"))

    def test_frontmatter_keys_outside_allowlist(self):
        # hooks（sandbox の外で動く）や allowed-tools（確認なしでツールを使える）が増えたら、書かずに止める。
        for key in ("hooks:\n  PreToolUse: []\n", "allowed-tools: Bash\n", "model: opus\n"):
            for skill in ("modern-web-guidance", "chrome-extensions"):
                with self.subTest(key=key, skill=skill):
                    if skill == "modern-web-guidance":
                        files = package_files(skill=UPSTREAM_SKILL.replace("description: |", key + "description: |"))
                    else:
                        files = package_files(chrome_skill=CHROME_SKILL.replace("description: >", key + "description: >"))
                    self.assert_apply_fails_without_writes(files, reason="frontmatter")

    def test_frontmatter_allowed_keys_pass(self):
        chrome = CHROME_SKILL.replace("description: >", "license: Apache-2.0\nmetadata:\n  a: b\ndescription: >")
        make_tgz(self.tgz, package_files(chrome_skill=chrome))
        self.apply()

    def test_dynamic_context_command(self):
        # 読み込むときにコマンドを実行する書き方（インラインの `!` とバッククォート、フェンスの ```!）を、SKILL.md に入れない。
        for extra in ("\n!`date`\n", "\nNow: !`date`\n", "\n```!\ndate\n```\n", "\n  ``` !\ndate\n  ```\n",
                      "\n~~~!\ndate\n~~~\n"):
            for skill in ("modern-web-guidance", "chrome-extensions"):
                with self.subTest(extra=extra, skill=skill):
                    if skill == "modern-web-guidance":
                        files = package_files(skill=UPSTREAM_SKILL + extra)
                    else:
                        files = package_files(chrome_skill=CHROME_SKILL + extra)
                    self.assert_apply_fails_without_writes(files)

    def test_chrome_extensions_runnable_runners(self):
        for command in ("npx -y modern-web-guidance@latest retrieve x", "npm x modern-web-guidance retrieve x",
                        "npm --yes exec modern-web-guidance", "bun x modern-web-guidance retrieve x",
                        "yarn dlx modern-web-guidance retrieve x", "pnpm dlx modern-web-guidance",
                        "pnpm --package=modern-web-guidance dlx mwg search x",
                        "yarn --silent dlx modern-web-guidance", "npx \\\n  modern-web-guidance search x",
                        "deno run npm:modern-web-guidance search x"):
            with self.subTest(command=command):
                self.assert_apply_fails_without_writes(
                    package_files(chrome_skill=CHROME_SKILL + f"\nRun `{command}`.\n"))

    def test_chrome_extensions_allowed_names_only(self):
        # SKILL.md・skill-version.txt・references の下の .md だけを置く（CLAUDE.md などが指示として読まれないように）。
        for name in ("CLAUDE.md", "claude.local.md", "references/run.sh", "scripts/a.md", "README.md"):
            with self.subTest(name=name):
                self.assert_apply_fails_without_writes(
                    extra=[member("package/skills/chrome-extensions/" + name)], reason="許していない")

    def test_file_and_directory_name_conflict(self):
        extra = [member("package/skills/chrome-extensions/references/x.md"),
                 member("package/skills/chrome-extensions/references/x.md/y.md")]
        result = self.assert_apply_fails_without_writes(extra=extra, reason="衝突")
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_required_file(self):
        files = package_files()
        del files["skills/modern-web-guidance/skill-version.txt"]
        self.assert_apply_fails_without_writes(files)

    def test_path_traversal_member(self):
        evil = member("package/skills/chrome-extensions/../../../escape.md")
        self.assert_apply_fails_without_writes(extra=[evil])
        self.assertFalse((self.repo / "claude" / "escape.md").exists())
        self.assertFalse((self.repo / "escape.md").exists())

    def test_double_slash_member(self):
        # PurePosixPath は // を潰すので、.. の検査だけでは抜けて、書き込み先が絶対パスになる。
        target = self.root / "escape" / "probe.md"
        evil = member(f"package/skills/chrome-extensions/{target}")  # target は / で始まるので // になる
        self.assert_apply_fails_without_writes(extra=[evil])
        self.assertFalse(target.exists())

    def test_non_canonical_members(self):
        for name in ("package/skills/chrome-extensions/./a.md", "package/skills/chrome-extensions/references/"):
            with self.subTest(name=name):
                info, data = member(name)
                self.assert_apply_fails_without_writes(extra=[(info, data)])

    def test_symlink_member(self):
        # リンク先を tarball の中のファイルにする（外を指すリンクは、tarfile が別の理由で読めずに止まるため）。
        info = tarfile.TarInfo("package/skills/chrome-extensions/references/link.md")
        info.type = tarfile.SYMTYPE
        info.linkname = "../SKILL.md"
        self.assert_apply_fails_without_writes(extra=[(info, None)], reason="通常のファイルでない")

    def test_entries_outside_package_or_duplicated(self):
        # インストーラーは先頭の階層を名前によらず取り除くので、package/ の外や重複のエントリーは、検査していない
        # package.json がインストールで使われうる。大文字小文字だけが違う名前も、取り込まないファイルを含めて止める。
        deps = '{"name": "modern-web-guidance", "dependencies": {"x": "1"}}'
        for extra in ([member("other/package.json", deps.encode())],
                      [member("package/package.json", deps.encode())],
                      [member("package/PACKAGE.JSON", deps.encode())],
                      [member("package/gen/A.json"), member("package/gen/a.json")]):
            with self.subTest(extra=[m[0].name for m in extra]):
                self.assert_apply_fails_without_writes(extra=extra)

    def test_non_canonical_entries_not_imported(self):
        # 取り込まないエントリーも、展開するときは正規のパスと同じ場所を指すので、検査をすり抜けさせない
        # （Codex のレビュー: package/./package.json が、検証した package.json を上書きしうる）。
        deps = '{"name": "modern-web-guidance", "dependencies": {"x": "1"}}'.encode()
        for name in ("package/./package.json", "package//package.json", "package/./binding.gyp",
                     "package/gen/../package.json", "package/gen//a.js"):
            with self.subTest(name=name):
                self.assert_apply_fails_without_writes(extra=[member(name, deps)], reason="安全でないパス")

    def test_non_file_entries_not_imported(self):
        # 取り込まないエントリーでも、シンボリックリンクなどはインストールで作られるので止める。
        info = tarfile.TarInfo("package/gen/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "../LICENSE"
        self.assert_apply_fails_without_writes(extra=[(info, None)], reason="通常のファイルでない")

    def test_binding_gyp(self):
        # ルートの binding.gyp があると、インストールで node-gyp rebuild が暗黙に動く。
        self.assert_apply_fails_without_writes(extra=[member("package/binding.gyp")], reason="binding.gyp")

    def test_case_or_unicode_only_name_collision(self):
        # 大文字小文字を区別しない APFS では、後に書いた方が検証した SKILL.md を上書きする。
        for name in ("skills/chrome-extensions/skill.md", "skills/chrome-extensions/SKILL.MD"):
            with self.subTest(name=name):
                self.assert_apply_fails_without_writes(extra=[member("package/" + name)], reason="衝突")
        nfd = "package/skills/chrome-extensions/references/cafe\u0301.md"
        nfc = "package/skills/chrome-extensions/references/caf\u00e9.md"
        self.assert_apply_fails_without_writes(extra=[member(nfc), member(nfd)], reason="衝突")

    def test_dot_files(self):
        # .gitignore や .gitattributes で、取り込んだファイルを差分や PR から隠せないようにする。
        for name in (".gitignore", "references/.gitattributes", ".hidden/a.md"):
            with self.subTest(name=name):
                self.assert_apply_fails_without_writes(
                    extra=[member("package/skills/chrome-extensions/" + name)], reason="ドット")

    def test_oversized_package(self):
        files = package_files()
        files["skills/chrome-extensions/references/huge.md"] = "x" * (2 * 1024 * 1024 + 1)
        self.assert_apply_fails_without_writes(files)

    def test_corrupt_tarball(self):
        self.tgz.write_bytes(b"not a tarball")
        result = self.assert_apply_fails_without_writes()
        self.assertNotIn("Traceback", result.stderr)

    def test_package_json_dependencies_or_install_scripts(self):
        # mise install は sandbox の外で npm install -g を動かすので、依存とインストール時のスクリプトが増えたら止める。
        for extra in ('"dependencies": {"left-pad": "1.0.0"}', '"optionalDependencies": {"x": "1"}',
                      '"scripts": {"postinstall": "node x.js"}', '"scripts": {"preinstall": "x"}',
                      '"scripts": {"install": "x"}', '"scripts": {"prepare": "x"}'):
            with self.subTest(extra=extra):
                package_json = PACKAGE_JSON[:-1] + ", " + extra + "}"
                self.assert_apply_fails_without_writes(package_files(package_json=package_json),
                                                       reason="package.json")

    def test_package_json_bin(self):
        # mise は node_modules/.bin を PATH の先頭に入れるので、bin が増えると git などが置き換わる。
        base = '{"name": "modern-web-guidance", "version": "1.0.2"'
        for package_json in (base + ', "bin": {"modern-web-guidance": "a.mjs", "git": "b.js"}}',
                             base + ', "bin": {"git": "b.js"}}',
                             base + '}',
                             base + ', "bin": "a.mjs", "directories": {"bin": "bin"}}',
                             '{"name": "other", "version": "1.0.2", "bin": "a.mjs"}'):
            with self.subTest(package_json=package_json):
                self.assert_apply_fails_without_writes(package_files(package_json=package_json),
                                                       reason="package.json")

    def test_package_json_string_bin_passes(self):
        make_tgz(self.tgz, package_files(package_json='{"name": "modern-web-guidance", "bin": "a.mjs"}'))
        self.apply()

    def test_package_json_other_scripts_pass(self):
        package_json = PACKAGE_JSON[:-1] + ', "scripts": {"test": "node --test"}}'
        make_tgz(self.tgz, package_files(package_json=package_json))
        self.apply()

    # --- --out: 確かめるために、指定したディレクトリの下にだけ書く

    def test_out_writes_pinned_version_only_to_dir(self):
        out = self.root / "out"
        before = self.snapshot()
        result, log = self.run_script("--out", str(out))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(any(line.startswith("npm view") for line in log))
        self.assertTrue(any(line.startswith("npm pack modern-web-guidance@1.0.1 ") for line in log), log)
        skill = (out / "modern-web-guidance" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("modern-web-guidance@1.0.1", skill)
        self.assertIn("DISABLE_TELEMETRY=1 modern-web-guidance search", skill)
        self.assertEqual((out / "chrome-extensions" / "SKILL.md").read_text(encoding="utf-8"), CHROME_SKILL)

    def test_out_latest_writes_new_version_only_to_dir(self):
        out = self.root / "out"
        before = self.snapshot()
        result, log = self.run_script("--out", str(out), "--latest")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(any(line.startswith("npm pack modern-web-guidance@1.0.2 ") for line in log), log)
        self.assertIn("modern-web-guidance@1.0.2", (out / "modern-web-guidance" / "SKILL.md").read_text(encoding="utf-8"))


class WriteSkillsRollbackTest(unittest.TestCase):
    """入れ替えの途中で失敗したら、元のスキルのディレクトリに戻す。"""

    def setUp(self):
        spec = importlib.util.spec_from_file_location("update_mwg", SCRIPTS / SCRIPT_NAME)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root)
        for name in ("modern-web-guidance", "chrome-extensions"):
            (self.root / name).mkdir()
            (self.root / name / "SKILL.md").write_text(f"old {name}\n", encoding="utf-8")

    def skills(self):
        return {name: {"SKILL.md": f"new {name}\n".encode()} for name in ("modern-web-guidance", "chrome-extensions")}

    def fail_when_placing_chrome(self, error):
        real_replace = os.replace

        def replace(src, dst):
            # 2 つ目のスキルの新しい版を置くところで失敗させる。
            if Path(dst) == self.root / "chrome-extensions" and "new" in Path(src).parts:
                raise error
            return real_replace(src, dst)
        return replace

    def assert_old_restored(self, names=("modern-web-guidance", "chrome-extensions")):
        for name in names:
            self.assertEqual((self.root / name / "SKILL.md").read_text(encoding="utf-8"), f"old {name}\n")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), sorted(names))

    def test_failure_on_second_skill_restores_both(self):
        with mock.patch.object(self.module.os, "replace", side_effect=self.fail_when_placing_chrome(OSError("x"))):
            with self.assertRaises(OSError):
                self.module.write_skills(self.skills(), self.root)
        self.assert_old_restored()

    def test_interrupt_restores_both(self):
        # Ctrl-C（OSError でない）でも元に戻してから、そのまま止める。
        with mock.patch.object(self.module.os, "replace", side_effect=self.fail_when_placing_chrome(KeyboardInterrupt())):
            with self.assertRaises(KeyboardInterrupt):
                self.module.write_skills(self.skills(), self.root)
        self.assert_old_restored()

    def test_rollback_removes_skill_that_did_not_exist(self):
        # 前になかったスキル（ここでは modern-web-guidance）は、戻した後に残さない。
        shutil.rmtree(self.root / "modern-web-guidance")
        with mock.patch.object(self.module.os, "replace", side_effect=self.fail_when_placing_chrome(OSError("x"))):
            with self.assertRaises(OSError):
                self.module.write_skills(self.skills(), self.root)
        self.assert_old_restored(names=("chrome-extensions",))

    def test_failed_rollback_keeps_old_copies(self):
        # 戻す途中でも失敗したら、旧版の写しを一時ディレクトリに残す（消さない）。
        real_replace = os.replace

        def replace(src, dst):
            if Path(dst) == self.root / "chrome-extensions" and "new" in Path(src).parts:
                raise OSError("place")
            if Path(dst) == self.root / "modern-web-guidance" and "old" in Path(src).parts:
                raise OSError("restore")
            return real_replace(src, dst)

        with mock.patch.object(self.module.os, "replace", side_effect=replace):
            with self.assertRaises(OSError):
                self.module.write_skills(self.skills(), self.root)
        kept = list(self.root.glob(".update-mwg-*/old/modern-web-guidance/SKILL.md"))
        self.assertEqual(len(kept), 1, list(self.root.rglob("*")))
        self.assertEqual(kept[0].read_text(encoding="utf-8"), "old modern-web-guidance\n")


if __name__ == "__main__":
    unittest.main()
