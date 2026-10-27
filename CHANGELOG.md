# Changelog

## 0.2.1

- Fix the latest-answer sensor reporting `unknown` despite having a saved answer. It now uses Home Assistant's sensor entity implementation.
- Disable polling for the sensor because archive events already update it.

## 0.2.0

- Add the separate latest-reply card with a configurable dismissal timer.
- Provide persistent conversation history with search, hidden entries, and debug details.
