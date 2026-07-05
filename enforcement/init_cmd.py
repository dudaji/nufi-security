"""``nufi-egress init`` quick-start command (patch90).

Initializes NuFi in a new project directory — generating config files,
.nufiignore, and optionally a pre-commit hook.

Idempotent: running twice does not overwrite existing configs.
"""
from __future__ import annotations

import os
import stat
import textwrap
from pathlib import Path
from typing import List


# ---------------------------------------------------------------------------
# Template contents (minimal but functional defaults)
# ---------------------------------------------------------------------------

_POLICY_YAML = textwrap.dedent("""\
    # NuFi Egress Policy — default template
    # Entity-level actions: block | redact | pseudonymize | warn | allow
    version: 1

    default_action: warn
    blocking_actions: [block]

    entities:
      # Strong PII — block by default
      KR_RRN:            { action: block, severity: critical }
      CREDIT_CARD:       { action: block, severity: critical }
      SECRET:            { action: block, severity: critical }

      # Weak PII — pseudonymize
      KR_PHONE:          { action: pseudonymize, severity: medium }
      EMAIL:             { action: pseudonymize, severity: low }
      KR_PERSON:         { action: pseudonymize, severity: medium }
""")

_PII_ROUTING_YAML = textwrap.dedent("""\
    # PII Routing — default template
    # Routes requests containing PII to a local model.
    enabled: true
    local_model: nufi-local
    cloud_model: nufi-cloud
    fail_closed: true
    force_local_entities: null
    check_injection: false
""")

_INJECTION_PATTERNS_YAML = textwrap.dedent("""\
    # Custom injection patterns (append to built-in patterns).
    # Each entry: { id, pattern, severity, description }
    # severity: low | medium | high | critical
    patterns: []
""")

_NUFIIGNORE = textwrap.dedent("""\
    # .nufiignore — files/dirs excluded from NuFi scanning
    # Uses gitignore-style glob patterns.

    # Version control
    .git/

    # Dependencies
    node_modules/
    venv/
    .venv/
    __pycache__/

    # Build artifacts
    dist/
    build/
    *.egg-info/

    # Logs and temp
    logs/
    *.log
    *.tmp

    # Binaries and media
    *.png
    *.jpg
    *.gif
    *.pdf
    *.zip
    *.tar.gz
""")

_PRE_COMMIT_HOOK = textwrap.dedent("""\
    #!/usr/bin/env bash
    # NuFi pre-commit hook — scans staged files for PII leaks.
    # Installed by: nufi-egress init --install-hook

    set -e

    # Collect staged files (added/modified)
    FILES=$(git diff --cached --name-only --diff-filter=ACM)
    if [ -z "$FILES" ]; then
        exit 0
    fi

    echo "[nufi] Scanning staged files for PII..."
    nufi-egress scan . --fail-on-pii --pattern "$(echo $FILES | tr ' ' ',')" 2>/dev/null
    STATUS=$?
    if [ $STATUS -ne 0 ]; then
        echo "[nufi] PII detected in staged files. Commit blocked."
        echo "[nufi] Run 'nufi-egress scan .' to see details."
        exit 1
    fi
""")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def run_init(target_dir: str = ".", install_hook: bool = False) -> dict:
    """Initialize NuFi config in *target_dir*.

    Returns a dict with keys:
      created: list of files created
      skipped: list of files that already existed
      errors:  list of error messages (if any)
    """
    root = Path(target_dir).resolve()
    config_dir = root / "config"

    files_to_create = [
        (config_dir / "policy.yaml", _POLICY_YAML),
        (config_dir / "pii_routing.yaml", _PII_ROUTING_YAML),
        (config_dir / "injection_patterns.yaml", _INJECTION_PATTERNS_YAML),
        (root / ".nufiignore", _NUFIIGNORE),
    ]

    created: List[str] = []
    skipped: List[str] = []
    errors: List[str] = []

    # Ensure config directory exists
    config_dir.mkdir(parents=True, exist_ok=True)

    for path, content in files_to_create:
        if path.exists():
            skipped.append(str(path.relative_to(root)))
        else:
            try:
                path.write_text(content, encoding="utf-8")
                created.append(str(path.relative_to(root)))
            except OSError as e:
                errors.append(f"{path.relative_to(root)}: {e}")

    # Pre-commit hook
    if install_hook:
        hook_path = _find_git_hook_path(root)
        if hook_path is None:
            errors.append("pre-commit hook: not a git repository (no .git found)")
        elif hook_path.exists():
            skipped.append(str(hook_path.relative_to(root)))
        else:
            try:
                hook_path.parent.mkdir(parents=True, exist_ok=True)
                hook_path.write_text(_PRE_COMMIT_HOOK, encoding="utf-8")
                hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                created.append(str(hook_path.relative_to(root)))
            except OSError as e:
                errors.append(f"pre-commit hook: {e}")

    return {"created": created, "skipped": skipped, "errors": errors}


def _find_git_hook_path(root: Path) -> "Path | None":
    """Locate .git/hooks/pre-commit, handling worktrees."""
    git_dir = root / ".git"
    if git_dir.is_file():
        # git worktree — .git is a file pointing to actual git dir
        text = git_dir.read_text().strip()
        if text.startswith("gitdir:"):
            git_dir = Path(text.split(":", 1)[1].strip())
            if not git_dir.is_absolute():
                git_dir = (root / git_dir).resolve()
    if not git_dir.is_dir():
        return None
    return git_dir / "hooks" / "pre-commit"


def render_result(result: dict) -> str:
    """Human-readable summary of init result."""
    lines: List[str] = []
    if result["created"]:
        lines.append("Created:")
        for f in result["created"]:
            lines.append(f"  + {f}")
    if result["skipped"]:
        lines.append("Skipped (already exist):")
        for f in result["skipped"]:
            lines.append(f"  ~ {f}")
    if result["errors"]:
        lines.append("Errors:")
        for e in result["errors"]:
            lines.append(f"  ! {e}")
    if not lines:
        lines.append("Nothing to do.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point (called from enforcement.cli)
# ---------------------------------------------------------------------------

def cmd_quickstart_init(args) -> int:
    """Handle `nufi-egress init` quick-start subcommand."""
    target = getattr(args, "dir", ".") or "."
    install_hook = getattr(args, "install_hook", False)

    result = run_init(target_dir=target, install_hook=install_hook)
    print(render_result(result))

    return 1 if result["errors"] else 0
