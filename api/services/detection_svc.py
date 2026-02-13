"""Detection service — scan Sigma YAML rules from the filesystem."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import yaml as _yaml
except ImportError:
    _yaml = None  # type: ignore[assignment]


def _parse_yaml(path: Path) -> Dict[str, Any]:
    """Parse a YAML file, returning an empty dict on failure."""
    try:
        text = path.read_text()
        if _yaml:
            return _yaml.safe_load(text) or {}
        # Minimal fallback for environments without PyYAML
        data: Dict[str, Any] = {"_raw": text}
        for line in text.splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()
        return data
    except Exception:
        logger.warning("Failed to parse %s", path, exc_info=True)
        return {}


def list_rules(rules_dir: str) -> List[Dict[str, Any]]:
    """Return all Sigma rules found under *rules_dir*."""
    base = Path(rules_dir)
    if not base.is_dir():
        return []

    results: List[Dict[str, Any]] = []
    for p in sorted(base.iterdir()):
        if p.suffix not in (".yml", ".yaml"):
            continue
        raw = _parse_yaml(p)
        if not raw:
            continue

        logsource = raw.get("logsource", {}) if isinstance(raw.get("logsource"), dict) else {}
        tags = raw.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        results.append({
            "id": raw.get("id", p.stem),
            "title": raw.get("title", p.stem),
            "description": raw.get("description", ""),
            "category": logsource.get("category", ""),
            "severity": raw.get("level", "medium"),
            "status": raw.get("status", "active"),
            "source": "imported",
            "author": raw.get("author", ""),
            "created": raw.get("date", ""),
            "lastModified": raw.get("date", ""),
            "tags": tags,
            "detectionCount24h": 0,
            "falsePositiveRate": 0.0,
            "coverage": [],
            "ymlContent": p.read_text(),
        })
    return results


def get_rule(rules_dir: str, rule_id: str) -> Optional[Dict[str, Any]]:
    """Return a single rule by its *id* field or filename stem."""
    for rule in list_rules(rules_dir):
        if rule["id"] == rule_id:
            return rule
    return None
