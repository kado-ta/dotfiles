import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parents[2] / "bin"
loader = importlib.machinery.SourceFileLoader("cc_crit", str(BIN / "cc-crit"))
spec = importlib.util.spec_from_loader(loader.name, loader)
wrapper = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = wrapper
loader.exec_module(wrapper)

REQUEST = ".cc-crit-request.json"
SESSION = "d58eb1c63694"


def reply_request(**changes):
    data = {"session": SESSION, "replies": [{"reply_to": "c_73f150", "body": "3.3 を更新しました。\n\t詳細は下記"}]}
    data.update(changes)
    return data


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cc-crit-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        # find_toplevel は .git の有無だけを見て、git は実行しない。
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "plan.md").write_text("# plan\n", encoding="utf-8")
        (self.root / "outside.md").write_text("outside\n", encoding="utf-8")
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.repo)

    def write_request(self, data=None, raw=None):
        Path(REQUEST).write_bytes(raw if raw is not None else json.dumps(data).encode("utf-8"))

    def assertDenied(self, fn, *args):
        with self.assertRaises(wrapper.Denied):
            fn(*args)


class ClaimTests(Base):
    def test_claims_and_removes_the_request(self):
        self.write_request({"files": ["docs/plan.md"]})
        raw = wrapper.claim_request()
        self.assertEqual(json.loads(raw), {"files": ["docs/plan.md"]})
        self.assertFalse(os.path.lexists(REQUEST))

    def test_missing_request_is_denied(self):
        self.assertDenied(wrapper.claim_request)

    def test_invalid_content_is_claimed_and_removed_before_parsing(self):
        self.write_request(raw=b"not json")
        raw = wrapper.claim_request()
        self.assertFalse(os.path.lexists(REQUEST))
        self.assertDenied(wrapper.parse_request, raw, "review")

    def test_symlink_is_denied_and_removed(self):
        target = self.root / "target.json"
        target.write_text('{"files": []}', encoding="utf-8")
        os.symlink(target, REQUEST)
        self.assertDenied(wrapper.claim_request)
        self.assertFalse(os.path.lexists(REQUEST))
        self.assertTrue(target.exists())

    def test_hard_link_is_denied_and_removed(self):
        other = self.root / "other.json"
        other.write_text('{"files": []}', encoding="utf-8")
        os.link(other, REQUEST)
        self.assertDenied(wrapper.claim_request)
        self.assertFalse(os.path.lexists(REQUEST))
        self.assertTrue(other.exists())

    def test_fifo_is_denied_without_blocking(self):
        os.mkfifo(REQUEST)
        self.assertDenied(wrapper.claim_request)
        self.assertFalse(os.path.lexists(REQUEST))

    def test_oversized_request_is_denied_and_removed(self):
        self.write_request(raw=b"{" + b" " * wrapper.MAX_REQUEST + b"}")
        self.assertDenied(wrapper.claim_request)
        self.assertFalse(os.path.lexists(REQUEST))


class ParseReviewTests(Base):
    def parse(self, data):
        return wrapper.parse_request(json.dumps(data).encode("utf-8"), "review")

    def test_files_are_returned(self):
        self.assertEqual(self.parse({"files": ["docs/plan.md"]}), {"files": ["docs/plan.md"]})

    def test_omitted_files_mean_the_branch_diff(self):
        self.assertEqual(self.parse({}), {"files": []})

    def test_too_many_files_are_denied(self):
        self.assertDenied(self.parse, {"files": [f"f{i}.md" for i in range(wrapper.MAX_FILES + 1)]})

    def test_non_string_file_is_denied(self):
        self.assertDenied(self.parse, {"files": [1]})

    def test_empty_file_name_is_denied(self):
        self.assertDenied(self.parse, {"files": [""]})

    def test_files_must_be_a_list(self):
        self.assertDenied(self.parse, {"files": "docs/plan.md"})

    def test_unknown_key_is_denied(self):
        self.assertDenied(self.parse, {"files": [], "host": "0.0.0.0"})

    def test_reply_fields_are_denied_for_review(self):
        self.assertDenied(self.parse, reply_request())


