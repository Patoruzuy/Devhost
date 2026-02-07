"""Diagnostic bundle export for Devhost."""

from __future__ import annotations

import json
import os
import platform
import re
import sys
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .config import Config
from .logs import get_log_path


def _format_bytes(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.0f}{unit}"
        num /= 1024
    return f"{num:.0f}TB"


DEFAULT_BUNDLE_SIZE_LIMIT_BYTES = 200 * 1024 * 1024

DEFAULT_REDACTION_PATTERNS: list[tuple[re.Pattern, str | Callable[[re.Match], str]]] = [
    (
        re.compile(r"(?im)^(authorization|proxy-authorization|x-authorization)\s*:\s*bearer\s+[^\s]+"),
        lambda m: f"{m.group(1)}: Bearer [REDACTED]",
    ),
    (
        re.compile(r"(?im)^(authorization|proxy-authorization|x-authorization)\s*:\s*basic\s+[^\s]+"),
        lambda m: f"{m.group(1)}: Basic [REDACTED]",
    ),
    (
        re.compile(r"(?im)^(authorization|proxy-authorization|x-authorization)\s*:\s*token\s+[^\s]+"),
        lambda m: f"{m.group(1)}: Token [REDACTED]",
    ),
    (
        re.compile(
            r"(?im)^(x-api-key|x-auth-token|x-access-token|x-amz-security-token|x-goog-api-key|x-azure-sas|x-azure-sas-token)\s*:\s*.*$"
        ),
        lambda m: f"{m.group(1)}: [REDACTED]",
    ),
    (
        re.compile(
            r'(?i)(?P<prefix>"?(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|refresh[_-]?token|client[_-]?secret|x-api-key)"?\s*[:=]\s*)(?P<quote>["\']?)(?P<value>[^"\'\s]+)(?P=quote)'
        ),
        lambda m: f"{m.group('prefix')}{m.group('quote')}[REDACTED]{m.group('quote')}",
    ),
    (
        re.compile(
            r"(?im)^(?P<key>[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASS|API_KEY|ACCESS_KEY|REFRESH_TOKEN|CLIENT_SECRET|PRIVATE_KEY)[A-Z0-9_]*)\s*=\s*(?P<quote>['\"]?)(?P<value>.*?)(?P=quote)\s*$"
        ),
        lambda m: f"{m.group('key')}={m.group('quote')}[REDACTED]{m.group('quote')}",
    ),
    (
        re.compile(r"(?im)^(cookie|set-cookie)\s*:\s*.*$"),
        lambda m: f"{m.group(1)}: [REDACTED]",
    ),
    (
        re.compile(r"(?i)\b(https?://)([^/\s:@]+):([^@\s/]+)@"),
        lambda m: f"{m.group(1)}[REDACTED]@",
    ),
    (re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b"), "[REDACTED_JWT]"),
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"),
        "[REDACTED_PRIVATE_KEY]",
    ),
]


def _redact_text(
    text: str,
    include_defaults: bool = True,
    extra_patterns: list[tuple[re.Pattern, str | Callable[[re.Match], str]]] | None = None,
) -> tuple[str, int]:
    redacted = text
    total = 0
    patterns: list[tuple[re.Pattern, str | Callable[[re.Match], str]]] = []
    if include_defaults:
        patterns.extend(DEFAULT_REDACTION_PATTERNS)
    if extra_patterns:
        patterns.extend(extra_patterns)
    for pattern, replacement in patterns:
        redacted, count = pattern.subn(replacement, redacted)
        total += count
    return redacted, total


@dataclass
class RedactionContext:
    patterns: list[tuple[re.Pattern, str | Callable[[re.Match], str]]]
    include_defaults: bool
    source: Path | None
    errors: list[str]


def _get_redaction_config_path(devhost_dir: Path, override: Path | None) -> Path | None:
    if override:
        return override
    env_path = os.getenv("DEVHOST_DIAGNOSTICS_REDACTION_FILE")
    if env_path:
        return Path(env_path)
    default_path = devhost_dir / "diagnostics-redaction.json"
    return default_path if default_path.exists() else None


