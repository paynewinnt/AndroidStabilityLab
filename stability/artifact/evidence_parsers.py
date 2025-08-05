from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from stability.domain import ArtifactType


_PARSER_VERSION = "structured_evidence.v1"
_MAX_TEXT_BYTES = 256 * 1024


def parse_artifact_evidence(artifact_type: ArtifactType, file_path: str | Path) -> dict[str, Any]:
    """Return structured evidence extracted from high-value issue artifacts.

    The parser is intentionally conservative: it adds machine-readable hints
    without replacing existing text-based detectors.
    """
    path = Path(file_path)
    if artifact_type == ArtifactType.DUMPSYS_SURFACEFLINGER:
        return _parse_surfaceflinger(path)
    if artifact_type == ArtifactType.DROPBOX:
        return _parse_dropbox(path)
    if artifact_type == ArtifactType.PERFETTO_TRACE:
        return _parse_perfetto(path)
    return {}


def _parse_surfaceflinger(path: Path) -> dict[str, Any]:
    text = _read_text_head(path)
    if not text:
        return {}

    signals: list[dict[str, str]] = []
    metrics: dict[str, Any] = {
        "visible_layer_mentions": len(re.findall(r"\bvisible\s+layers?\b", text, re.IGNORECASE)),
        "layer_mentions": len(re.findall(r"\bLayer\b|^\s*\+", text, re.IGNORECASE | re.MULTILINE)),
    }

    for pattern, hint, source in (
        (r"\b(?:no|0)\s+visible\s+layers?\b|\bvisible\s+layers?\s*[:=]\s*0\b", "black_screen", "surfaceflinger"),
        (r"\b(?:black|blank)\s+(?:screen|surface|display|layer)\b", "black_screen", "surfaceflinger"),
        (r"\b(?:no|missing)\s+(?:buffer|frame|visible\s+content)\b", "black_screen", "surfaceflinger"),
        (r"\b(?:stale|not\s+updating|no\s+refresh|missed\s+frame|frozen)\b", "freeze", "frame_refresh"),
        (r"\b(?:present\s+latency|frame\s+timeline|refresh\s+rate)\b", "frame_context", "frame_refresh"),
    ):
        signals.extend(_signals_for_pattern(text, pattern, hint=hint, source=source, raw_source="dumpsys_surfaceflinger"))

    surfaces = _extract_limited(
        text,
        (
            r"SurfaceView[^\n]{0,120}",
            r"ActivityRecord[^\n]{0,120}",
            r"[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+[^\n]{0,80}",
        ),
        limit=5,
    )
    if surfaces:
        metrics["surface_candidates"] = surfaces

    return _summary("surfaceflinger", signals, metrics)


def _parse_dropbox(path: Path) -> dict[str, Any]:
    text = _read_text_head(path)
    if not text:
        return {}

    signals: list[dict[str, str]] = []
    tag_counts: dict[str, int] = {}
    for match in re.finditer(
        r"\b(system_server_watchdog|watchdog|system_app_crash|system_server_crash|system_app_anr|data_app_crash|system_server_wtf)\b",
        text,
        re.IGNORECASE,
    ):
        tag = match.group(1).lower()
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
        hint = _dropbox_hint(tag)
        source = "dropbox"
        signals.append(
            {
                "source": source,
                "raw_source": "dumpsys_dropbox",
                "pattern": tag,
                "hint": hint,
                "fragment": _snippet_around(text, match),
            }
        )

    for pattern, hint in (
        (r"\bWATCHDOG KILLING SYSTEM PROCESS\b", "watchdog"),
        (r"\bProcess:\s*system_server\b", "system_server_crash"),
        (r"\bFATAL EXCEPTION\b", "crash"),
        (r"\bANR\b|Application Not Responding", "anr"),
    ):
        signals.extend(_signals_for_pattern(text, pattern, hint=hint, source="dropbox", raw_source="dumpsys_dropbox"))

    metrics = {"tag_counts": tag_counts, "entry_count_hint": _dropbox_entry_count(text)}
    return _summary("dropbox", signals, metrics)


