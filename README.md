# Voice Logs

A Home Assistant HACS integration for a live Assist transcript and a persistent conversation archive.

Voice Logs brings together three useful ideas:

- **Assist Monitor:** reads all Home Assistant Assist pipelines, including local intents, AI agents, voice satellites, and typed Assist.
- **Assist Chat Display:** shows the active request and answer as chat bubbles, then keeps completed turns in the archive.
- **Assist Transcript:** exposes the latest question and answer through `sensor.voice_logs_latest` for dashboards and automations.

The archive is stored locally in Home Assistant. It keeps text and small troubleshooting fields only; it never stores microphone audio or tool-result payloads. There is no automatic phone notification. A dashboard card lets you search older turns, hide and restore entries, page through history, and inspect recorded actions.

## Install with HACS

1. Add this repository in **HACS → Integrations → ⋮ → Custom repositories** as an Integration.
2. Install **Voice Logs** and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and add **Voice Logs**.
4. Add the card below to a dashboard. In Lovelace storage mode, the integration registers the card resource automatically.

For a YAML-managed Lovelace resource list, add:

```yaml
- url: /voice_logs/voice-logs-card.js?v=0.3.4
  type: module
```

## Persistent conversation card

```yaml
type: custom:voice-logs-card
title: Puheavustajan keskustelut
page_size: 20
height: 700px
```

The card has a visual editor in Home Assistant for its title, sensor, page size, dimensions, and diagnostic details. In wide panel views it centers the archive in a readable column up to 1200px wide; set `width` to override that default. Height and width accept CSS dimensions such as `700px`, `40rem`, or `100%`; the archive list scrolls inside a set height. The query and response text is selectable for copy and paste. The card controls are currently in Finnish.

The card starts with visible conversations, newest first. Search covers the complete archive, including hidden conversations only when **Näytä piilotetut** is enabled. Use **Piilota** to take a turn out of the default view and **Palauta** to bring it back. Hiding never deletes a turn. The **Toiminta** section shows the recorded operation, its targets or selected parameters, and the available outcome. It covers AI tool calls, native intent targets, and service calls connected to the active Assist context. A service dispatch is labelled **Palvelukutsu tehty**, not claimed as a confirmed success. Unfinished or historical calls without results are labelled explicitly.

Older entries may lack action details. Voice Logs can enrich entries whose original HA debug run is still available; it does not invent actions for older transcripts. Search also matches saved action names and targets.

For technical troubleshooting, opt into a separate **Tekniset tiedot** section:

```yaml
type: custom:voice-logs-card
show_diagnostics: true
```

## Latest reply card

Use the separate transient card on a tablet dashboard. Its timer is part of the card's frontend behavior, so it hides only this display; the archived conversation stays in the persistent card and sensor.

```yaml
type: custom:voice-logs-latest-card
title: Vastaus valmis
dismiss_after: 30
show_question: false
```

`dismiss_after` is seconds (30 by default). Set it to `0` to keep the card visible until another reply arrives. `show_question: true` also displays what was asked. A new completed Assist answer reappears and restarts the timer. The card tracks the latest answer from `sensor.voice_logs_latest`; opening or reloading the dashboard shows that latest answer and starts a fresh timer.

The latest-reply card also has a Home Assistant visual editor for its title, sensor, dismissal delay, dimensions, and question visibility.

## Latest answer sensor

The integration creates `sensor.voice_logs_latest`. Its state is a short version of the latest response; attributes include the full `question`, `answer`, `created_at`, `run_id`, `debug`, `active`, and `total_conversations`. Both cards use this sensor; the persistent card also loads the archive through the integration's WebSocket API.

## Actions

The integration provides `voice_logs.hide_conversation` and `voice_logs.restore_conversation`, each taking a `conversation_id`. The chat card uses these actions for its hide/restore controls.

## Capture and compatibility

Home Assistant does not put Assist pipeline messages on the event bus. Voice Logs follows the read-only approach used by Assist Monitor: it polls `hass.data["assist_pipeline"].pipeline_debug`, also refreshing when an Assist satellite changes state. Completed turns are persisted immediately in the integration's Store, so the archive outlives Home Assistant's small in-memory debug window and restarts. The integration also imports any still-available completed runs when first set up.

`pipeline_debug` is an internal Home Assistant structure rather than a stable public API. Voice Logs checks for missing or changed data and logs a warning without modifying or patching Home Assistant's pipeline code. Native service capture also reads the active-run registry and listens to the public `call_service` event. For sentence-triggered automations that HA starts without a parent context, it reads the original ConversationInput context from the running automation. It correlates only unambiguous active run contexts and their observed children; unrelated background service calls are excluded. It stores a small allowlist of operation parameters, never full service or tool result payloads.

## Development

Run the standalone checks with:

```bash
python3 tests/test_pipeline_reader.py
python3 -m compileall -q custom_components/voice_logs
```

Report problems through the [issue tracker](https://github.com/ollisulopuisto/voice-logs/issues).
