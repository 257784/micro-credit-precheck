"""Check the Codex write guard without starting a Codex session."""

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("codex_hook_policy", ROOT / ".codex/hooks/policy.py")
policy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = policy
SPEC.loader.exec_module(policy)


def edit_event(path: str, content: str) -> dict:
    return {
        "tool_name": "apply_patch",
        "cwd": str(ROOT),
        "tool_input": {"command": f"*** Begin Patch\n*** Add File: {path}\n+{content}\n*** End Patch"},
    }


class CodexHookTests(unittest.TestCase):
    def test_blocks_sensitive_assignment_without_echoing_value(self):
        event = edit_event("backend/app/example.py", "+password=example-value")
        result = policy.pre_result(event)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertNotIn("example-value", str(result))

    def test_blocks_ignored_target(self):
        result = policy.pre_result(edit_event("frontend/dist/generated.js", "+console.log(1)"))
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_blocks_shell_write_to_ignored_target(self):
        event = {
            "tool_name": "Bash",
            "cwd": str(ROOT),
            "tool_input": {"command": "Set-Content -LiteralPath backend/.env -Value demo"},
        }
        result = policy.pre_result(event)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_allows_normal_edit_and_read_only_command(self):
        self.assertIsNone(policy.pre_result(edit_event("backend/app/example.py", "+answer = 1")))
        event = {"tool_name": "Bash", "tool_input": {"command": "git status --short"}}
        self.assertIsNone(policy.pre_result(event))
        self.assertIsNone(policy.post_result(event))

    def test_failed_post_check_returns_agent_feedback(self):
        event = edit_event("backend/app/example.py", "+answer = 1")
        with patch.object(policy.subprocess, "run") as run:
            run.return_value.returncode = 1
            run.return_value.stdout = "problem"
            run.return_value.stderr = ""
            result = policy.post_result(event)
        self.assertEqual(result["decision"], "block")
        self.assertIn("请先修复", result["reason"])

    def test_configured_windows_command_invokes_pre_hook(self):
        if sys.platform != "win32":
            self.skipTest("The configured Windows command is Windows-specific")
        config = json.loads((ROOT / ".codex/hooks.json").read_text(encoding="utf-8"))
        command = config["hooks"]["PreToolUse"][0]["hooks"][0]["commandWindows"]
        event = edit_event("frontend/dist/generated.js", "+console.log(1)")
        completed = subprocess.run(
            command,
            cwd=ROOT,
            input=json.dumps(event),
            text=True,
            capture_output=True,
            shell=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
