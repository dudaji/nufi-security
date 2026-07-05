"""Scan profile loading and resolution (patch110).

Scan profiles allow users to define reusable sets of scan options
(e.g. ``development``, ``ci``, ``strict``) in a YAML config file.

Profile settings serve as defaults that can be overridden by explicit
CLI flags.

Usage::

    from enforcement.scan_profiles import load_profiles, resolve_profile

    profiles = load_profiles()              # loads config/scan_profiles.yaml
    settings = resolve_profile("ci", profiles)
    # settings == {"check_injection": True, "min_severity": "medium", ...}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_PROFILES_PATH = _ROOT / "config" / "scan_profiles.yaml"

# Keys that a profile may set (whitelist for safety).
_PROFILE_KEYS = frozenset({
    "check_injection",
    "min_severity",
    "fail_on_pii",
    "parallel",
    "format",
    "pattern",
    "exclude",
    "cache",
    "stats",
})


@dataclass
class ScanProfile:
    """Resolved scan profile with typed fields."""

    name: str
    check_injection: bool = False
    min_severity: str = "low"
    fail_on_pii: bool = False
    parallel: int = 1
    format: Optional[str] = None
    pattern: Optional[str] = None
    exclude: Optional[str] = None
    cache: bool = False
    stats: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "check_injection": self.check_injection,
            "min_severity": self.min_severity,
            "fail_on_pii": self.fail_on_pii,
            "parallel": self.parallel,
            "format": self.format,
            "pattern": self.pattern,
            "exclude": self.exclude,
            "cache": self.cache,
            "stats": self.stats,
        }


def load_profiles(path: Optional[str | Path] = None) -> Dict[str, Dict[str, Any]]:
    """Load scan profiles from YAML file.

    Args:
        path: Path to scan_profiles.yaml. Defaults to config/scan_profiles.yaml.

    Returns:
        Mapping of profile name to settings dict.

    Raises:
        FileNotFoundError: if the profiles file does not exist.
        ValueError: if the YAML structure is invalid.
    """
    profiles_path = Path(path) if path else _DEFAULT_PROFILES_PATH
    if not profiles_path.is_file():
        raise FileNotFoundError(f"Scan profiles file not found: {profiles_path}")

    text = profiles_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}

    profiles = data.get("scan_profiles")
    if profiles is None:
        raise ValueError(
            f"Missing 'scan_profiles' key in {profiles_path}"
        )
    if not isinstance(profiles, dict):
        raise ValueError(
            f"'scan_profiles' must be a mapping in {profiles_path}"
        )

    # Validate keys
    for name, settings in profiles.items():
        if not isinstance(settings, dict):
            raise ValueError(
                f"Profile '{name}' must be a mapping in {profiles_path}"
            )
        unknown = set(settings.keys()) - _PROFILE_KEYS
        if unknown:
            raise ValueError(
                f"Profile '{name}' has unknown keys: {', '.join(sorted(unknown))}"
            )

    return profiles


def resolve_profile(
    profile_name: str,
    profiles: Optional[Dict[str, Dict[str, Any]]] = None,
    profiles_path: Optional[str | Path] = None,
) -> ScanProfile:
    """Resolve a profile name to a ScanProfile.

    Args:
        profile_name: Name of the profile to resolve.
        profiles: Pre-loaded profiles dict. If None, loads from disk.
        profiles_path: Path to profiles YAML (used only if *profiles* is None).

    Returns:
        ScanProfile with the profile settings applied.

    Raises:
        KeyError: if the named profile does not exist.
    """
    if profiles is None:
        profiles = load_profiles(profiles_path)

    if profile_name not in profiles:
        available = ", ".join(sorted(profiles.keys()))
        raise KeyError(
            f"Unknown scan profile '{profile_name}'. "
            f"Available: {available}"
        )

    settings = profiles[profile_name]
    return ScanProfile(
        name=profile_name,
        check_injection=bool(settings.get("check_injection", False)),
        min_severity=str(settings.get("min_severity", "low")),
        fail_on_pii=bool(settings.get("fail_on_pii", False)),
        parallel=int(settings.get("parallel", 1)),
        format=settings.get("format"),
        pattern=settings.get("pattern"),
        exclude=settings.get("exclude"),
        cache=bool(settings.get("cache", False)),
        stats=bool(settings.get("stats", False)),
    )


def apply_profile_to_args(profile: ScanProfile, args) -> None:
    """Apply profile defaults to an argparse Namespace.

    Only sets values that are not already explicitly provided
    (i.e. still at their default/None/False state).
    Explicit CLI flags always win.
    """
    # check_injection: default is False
    if not getattr(args, "check_injection", False) and profile.check_injection:
        args.check_injection = True

    # fail_on_pii: default is False
    if not getattr(args, "fail_on_pii", False) and profile.fail_on_pii:
        args.fail_on_pii = True

    # parallel: default is 1
    if getattr(args, "parallel", 1) == 1 and profile.parallel > 1:
        args.parallel = profile.parallel

    # format: default is None
    if getattr(args, "format", None) is None and profile.format:
        args.format = profile.format

    # pattern: default is None
    if getattr(args, "pattern", None) is None and profile.pattern:
        args.pattern = profile.pattern

    # exclude: default is None
    if getattr(args, "exclude", None) is None and profile.exclude:
        args.exclude = profile.exclude

    # cache: default is False
    if not getattr(args, "cache", False) and profile.cache:
        args.cache = True

    # stats: default is False
    if not getattr(args, "stats", False) and profile.stats:
        args.stats = True