def _compile_custom_patterns(
    data: dict,
) -> tuple[list[tuple[re.Pattern, str | Callable[[re.Match], str]]], bool, list[str]]:
    errors: list[str] = []
    patterns: list[tuple[re.Pattern, str | Callable[[re.Match], str]]] = []
    include_defaults = True
    redaction = data.get("redaction", data)
    if isinstance(redaction, dict):
        include_defaults = redaction.get("include_defaults", True)
        raw_patterns = redaction.get("patterns", [])
    else:
        raw_patterns = []

    for item in raw_patterns:
        if isinstance(item, str):
            pattern_text = item
            replacement = "[REDACTED_CUSTOM]"
            flags = 0
        elif isinstance(item, dict):
            pattern_text = item.get("pattern")
            if not pattern_text:
                errors.append("Redaction pattern missing 'pattern' field.")
                continue
            replacement = item.get("replacement", "[REDACTED_CUSTOM]")
            flags = 0
            flag_text = item.get("flags", "")
            if isinstance(flag_text, str):
                if "i" in flag_text:
                    flags |= re.IGNORECASE
                if "m" in flag_text:
                    flags |= re.MULTILINE
                if "s" in flag_text:
                    flags |= re.DOTALL
        else:
            errors.append("Invalid redaction pattern entry.")
            continue
        try:
            compiled = re.compile(pattern_text, flags)
            patterns.append((compiled, replacement))
        except re.error as exc:
            errors.append(f"Invalid regex '{pattern_text}': {exc}")

    return patterns, include_defaults, errors


def _load_redaction_context(devhost_dir: Path, override: Path | None) -> RedactionContext:
    source = _get_redaction_config_path(devhost_dir, override)
    if not source:
        return RedactionContext(patterns=[], include_defaults=True, source=None, errors=[])

    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        return RedactionContext(
            patterns=[],
            include_defaults=True,
            source=source,
            errors=[f"Failed to read redaction config: {exc}"],
        )

    patterns, include_defaults, errors = _compile_custom_patterns(data if isinstance(data, dict) else {})
    return RedactionContext(patterns=patterns, include_defaults=include_defaults, source=source, errors=errors)


