"""Codex write guard and verification hooks for this repository."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_SUFFIXES = {".py", ".js", ".jsx", ".mjs", ".css", ".html", ".json", ".toml"}
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b(?:password|passwd|api[_-]?key|secret|access[_-]?token)\s*[:=]"
)
PATCH_PATH = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", re.M)
SHELL_WRITE = re.compile(
    r"(?i)\b(?:Set-Content|Add-Content|Out-File|New-Item|Copy-Item|Move-Item|"
    r"Tee-Object|apply_patch|write_text|write_bytes|writeFile|appendFile)\b|(?<![<>])>(?![>&])"
)
SHELL_DESTINATION = re.compile(
    r"(?i)(?:-LiteralPath|-FilePath|-Path|(?<![<>])>(?![>&]))\s+"
    r"(?:'([^']+)'|\"([^\"]+)\"|([^\s;&|]+))"
)


def command_text(event: dict) -> str:
    tool_input = event.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return ""
    return str(tool_input.get("command") or tool_input.get("cmd") or "")


def is_write(event: dict) -> bool:
    command = command_text(event)
    if event.get("tool_name") == "apply_patch":
        return bool(PATCH_PATH.search(command))
    return event.get("tool_name") == "Bash" and bool(SHELL_WRITE.search(command))


def changed_paths(event: dict) -> list[str]:
    command = command_text(event)
    if event.get("tool_name") == "apply_patch":
        return PATCH_PATH.findall(command)
    return [next(value for value in match.groups() if value) for match in SHELL_DESTINATION.finditer(command)]


def added_text(event: dict) -> str:
    command = command_text(event)
    if event.get("tool_name") == "apply_patch":
        return "\n".join(
            line[1:] for line in command.splitlines() if line.startswith("+") and not line.startswith("+++")
        )
    return command


def ignored_path(raw_path: str, cwd: Path) -> bool:
    candidate = (cwd / raw_path).resolve()
    try:
        relative = candidate.relative_to(REPO_ROOT)
    except ValueError:
        return False
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "--", str(relative)],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


def pre_result(event: dict) -> dict | None:
    if not is_write(event):
        return None
    if SENSITIVE_ASSIGNMENT.search(added_text(event)):
        reason = "写入内容包含疑似密码或令牌赋值；请改用环境变量，不要把值写进文件或命令。"
    else:
        cwd = Path(event.get("cwd") or REPO_ROOT).resolve()
        ignored = [path for path in changed_paths(event) if ignored_path(path, cwd)]
        reason = "目标文件受 .gitignore 忽略，请改用受版本管理的示例文件。" if ignored else ""
    if not reason:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def post_result(event: dict) -> dict | None:
    if not is_write(event):
        return None
    paths = changed_paths(event)
    if paths and not any(Path(path).suffix.lower() in CODE_SUFFIXES for path in paths):
        return None

    try:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/check_project.py")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if result.returncode == 0:
            return None
        detail = (result.stdout + result.stderr).strip()[-1800:]
    except (OSError, subprocess.TimeoutExpired) as error:
        detail = str(error)
    return {"decision": "block", "reason": f"项目检查失败。请先修复并重新运行检查，再继续开发。\n{detail}"}


def main() -> None:
    event = json.load(sys.stdin)
    result = pre_result(event) if sys.argv[1] == "pre" else post_result(event)
    if result:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
