# Changelog

## 0.3.3

- Add Home Assistant visual editors for both cards, including configurable dimensions.
- Center the archive in panel views and keep its conversation list readable on wide screens.

## 0.3.2

- Add HACS and Hassfest validation, repository metadata, and a local integration icon.
- Clarify configuration and dashboard setup for new installations.

## 0.3.1

- Link native sentence-triggered automations through the original ConversationInput context. HA starts these automations without a parent context, so context ancestry alone missed their service calls.

## 0.3.0

- Replace the default debug section with **Toiminta**: recorded operations, targets, selected parameters, and honest outcome labels.
- Capture native Assist service dispatches through their active context, including nested scripts, without patching Home Assistant.
- Capture actual HA ToolInput/ToolResult objects and serialized debug events, distinguishing calls from results and failures.
- Keep technical fields available through `show_diagnostics: true` and include actions in archive search.
- Enrich older entries only when the original debug evidence is still available, preserving hidden state.

## 0.2.1

- Fix the latest-answer sensor reporting `unknown` despite having a saved answer. It now uses Home Assistant's sensor entity implementation.
- Disable polling for the sensor because archive events already update it.

## 0.2.0

- Add the separate latest-reply card with a configurable dismissal timer.
- Provide persistent conversation history with search, hidden entries, and debug details.
