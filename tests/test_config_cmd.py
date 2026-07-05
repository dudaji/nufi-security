"""tests/test_config_cmd.py -- nufi-egress config validate/show 테스트 (patch105, patch187).

시나리오:
1. 유효한 설정 → 에러 없음
2. 잘못된 regex 패턴 → 에러 보고
3. config show → 유효 설정 반환(defaults 적용)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from enforcement.config_cmd import validate_config, show_config, ConfigValidationResult


class TestValidConfigNoErrors:
    """유효한 설정 파일 → 에러 없음."""

    def test_valid_config(self, tmp_path: Path):
        # Create valid config files
        (tmp_path / "policy.yaml").write_text(
            "version: 1\n"
            "default_action: warn\n"
            "blocking_actions: [block]\n"
            "entities:\n"
            "  KR_RRN:\n"
            "    action: block\n"
            "    severity: critical\n",
            encoding="utf-8",
        )
        (tmp_path / "pii_routing.yaml").write_text(
            "enabled: true\n"
            "local_model: nufi-local\n"
            "cloud_model: nufi-cloud\n",
            encoding="utf-8",
        )
        (tmp_path / "injection_patterns.yaml").write_text(
            "custom_patterns:\n"
            "  - pattern: 'hello.*world'\n"
            "    severity: low\n"
            "    description: test\n",
            encoding="utf-8",
        )

        result = validate_config(config_dir=tmp_path)
        assert result.files_checked == 3
        assert not result.has_errors


class TestInvalidRegexReported:
    """injection_patterns.yaml 에 잘못된 regex → 에러 보고."""

    def test_invalid_regex(self, tmp_path: Path):
        # Create config with invalid regex
        (tmp_path / "policy.yaml").write_text(
            "version: 1\ndefault_action: warn\nentities: {}\n",
            encoding="utf-8",
        )
        (tmp_path / "pii_routing.yaml").write_text(
            "enabled: true\nlocal_model: x\ncloud_model: y\n",
            encoding="utf-8",
        )
        (tmp_path / "injection_patterns.yaml").write_text(
            "custom_patterns:\n"
            "  - pattern: '[invalid(regex'\n"
            "    severity: high\n"
            "    description: bad pattern\n",
            encoding="utf-8",
        )

        result = validate_config(config_dir=tmp_path)
        assert result.has_errors
        # Should have at least one error about invalid regex
        regex_errors = [
            i for i in result.issues
            if "invalid regex" in i.message.lower() or "regex" in i.message.lower()
        ]
        assert len(regex_errors) >= 1


class TestConfigShow:
    """config show — 유효 설정 반환 (patch187)."""

    def test_show_with_existing_files(self, tmp_path: Path):
        """Existing config files are loaded and defaults are merged."""
        (tmp_path / "policy.yaml").write_text(
            "version: 2\ndefault_action: block\nentities:\n  KR_RRN:\n    action: block\n",
            encoding="utf-8",
        )
        (tmp_path / "pii_routing.yaml").write_text(
            "enabled: true\nlocal_model: my-local\ncloud_model: my-cloud\n",
            encoding="utf-8",
        )
        # No injection_patterns.yaml or scan_profiles.yaml → defaults used

        effective = show_config(config_dir=tmp_path)

        # policy loaded from file
        assert effective["policy"]["version"] == 2
        assert effective["policy"]["default_action"] == "block"
        assert "KR_RRN" in effective["policy"]["entities"]

        # pii_routing loaded from file
        assert effective["pii_routing"]["enabled"] is True
        assert effective["pii_routing"]["local_model"] == "my-local"

        # injection_patterns falls back to defaults (file missing)
        assert effective["injection_patterns"]["custom_patterns"] == []

        # scan_profiles falls back to defaults (file missing)
        assert effective["scan_profiles"]["profiles"] == {}

        # Meta
        assert effective["_meta"]["config_dir"] == str(tmp_path)
        assert len(effective["_meta"]["files_loaded"]) == 2  # only 2 files exist
