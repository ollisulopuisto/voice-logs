# Voice Logs HACS Integration Plan

**Goal:** Combine Assist Monitor's all-pipeline capture, Assist Chat Display's live chat bubbles, and Assist Transcript's latest-answer sensor in a standalone HACS integration with a persistent searchable archive.

**Architecture:** Read Home Assistant's Assist debug store without patching Core, refresh incrementally on satellite activity plus a safety poll, persist each completed run in a `Store`, and expose paginated history over the authenticated WebSocket API. A bundled Lovelace card shows live and archived exchanges with search, paging, hidden/restore controls, and expandable debug details.

**Files:** `custom_components/voice_logs/`, `tests/`, `hacs.json`, `README.md`.

**Validation:** Pure Python tests for pipeline parsing and archive filtering; JSON/YAML and JavaScript syntax checks; Python compilation. Live deployment is separate and uses the user's HA deployment procedure.
