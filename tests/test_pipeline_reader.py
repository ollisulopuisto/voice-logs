#!/usr/bin/env python3
"""Offline checks for Assist pipeline parsing and searchable history pages."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components/voice_logs/history.py"
SPEC = importlib.util.spec_from_file_location("voice_logs_history", SOURCE)
assert SPEC and SPEC.loader
history = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(history)


def event(kind: str, data: dict | None = None, second: int = 0):
    return SimpleNamespace(
        type=kind,
        data=data or {},
        timestamp=f"2026-10-27T12:00:{second:02d}+00:00",
    )


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    events = [
        event(
            "run-start",
            {"pipeline": "pipeline-a", "satellite_id": "assist_satellite.kitchen", "language": "fi"},
        ),
        event("stt-end", {"stt_output": {"text": "Sataako tänään?"}}, 1),
        event(
            "intent-start",
            {"engine": "conversation.home_assistant", "intent_input": "Sataako tänään?"},
            2,
        ),
        event(
            "intent-progress",
            {"chat_log_delta": {"tool_calls": [{"tool_name": "weather.get_forecasts"}]}},
            3,
        ),
        event(
            "intent-end",
            {
                "processed_locally": True,
                "intent_output": {
                    "response": {
                        "speech": {"plain": {"speech": "Ei sada."}},
                        "response_type": "action_done",
                    }
                },
            },
            4,
        ),
        event("run-end", {}, 5),
    ]
    turn = history.flatten_run("run-1", events)
    check(turn is not None, "completed voice run becomes a transcript")
    check(turn["id"] == "run-1", "run ID is a stable transcript ID")
    check(turn["query"] == "Sataako tänään?", "recognized utterance is captured")
    check(turn["answer"] == "Ei sada.", "final answer is captured")
    check(turn["finished"] and turn["status"] == "success", "completed state is captured")
    check(turn["debug"]["mode"] == "local", "local-vs-LLM debug mode is captured")
    check(turn["debug"]["tool_names"] == ["weather.get_forecasts"], "tool names are captured")
    check(turn["actions"][0]["status"] == "requested", "a tool call alone is not claimed successful")

    action_events = [
        event("intent-start", {"intent_input": "Lisää margariini ostoslistalle"}),
        event("intent-progress", {"chat_log_delta": {"tool_calls": [
            SimpleNamespace(id="call-1", tool_name="script__lisaa_ostoslistaan", tool_args={"tuote": "margariini", "private": "do not store"}),
            SimpleNamespace(id="call-2", tool_name="script__lisaa_ostoslistaan", tool_args={"tuote": "maito"}),
        ]}}),
        event("intent-progress", {"chat_log_delta": {
            "role": "tool_result", "tool_call_id": "call-1", "tool_name": "script__lisaa_ostoslistaan",
            "result": SimpleNamespace(data={"large_private_payload": "not stored"}, error=False),
        }}),
        event("intent-progress", {"chat_log_delta": {
            "role": "tool_result", "tool_call_id": "call-2", "tool_name": "script__lisaa_ostoslistaan",
            "result": {"data": {"error": "service failed"}, "error": True},
        }}),
        event("run-end"),
    ]
    actions = history.flatten_run("actions", action_events)["actions"]
    check(len(actions) == 2, "repeated tools remain separate operations by call ID")
    check(actions[0]["parameters"] == {"tuote": "margariini"}, "live HA ToolInput objects expose only selected useful parameters")
    check(actions[0]["status"] == "returned" and actions[1]["status"] == "failed", "tool results are matched to the right operation")
    check("private" not in str(actions), "raw tool result bodies and unrelated arguments are not stored")

    local = history.flatten_run("local", [
        event("intent-start", {"intent_input": "Sammuta valot"}),
        event("intent-end", {"intent_output": {"response": {
            "response_type": "action_done", "data": {
                "success": [{"name": "Olohuone", "id": "light.living"}],
                "failed": [{"name": "Keittiö", "id": "light.kitchen"}],
            },
        }}}), event("run-end"),
    ])
    check(local["actions"][0]["targets"] == ["Olohuone"], "local intent results retain readable targets")
    check([a["status"] for a in local["actions"]] == ["completed", "failed"], "partial local outcomes keep successes and failures distinct")
    rejected = history.flatten_run("rejected", [
        event("intent-start", {"intent_input": "Unrecognized command"}),
        event("intent-end", {"intent_output": {"response": {"response_type": "error", "data": {"code": "no_intent_match"}}}}),
        event("run-end"),
    ])
    check(rejected["status"] == "error", "intent error responses are failures even without a pipeline error event")

    capture = history.ServiceActionCapture()
    runs = [SimpleNamespace(id="local-run", context=SimpleNamespace(id="assist-context"))]
    def service(context_id, parent_id, domain="script", name="lisaa_ostoslistaan"):
        return SimpleNamespace(
            context=SimpleNamespace(id=context_id, parent_id=parent_id),
            data={"domain": domain, "service": name, "service_data": {"tuote": "margariini", "message": "private body"}},
        )
    capture.record(service("automation-context", "assist-context"), runs)
    capture.record(service("script-context", "automation-context", "todo", "add_item"), runs)
    capture.record(service("unrelated", "different-context"), runs)
    finished = {"run_id": "local-run", "finished": True, "actions": []}
    capture.enrich([finished], [])
    check([a["name"] for a in finished["actions"]] == ["script.lisaa_ostoslistaan", "todo.add_item"], "native script and child service calls follow the Assist context chain")
    check(all(a["status"] == "called" for a in finished["actions"]), "service dispatch is not claimed to confirm success")
    check("private body" not in str(finished), "service message payloads are not archived")
    capture.record(service("late", "automation-context"), runs)
    next_turn = {"run_id": "local-run", "finished": True, "actions": []}
    capture.enrich([next_turn], [])
    check(not next_turn["actions"], "finished run contexts are forgotten")
    ambiguous = [*runs, SimpleNamespace(id="other", context=SimpleNamespace(id="assist-context"))]
    capture.record(service("ambiguous", "assist-context"), ambiguous)
    capture.enrich([next_turn], [])
    check(not next_turn["actions"], "ambiguous simultaneous contexts are not guessed")
    detached = SimpleNamespace(context=SimpleNamespace(id="detached", parent_id=None), data={"entity_id": "automation.shopping"})
    script_run = SimpleNamespace(_context=SimpleNamespace(id="detached"), _variables={"trigger": {
        "platform": "conversation", "user_input": {"context": {"id": "assist-context"}},
    }})
    automation = SimpleNamespace(action_script=SimpleNamespace(_runs=[script_run]))
    hass = SimpleNamespace(data={"automation": SimpleNamespace(get_entity=lambda _id: automation)})
    capture.link_automation(detached, hass, runs)
    capture.record(service("detached", None), runs)
    capture.enrich([next_turn], [])
    check(next_turn["actions"][0]["name"] == "script.lisaa_ostoslistaan", "sentence automations are linked through original input context when HA drops the parent")

    typed = history.flatten_run(
        "run-2",
        [
            event("intent-start", {"intent_input": "Kerro vitsi"}),
            event("tts-start", {"tts_input": "Miksi kana ylitti tien?"}, 1),
        ],
    )
    check(typed is not None and typed["query"] == "Kerro vitsi", "text Assist is supported")
    check(typed["answer"] == "Miksi kana ylitti tien?", "TTS text is used as fallback")
    check(not typed["finished"] and typed["status"] == "in_progress", "active run remains live")

    failed = history.flatten_run(
        "run-3",
        [
            event("stt-end", {"stt_output": {"text": "etsi pannukakkuresepti"}}),
            event("error", {"code": "intent-failed", "message": "Agent failed"}, 1),
            event("run-end", {}, 2),
        ],
    )
    check(failed is not None and failed["status"] == "error", "failed turns remain visible")
    check(failed["answer"] == "Agent failed", "failure detail is a readable reply")
    check(history.flatten_run("run-4", [event("run-start"), event("run-end")]) is None, "empty runs are skipped")

    records = [
        {"id": "3", "query": "Pizza taikina", "answer": "Kohota taikina", "hidden": False},
        {"id": "2", "query": "Sää", "answer": "Ei sada", "hidden": True},
        {"id": "1", "query": "Resepti", "answer": "Pannukakku", "hidden": False},
    ]
    page = history.history_page(records, query="pann", include_hidden=False, offset=0, limit=1)
    check(page["total"] == 1 and page["items"][0]["id"] == "1", "search matches query and answer")
    all_page = history.history_page(records, include_hidden=True, offset=0, limit=2)
    check(all_page["total"] == 3 and len(all_page["items"]) == 2, "hidden toggle and pagination work")
    check(all_page["items"][0]["id"] == "3", "history is newest first")
    action_page = history.history_page([local], query="keittiö")
    check(action_page["total"] == 1, "search also covers recorded action targets")
    print("OK: Assist pipeline parsing, live state, debug fields, search, and pagination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
