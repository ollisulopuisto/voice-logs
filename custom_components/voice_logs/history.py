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


def _field(value: Any, name: str, default: Any = None) -> Any:
    """HA's live tool events contain objects; WS debug events contain dictionaries."""
    return value.get(name, default) if isinstance(value, Mapping) else getattr(value, name, default)


def _action_parameters(arguments: Any) -> dict[str, Any]:
    """Keep only small, useful operation parameters, never full tool payloads."""
    allowed = (
        "entity_id", "name", "area", "area_id", "item", "tuote", "lista",
        "haku", "temperature", "brightness", "volume_level", "domain", "service",
    )
    result = {}
    for key in allowed:
        value = _mapping(arguments).get(key)
        if isinstance(value, (str, int, float, bool)):
            result[key] = value[:180] if isinstance(value, str) else value
        elif isinstance(value, list):
            result[key] = [str(item)[:180] for item in value[:8] if isinstance(item, (str, int, float))]
    target = _mapping(_mapping(arguments).get("target"))
    for key in ("entity_id", "area_id"):
        if key not in result and isinstance(target.get(key), str):
            result[key] = target[key][:180]
    return result


def _target_names(targets: Any) -> list[str]:
    if not isinstance(targets, list):
        return []
    return [str(t.get("name") or t.get("id"))[:180] for t in targets[:20]
            if isinstance(t, Mapping) and (t.get("name") or t.get("id"))]


def active_pipeline_runs(hass: Any) -> list[Any]:
    """Read current run contexts; if HA changes this internal registry, skip it."""
    data = hass.data.get(ASSIST_PIPELINE_KEY)
    registry = getattr(getattr(data, "pipeline_runs", None), "_pipeline_runs", {})
    if not isinstance(registry, Mapping):
        return []
    return [run for runs in registry.values() if isinstance(runs, Mapping) for run in runs.values()]


class ServiceActionCapture:
    """Attribute actual service dispatches only to unambiguous active Assist contexts."""

    def __init__(self) -> None:
        self._actions: dict[str, list[dict[str, Any]]] = {}
        self._contexts: dict[str, str] = {}

    def link_automation(self, event: Any, hass: Any, runs: Sequence[Any]) -> None:
        """HA sentence triggers omit parent_id; recover the original input context."""
        component = hass.data.get("automation")
        get_entity = getattr(component, "get_entity", None)
        if get_entity is None:
            return
        entity = get_entity(_mapping(getattr(event, "data", None)).get("entity_id"))
        context_id = _field(getattr(event, "context", None), "id")
        if not context_id:
            return
        candidates = set()
        for script_run in getattr(getattr(entity, "action_script", None), "_runs", []):
            if _field(getattr(script_run, "_context", None), "id") != context_id:
                continue
            variables = getattr(script_run, "_variables", {})
            trigger = _mapping(variables.get("trigger"))
            if trigger.get("platform") != "conversation":
                continue
            original = _mapping(_mapping(trigger.get("user_input")).get("context")).get("id")
            if original:
                candidates.update(str(run.id) for run in runs if _field(getattr(run, "context", None), "id") == original)
        if len(candidates) == 1:
            self._contexts[context_id] = candidates.pop()

    def record(self, event: Any, runs: Sequence[Any]) -> None:
        data = _mapping(getattr(event, "data", None))
        domain, service = data.get("domain"), data.get("service")
        if not domain or not service or domain == "voice_logs":
            return
        context = getattr(event, "context", None)
        context_ids = {value for value in (_field(context, "id"), _field(context, "parent_id")) if value}
        active_ids = {str(run.id) for run in runs}
        matches = {str(run.id) for run in runs if _field(getattr(run, "context", None), "id") in context_ids}
        matches.update(self._contexts[c] for c in context_ids if c in self._contexts and self._contexts[c] in active_ids)
        if len(matches) != 1:
            return
        run_id = matches.pop()
        actions = self._actions.setdefault(run_id, [])
        if len(actions) >= 50:
            return
        if context_id := _field(context, "id"):
            self._contexts[context_id] = run_id
        actions.append({
            "kind": "service", "name": f"{domain}.{service}", "status": "called",
            "parameters": _action_parameters(data.get("service_data")), "targets": [],
        })

    def enrich(self, turns: list[dict[str, Any]], runs: Sequence[Any]) -> None:
        """Attach observed dispatches, then forget finished and abandoned contexts."""
        finished = set()
        for turn in turns:
            turn.setdefault("actions", []).extend(self._actions.get(turn["run_id"], []))
            if turn["finished"]:
                finished.add(turn["run_id"])
        keep = {str(run.id) for run in runs} - finished
        self._actions = {key: value for key, value in self._actions.items() if key in keep}
        self._contexts = {key: value for key, value in self._contexts.items() if value in keep}


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
    tool_actions: dict[str, dict[str, Any]] = {}
    intent_actions: list[dict[str, Any]] = []
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
                name = _field(call, "tool_name")
                if not name:
                    continue
                call_id = str(_field(call, "id") or f"{name}:{len(tool_actions)}")
                if call_id not in tool_actions:
                    tool_names.append(str(name))
                    tool_actions[call_id] = {
                        "kind": "tool", "name": str(name), "status": "requested",
                        "parameters": _action_parameters(_field(call, "tool_args")),
                        "targets": [],
                    }
            if delta.get("role") == "tool_result":
                call_id = str(delta.get("tool_call_id") or "")
                name = str(delta.get("tool_name") or "")
                if call_id and name:
                    action = tool_actions.setdefault(call_id, {
                        "kind": "tool", "name": name, "status": "requested",
                        "parameters": {}, "targets": [],
                    })
                    result = delta.get("result")
                    payload = _mapping(_field(result, "data", delta.get("tool_result")))
                    failed = bool(_field(result, "error", False) or payload.get("error") or payload.get("success") is False)
                    action["status"] = "failed" if failed else "returned"
        elif kind == "intent-end":
            processed_locally = data.get("processed_locally")
            output = _mapping(data.get("intent_output"))
            response = _mapping(output.get("response"))
            speech = _mapping(response.get("speech"))
            plain = _mapping(speech.get("plain"))
            answer = str(plain.get("speech") or answer).strip()
            response_type = response.get("response_type")
            response_data = _mapping(response.get("data"))
            for outcome, action_status in (("success", "completed"), ("failed", "failed")):
                targets = _target_names(response_data.get(outcome))
                if targets:
                    intent_actions.append({
                        "kind": "intent", "name": str(response_type or "action_done"),
                        "status": "answered" if response_type == "query_answer" and outcome == "success" else action_status,
                        "targets": targets, "parameters": {},
                    })
            if response_type == "error":
                error_code = response_data.get("code") or "intent-error"
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
        "actions": [*tool_actions.values(), *intent_actions],
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
            or needle in str(record.get("actions", [])).casefold()
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
