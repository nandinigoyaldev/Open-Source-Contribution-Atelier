from django.test import TestCase

from apps.sandbox.ast_verifier import ASTVerifier, parse_git_command


class ASTVerifierTests(TestCase):
    def test_parse_git_command_basic(self):
        node = parse_git_command('git commit -m "feat: add initial commit"')
        self.assertEqual(node.base_cmd, "git")
        self.assertEqual(node.subcommand, "commit")
        self.assertIn("-m", node.flags)
        self.assertEqual(node.flag_values["-m"], "feat: add initial commit")

    def test_parse_git_command_flags_and_args(self):
        node = parse_git_command("git checkout -b feature-login main")
        self.assertEqual(node.base_cmd, "git")
        self.assertEqual(node.subcommand, "checkout")
        self.assertIn("-b", node.flags)
        self.assertEqual(node.flag_values["-b"], "feature-login")
        self.assertIn("main", node.args)

    def test_verify_command_allowed_default(self):
        res = ASTVerifier.verify_command('git commit -m "valid commit"')
        self.assertTrue(res.is_valid)
        self.assertIsNone(res.reason)

    def test_verify_command_denied_flag(self):
        res = ASTVerifier.verify_command("git push --force origin main")
        self.assertFalse(res.is_valid)
        self.assertIn("forbidden", res.reason)

    def test_verify_command_lesson_branching_pattern(self):
        # In git-branching.yml, branch name must match ^feature-.*
        res_valid = ASTVerifier.verify_command(
            "git branch feature-login", lesson_slug="git-branching"
        )
        self.assertTrue(res_valid.is_valid)

        res_invalid = ASTVerifier.verify_command(
            "git branch fix-bug", lesson_slug="git-branching"
        )
        self.assertFalse(res_invalid.is_valid)
        self.assertIn("format pattern", res_invalid.reason)

    def test_verify_command_not_allowed_subcommand(self):
        custom_allowlist = {"allowed_commands": {"status": {}}, "denied_flags": []}
        res = ASTVerifier.verify_command(
            "git rebase main", allowlist_config=custom_allowlist
        )
        self.assertFalse(res.is_valid)
        self.assertIn("not allowed", res.reason)