def _parse_perfetto(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    size_bytes = path.stat().st_size
    data = path.read_bytes()[:_MAX_TEXT_BYTES]
    text = data.decode("utf-8", errors="ignore")

    signals: list[dict[str, str]] = []
    for pattern, hint, source in (
        (r"\bsystem_server\b", "system_server_context", "perfetto"),
        (r"\bSurfaceFlinger\b|android\.surfaceflinger", "surfaceflinger_context", "perfetto"),
        (r"\bwatchdog\b", "watchdog", "perfetto"),
        (r"\b(?:sched_blocked_reason|uninterruptible|blocked)\b", "freeze", "perfetto"),
        (r"\bandroid\.network_packets\b|network_packets", "network_context", "perfetto"),
        (r"\bframe_timeline|present_fence|Choreographer\b", "frame_context", "frame_refresh"),
    ):
        signals.extend(_signals_for_pattern(text, pattern, hint=hint, source=source, raw_source="perfetto_trace"))

    metrics = {
        "size_bytes": size_bytes,
        "scan_bytes": len(data),
        "text_scan_available": bool(text.strip()),
    }
    return _summary("perfetto", signals, metrics)


def _summary(source: str, signals: list[dict[str, str]], metrics: dict[str, Any]) -> dict[str, Any]:
    deduped = _dedupe_signals(signals)
    matched_sources = _ordered_unique(signal["source"] for signal in deduped if signal.get("source"))
    matched_fragments = _ordered_unique(signal["fragment"] for signal in deduped if signal.get("fragment"))
    issue_hints = _ordered_unique(signal["hint"] for signal in deduped if signal.get("hint"))
    confidence = "strong" if len(matched_sources) >= 2 else "medium" if deduped else "none"
    payload: dict[str, Any] = {
        "parser": source,
        "parser_version": _PARSER_VERSION,
        "signals": deduped,
        "matched_sources": matched_sources,
        "matched_fragments": matched_fragments[:8],
        "issue_hints": issue_hints,
        "confidence": confidence,
        "metrics": metrics,
    }
    if issue_hints:
        payload["summary"] = f"{source}: " + ", ".join(issue_hints[:4])
    return payload


def _read_text_head(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_bytes()[:_MAX_TEXT_BYTES].decode("utf-8", errors="ignore")


def _signals_for_pattern(
    text: str,
    pattern: str,
    *,
    hint: str,
    source: str,
    raw_source: str,
) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    for match in re.finditer(pattern, text, re.IGNORECASE):
        signals.append(
            {
                "source": source,
                "raw_source": raw_source,
                "pattern": pattern,
                "hint": hint,
                "fragment": _snippet_around(text, match),
            }
        )
    return signals


def _snippet_around(text: str, match: re.Match[str], *, limit: int = 220) -> str:
    start = max(match.start() - 90, 0)
    end = min(match.end() + 130, len(text))
    return " ".join(text[start:end].split())[:limit].strip()


def _extract_limited(text: str, patterns: tuple[str, ...], *, limit: int) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            value = " ".join(match.group(0).split())[:160]
            if value and value not in seen:
                seen.add(value)
                values.append(value)
            if len(values) >= limit:
                return values
    return values


def _dropbox_hint(tag: str) -> str:
    if "watchdog" in tag:
        return "watchdog"
    if tag == "system_server_crash" or tag == "system_server_wtf":
        return "system_server_crash"
    if tag.endswith("_anr"):
        return "anr"
    if tag.endswith("_crash"):
        return "crash"
    return "dropbox_context"


def _dropbox_entry_count(text: str) -> int:
    header_matches = re.findall(r"^\d{4}-\d{2}-\d{2}|\b\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", text, re.MULTILINE)
    if header_matches:
        return len(header_matches)
    return len(re.findall(r"\b(?:system_|data_)[a-z_]+\b", text, re.IGNORECASE))


def _dedupe_signals(signals: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for signal in signals:
        key = (
            str(signal.get("source", "")),
            str(signal.get("hint", "")),
            str(signal.get("fragment", ""))[:120],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(signal)
    return deduped[:20]


def _ordered_unique(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "")
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