class ParseReplyTests(Base):
    def parse(self, data):
        return wrapper.parse_request(json.dumps(data).encode("utf-8"), "reply")

    def test_valid_reply_is_returned(self):
        self.assertEqual(self.parse(reply_request()), reply_request())

    def test_missing_session_is_denied(self):
        data = reply_request()
        del data["session"]
        self.assertDenied(self.parse, data)

    def test_malformed_session_is_denied(self):
        for session in ("D58EB1C63694", "d58eb1c6369", "d58eb1c63694x", "../../etc", 123):
            with self.subTest(session=session):
                self.assertDenied(self.parse, reply_request(session=session))

    def test_missing_or_empty_replies_are_denied(self):
        data = reply_request()
        del data["replies"]
        self.assertDenied(self.parse, data)
        self.assertDenied(self.parse, reply_request(replies=[]))

    def test_too_many_replies_are_denied(self):
        replies = [{"reply_to": "c_73f150", "body": "ok"}] * (wrapper.MAX_REPLIES + 1)
        self.assertDenied(self.parse, reply_request(replies=replies))

    def test_malformed_reply_to_is_denied(self):
        for reply_to in ("rp_bc1969", "c_XYZXYZ", "c_123", "c_73f150 --resolve", 7):
            with self.subTest(reply_to=reply_to):
                self.assertDenied(self.parse, reply_request(replies=[{"reply_to": reply_to, "body": "ok"}]))

    def test_extra_reply_fields_are_denied(self):
        # 解決済みへの変更、author の指定、新しいコメントの追加はできない。
        for extra in ({"resolve": True}, {"author": "kado-ta"}, {"file": "docs/plan.md", "line": 1}):
            with self.subTest(extra=extra):
                reply = {"reply_to": "c_73f150", "body": "ok", **extra}
                self.assertDenied(self.parse, reply_request(replies=[reply]))

    def test_body_with_control_characters_is_denied(self):
        for body in ("\x1b[31mred", "carriage\rreturn", "nul\0byte"):
            with self.subTest(body=body):
                self.assertDenied(self.parse, reply_request(replies=[{"reply_to": "c_73f150", "body": body}]))

    def test_empty_or_oversized_body_is_denied(self):
        for body in ("", "x" * (wrapper.MAX_BODY + 1), None):
            with self.subTest(length=None if body is None else len(body)):
                self.assertDenied(self.parse, reply_request(replies=[{"reply_to": "c_73f150", "body": body}]))

    def test_review_fields_are_denied_for_reply(self):
        self.assertDenied(self.parse, {"files": []})


class ParseEncodingTests(Base):
    def test_duplicate_keys_are_denied(self):
        self.assertDenied(wrapper.parse_request, b'{"files": [], "files": ["docs/plan.md"]}', "review")

    def test_byte_order_mark_is_denied(self):
        self.assertDenied(wrapper.parse_request, b'\xef\xbb\xbf{"files": []}', "review")

    def test_invalid_utf8_is_denied(self):
        self.assertDenied(wrapper.parse_request, b'{"files": ["\xff.md"]}', "review")

    def test_non_object_is_denied(self):
        self.assertDenied(wrapper.parse_request, b'["docs/plan.md"]', "review")

    def test_non_finite_number_is_denied(self):
        self.assertDenied(wrapper.parse_request, b'{"files": NaN}', "review")


class ToplevelTests(Base):
    def test_repository_root(self):
        self.assertEqual(wrapper.find_toplevel(self.repo), self.repo)

    def test_from_a_subdirectory(self):
        self.assertEqual(wrapper.find_toplevel(self.repo / "docs"), self.repo)

    def test_worktree_with_a_git_file(self):
        worktree = self.root / "worktree"
        (worktree / "sub").mkdir(parents=True)
        (worktree / ".git").write_text("gitdir: /elsewhere/.git/worktrees/x\n", encoding="utf-8")
        self.assertEqual(wrapper.find_toplevel(worktree / "sub"), worktree)

    def test_outside_a_repository_is_denied(self):
        self.assertDenied(wrapper.find_toplevel, self.root)


class ResolveFilesTests(Base):
    def resolve(self, files, cwd=None):
        return wrapper.resolve_files(files, cwd or self.repo, self.repo)

    def test_relative_path_becomes_absolute(self):
        self.assertEqual(self.resolve(["docs/plan.md"]), [str(self.repo / "docs" / "plan.md")])

    def test_relative_to_a_subdirectory(self):
        self.assertEqual(self.resolve(["plan.md"], cwd=self.repo / "docs"), [str(self.repo / "docs" / "plan.md")])

    def test_symlink_inside_the_repository_resolves_to_the_target(self):
        os.symlink(self.repo / "docs" / "plan.md", self.repo / "link.md")
        self.assertEqual(self.resolve(["link.md"]), [str(self.repo / "docs" / "plan.md")])

    def test_option_like_name_is_denied(self):
        for name in ("-o", "--pr", "-"):
            with self.subTest(name=name):
                self.assertDenied(self.resolve, [name])

    def test_path_outside_the_repository_is_denied(self):
        for name in ("../outside.md", str(self.root / "outside.md")):
            with self.subTest(name=name):
                self.assertDenied(self.resolve, [name])

    def test_symlink_pointing_outside_is_denied(self):
        os.symlink(self.root / "outside.md", self.repo / "escape.md")
        self.assertDenied(self.resolve, ["escape.md"])

    def test_directory_is_denied(self):
        self.assertDenied(self.resolve, ["docs"])

    def test_missing_file_is_denied(self):
        self.assertDenied(self.resolve, ["missing.md"])

    def test_file_inside_dot_git_is_denied(self):
        (self.repo / ".git" / "config").write_text("[core]\n", encoding="utf-8")
        self.assertDenied(self.resolve, [".git/config"])

    def test_fifo_is_denied(self):
        os.mkfifo(self.repo / "pipe")
        self.assertDenied(self.resolve, ["pipe"])


if __name__ == "__main__":
    unittest.main()
