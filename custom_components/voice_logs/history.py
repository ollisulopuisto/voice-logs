"""Pure helpers for reading and filtering Home Assistant Assist pipeline runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

ASSIST_PIPELINE_KEY = "assist_pipeline"


def _event_type(event: Any) -> str:
    value = getattr(event, "type", "")
    return str(getattr(value, "value", value) or "")


def _mapping(value: Any) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def flatten_run(run_id: str, events: Sequence[Any]) -> dict[str, Any] | None:
    """Extract a safe transcript and useful troubleshooting fields from one run."""
    query = ""
    answer = ""
    started_at = ""
    pipeline_id = None
    satellite_id = None
    language = None
    intent_engine = None
    stt_engine = None
    processed_locally = None
    response_type = None
    error_code = None
    error_message = None
    tool_names: list[str] = []
    finished = False

    for event in events:
        kind = _event_type(event)
        data = _mapping(getattr(event, "data", None))
        timestamp = str(getattr(event, "timestamp", "") or "")

        if kind == "run-start":
            started_at = timestamp or started_at
            pipeline_id = data.get("pipeline", pipeline_id)
            satellite_id = data.get("satellite_id", satellite_id)
            language = data.get("language", language)
        elif kind == "stt-start":
            stt_engine = data.get("engine", stt_engine)
        elif kind == "stt-end":
            output = _mapping(data.get("stt_output"))
            query = str(output.get("text") or query).strip()
        elif kind == "intent-start":
            query = str(data.get("intent_input") or query).strip()
            intent_engine = data.get("engine", intent_engine)
        elif kind == "intent-progress":
            delta = _mapping(data.get("chat_log_delta"))
            for call in delta.get("tool_calls") or []:
                if isinstance(call, Mapping) and call.get("tool_name"):
                    tool_names.append(str(call["tool_name"]))
        elif kind == "intent-end":
            processed_locally = data.get("processed_locally")
            output = _mapping(data.get("intent_output"))
            response = _mapping(output.get("response"))
            speech = _mapping(response.get("speech"))
            plain = _mapping(speech.get("plain"))
            answer = str(plain.get("speech") or answer).strip()
            response_type = response.get("response_type")
        elif kind == "tts-start":
            answer = answer or str(data.get("tts_input") or "").strip()
        elif kind == "error":
            error_code = data.get("code")
            error_message = data.get("message")
            answer = answer or str(error_message or "").strip()
        elif kind == "run-end":
            finished = True

    if not query:
        return None

    if error_code:
        status = "error"
    elif any(_event_type(event) == "intent-end" for event in events):
        status = "success"
    else:
        status = "in_progress"

    mode = "local" if processed_locally is True else "llm" if processed_locally is False else None
    return {
        "id": str(run_id),
        "run_id": str(run_id),
        "query": query,
        "answer": answer,
        "created_at": started_at or str(getattr(events[0], "timestamp", "") or ""),
        "finished": finished,
        "hidden": False,
        "status": status,
        "debug": {
            "pipeline_id": pipeline_id,
            "satellite_id": satellite_id,
            "language": language,
            "stt_engine": stt_engine,
            "intent_engine": intent_engine,
            "mode": mode,
            "response_type": response_type,
            "tool_names": tool_names,
            "error_code": error_code,
            "error_message": error_message,
        },
    }


def parse_pipeline_debug(pipeline_debug: Any) -> list[dict[str, Any]]:
    """Flatten recent runs from HA's read-only pipeline debug store."""
    if not isinstance(pipeline_debug, Mapping):
        return []

    turns: list[dict[str, Any]] = []
    for _pipeline_id, runs in pipeline_debug.items():
        if not isinstance(runs, Mapping):
            continue
        for run_id, run in runs.items():
            events = getattr(run, "events", None)
            if not events:
                continue
            turn = flatten_run(str(run_id), events)
            if turn is not None:
                turns.append(turn)

    return sorted(turns, key=lambda turn: turn.get("created_at", ""), reverse=True)


def parse_all(hass: Any) -> list[dict[str, Any]]:
    """Read the internal debug store defensively; no monkeypatching or mutation."""
    pipeline_data = hass.data.get(ASSIST_PIPELINE_KEY)
    return parse_pipeline_debug(getattr(pipeline_data, "pipeline_debug", None))


def history_page(
    records: Sequence[dict[str, Any]],
    *,
    query: str = "",
    include_hidden: bool = False,
    offset: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    """Filter newest-first history and return a bounded page."""
    needle = query.strip().casefold()
    matched = [
        record
        for record in records
        if (include_hidden or not record.get("hidden", False))
        and (
            not needle
            or needle in str(record.get("query", "")).casefold()
            or needle in str(record.get("answer", "")).casefold()
            or needle in str(record.get("debug", {})).casefold()
        )
    ]
    safe_offset = max(0, offset)
    safe_limit = min(max(1, limit), 100)
    return {
        "items": matched[safe_offset : safe_offset + safe_limit],
        "total": len(matched),
        "offset": safe_offset,
        "limit": safe_limit,
    }
