# New Chat Prompt Template

Use this when starting a new chat.

---

You are helping me build a manufacturing warehouse simulator.

Current version: v0.2.0
Target version: v0.3.0

Read the project state and API surface below before suggesting changes.

## Rules

- Implement only the target version.
- Do not implement future features.
- Do not rename existing public functions or classes unless required.
- If a rename is required, list it clearly as a breaking change.
- Keep simulation logic outside Flask routes.
- Keep frontend JavaScript vanilla.
- Prefer small, reviewable patches.
- Preserve the existing architecture.
- If unsure, ask clarifying questions before changing core files.

## Project State

[paste docs/PROJECT_STATE.md]

## API Surface

[paste docs/API_SURFACE.md]

## Task For This Chat

Describe the exact version or feature here.

Example:

Implement v0.3.0: improve the task system so tasks can use different pickup
and dropoff locations. Keep the simulation engine independent from Flask.
Do not add battery, charging, collision avoidance, database, or WebSocket yet.