def parse_size_limit(value: str | int | None) -> int | None:
    """Parse a size limit string like '50MB' into bytes."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip().lower()
    if text in {"0", "none", "no", "off", "unlimited", "disable", "disabled"}:
        return 0
    match = re.fullmatch(r"(\d+)\s*(b|kb|mb|gb|tb)?", text)
    if not match:
        raise ValueError(f"Invalid size limit: {value}")
    number = int(match.group(1))
    unit = match.group(2) or "b"
    multipliers = {
        "b": 1,
        "kb": 1024,
        "mb": 1024**2,
        "gb": 1024**3,
        "tb": 1024**4,
    }
    return number * multipliers[unit]


def _normalize_size_limit(size_limit_bytes: int | None) -> int | None:
    if size_limit_bytes is None:
        return DEFAULT_BUNDLE_SIZE_LIMIT_BYTES
    if size_limit_bytes <= 0:
        return None
    return size_limit_bytes


def _add_file(
    zipf: zipfile.ZipFile,
    source: Path,
    arcname: str,
    included: list[str],
    missing: list[str],
    redacted: list[str],
    redaction_skipped: list[str],
    redact: bool = False,
    redaction: RedactionContext | None = None,
) -> None:
    if source.exists() and source.is_file():
        if redact and redaction:
            try:
                content = source.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                zipf.write(source, arcname)
                included.append(arcname)
                redaction_skipped.append(arcname)
                return
            redacted_text, count = _redact_text(
                content,
                include_defaults=redaction.include_defaults,
                extra_patterns=redaction.patterns,
            )
            if count > 0:
                redacted.append(arcname)
            zipf.writestr(arcname, redacted_text)
            included.append(arcname)
        else:
            zipf.write(source, arcname)
            included.append(arcname)
    else:
        missing.append(arcname)


def _add_dir(
    zipf: zipfile.ZipFile,
    source_dir: Path,
    arc_prefix: str,
    included: list[str],
    missing: list[str],
    redacted: list[str],
    redaction_skipped: list[str],
    redact: bool = False,
    redaction: RedactionContext | None = None,
) -> None:
    if not source_dir.exists():
        return
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(source_dir)
        arcname = str(Path(arc_prefix) / rel)
        _add_file(
            zipf,
            path,
            arcname,
            included,
            missing,
            redacted,
            redaction_skipped,
            redact=redact,
            redaction=redaction,
        )


def _collect_files(
    state: Any,
    config_file: Path | None,
    domain_file: Path | None,
    log_path: Path | None,
    include_state: bool,
    include_config: bool,
    include_proxy: bool,
    include_logs: bool,
    redact: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    devhost_dir = Path(getattr(state, "devhost_dir", Path.home() / ".devhost"))
    state_file = Path(getattr(state, "state_file", devhost_dir / "state.yml"))
    proxy_dir = devhost_dir / "proxy"
    logs_dir = devhost_dir / "logs"
    included: list[dict[str, Any]] = []
    missing: list[str] = []

    def _add_candidate(path: Path, arcname: str, should_redact: bool) -> None:
        if path.exists() and path.is_file():
            included.append(
                {
                    "path": arcname,
                    "size": path.stat().st_size,
                    "redact": should_redact,
                }
            )
        else:
            missing.append(arcname)

    if include_state:
        _add_candidate(state_file, "state/state.yml", redact)
    if include_config:
        if config_file:
            _add_candidate(config_file, "config/devhost.json", redact)
        if domain_file:
            _add_candidate(domain_file, "config/domain", redact)
    if include_logs:
        if log_path:
            _add_candidate(log_path, "logs/router.log", redact)
        if logs_dir.exists():
            for path in logs_dir.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(logs_dir)
                arcname = str(Path("logs") / rel)
                _add_candidate(path, arcname, redact)
    if include_proxy and proxy_dir.exists():
        for path in proxy_dir.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(proxy_dir)
            arcname = str(Path("proxy") / rel)
            _add_candidate(path, arcname, False)

    return included, missing


def preview_diagnostic_bundle(
    state: Any,
    config_file: Path | None = None,
    domain_file: Path | None = None,
    log_path: Path | None = None,
    include_state: bool = True,
    include_config: bool = True,
    include_proxy: bool = True,
    include_logs: bool = True,
    redact: bool = True,
    redaction_file: Path | None = None,
    size_limit_bytes: int | None = None,
) -> dict[str, Any]:
    size_limit = _normalize_size_limit(size_limit_bytes)
    if include_config and (config_file is None or domain_file is None):
        config = Config()
        config_file = config_file or config.config_file
        domain_file = domain_file or config.domain_file
    log_path = log_path or get_log_path()

    included, missing = _collect_files(
        state,
        config_file,
        domain_file,
        log_path,
        include_state,
        include_config,
        include_proxy,
        include_logs,
        redact,
    )
    devhost_dir = Path(getattr(state, "devhost_dir", Path.home() / ".devhost"))
    redaction = _load_redaction_context(devhost_dir, redaction_file) if redact else None
    total_size = sum(item["size"] for item in included)
    redacted_count = sum(1 for item in included if item["redact"])
    included_sorted = sorted(included, key=lambda x: x["size"], reverse=True)
    over_limit = size_limit is not None and total_size > size_limit
    return {
        "included": included,
        "included_sorted": included_sorted,
        "missing": missing,
        "total_size": total_size,
        "total_size_human": _format_bytes(total_size),
        "redacted_count": redacted_count,
        "redact": redact,
        "size_limit_bytes": size_limit,
        "size_limit_human": _format_bytes(size_limit) if size_limit is not None else None,
        "over_limit": over_limit,
        "redaction_config": {
            "source": str(redaction.source) if redaction and redaction.source else None,
            "include_defaults": redaction.include_defaults if redaction else True,
            "custom_patterns": len(redaction.patterns) if redaction else 0,
            "errors": redaction.errors if redaction else [],
        },
    }


def export_diagnostic_bundle(
    state: Any,
    config_file: Path | None = None,
    domain_file: Path | None = None,
    log_path: Path | None = None,
    output_path: Path | None = None,
    include_state: bool = True,
    include_config: bool = True,
    include_proxy: bool = True,
    include_logs: bool = True,
    redact: bool = True,
    redaction_file: Path | None = None,
    size_limit_bytes: int | None = None,
) -> tuple[bool, Path | None, dict[str, Any]]:
    """
    Export a diagnostic bundle containing devhost-owned artifacts.

    Returns: (success, bundle_path, manifest)
    """
    manifest: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": __version__,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "included": [],
        "missing": [],
        "redacted": [],
        "redaction_skipped": [],
    }

    devhost_dir = Path(getattr(state, "devhost_dir", Path.home() / ".devhost"))
    size_limit = _normalize_size_limit(size_limit_bytes)
    if include_config and (config_file is None or domain_file is None):
        config = Config()
        config_file = config_file or config.config_file
        domain_file = domain_file or config.domain_file
    log_path = log_path or get_log_path()
    state_file = Path(getattr(state, "state_file", devhost_dir / "state.yml"))
    proxy_dir = devhost_dir / "proxy"
    logs_dir = devhost_dir / "logs"
    bundle_path: Path | None = None
    redaction = None
    if redact:
        redaction = _load_redaction_context(devhost_dir, redaction_file)

    manifest["options"] = {
        "include_state": include_state,
        "include_config": include_config,
        "include_proxy": include_proxy,
        "include_logs": include_logs,
        "redact": redact,
        "size_limit_bytes": size_limit,
        "size_limit_human": _format_bytes(size_limit) if size_limit is not None else None,
    }
    if redaction:
        manifest["redaction_config"] = {
            "source": str(redaction.source) if redaction.source else None,
            "include_defaults": redaction.include_defaults,
            "custom_patterns": len(redaction.patterns),
            "errors": redaction.errors,
        }

    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        if output_path:
            output_path = Path(output_path)
            if output_path.suffix.lower() == ".zip":
                bundle_path = output_path
            else:
                bundle_path = output_path / f"devhost-diagnostics-{timestamp}.zip"
        else:
            bundle_dir = devhost_dir / "diagnostics"
            bundle_dir.mkdir(parents=True, exist_ok=True)
            bundle_path = bundle_dir / f"devhost-diagnostics-{timestamp}.zip"
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        preview = preview_diagnostic_bundle(
            state,
            config_file=config_file,
            domain_file=domain_file,
            log_path=log_path,
            include_state=include_state,
            include_config=include_config,
            include_proxy=include_proxy,
            include_logs=include_logs,
            redact=redact,
            redaction_file=redaction_file,
            size_limit_bytes=size_limit_bytes,
        )
        if size_limit is not None and preview["total_size"] > size_limit:
            manifest["error"] = f"Bundle size {preview['total_size_human']} exceeds limit {_format_bytes(size_limit)}"
            manifest["over_limit"] = True
            return (False, None, manifest)

        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            if include_state:
                _add_file(
                    zipf,
                    state_file,
                    "state/state.yml",
                    manifest["included"],
                    manifest["missing"],
                    manifest["redacted"],
                    manifest["redaction_skipped"],
                    redact=redact,
                    redaction=redaction,
                )
            if include_config:
                if config_file:
                    _add_file(
                        zipf,
                        config_file,
                        "config/devhost.json",
                        manifest["included"],
                        manifest["missing"],
                        manifest["redacted"],
                        manifest["redaction_skipped"],
                        redact=redact,
                        redaction=redaction,
                    )
                if domain_file:
                    _add_file(
                        zipf,
                        domain_file,
                        "config/domain",
                        manifest["included"],
                        manifest["missing"],
                        manifest["redacted"],
                        manifest["redaction_skipped"],
                        redact=redact,
                        redaction=redaction,
                    )
            if include_logs:
                _add_file(
                    zipf,
                    log_path,
                    "logs/router.log",
                    manifest["included"],
                    manifest["missing"],
                    manifest["redacted"],
                    manifest["redaction_skipped"],
                    redact=redact,
                    redaction=redaction,
                )
                _add_dir(
                    zipf,
                    logs_dir,
                    "logs",
                    manifest["included"],
                    manifest["missing"],
                    manifest["redacted"],
                    manifest["redaction_skipped"],
                    redact=redact,
                    redaction=redaction,
                )
            if include_proxy:
                _add_dir(
                    zipf,
                    proxy_dir,
                    "proxy",
                    manifest["included"],
                    manifest["missing"],
                    manifest["redacted"],
                    manifest["redaction_skipped"],
                    redact=False,
                    redaction=redaction,
                )

            readme = (
                "Devhost Diagnostic Bundle\n"
                "\n"
                "Includes:\n"
                "- state.yml\n"
                "- devhost.json and domain\n"
                "- devhost-owned proxy snippets\n"
                "- devhost logs (router/logs)\n"
                "\n"
                "Redaction: secrets in logs/configs are masked when redaction is enabled.\n"
                "\n"
                "Note: external proxy configs are NOT included.\n"
            )
            zipf.writestr("README.txt", readme)
            zipf.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        return (True, bundle_path, manifest)
    except Exception as exc:
        manifest["error"] = str(exc)
        return (False, None, manifest)
