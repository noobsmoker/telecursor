# Dataset Schema

This document describes the complete data schema for TeleCursor's cursor telemetry dataset.

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-04-09 | Initial schema |

## Core Data Types

### Trajectory

The primary data structure containing a complete cursor session.

```json
{
  "trajectory_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-04-09T14:00:00.000Z",
  "session_context": { ... },
  "samples": [ ... ],
  "interaction_events": [ ... ],
  "task": { ... },
  "anonymization": { ... }
}
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trajectory_id` | UUID v4 | Yes | Unique identifier for this trajectory |
| `timestamp` | ISO 8601 | Yes | Session start time (UTC) |
| `session_context` | Object | Yes | Environmental context |
| `samples` | Array | Yes | Raw cursor position samples |
| `interaction_events` | Array | No | Semantic events (clicks, hovers) |
| `task` | Object | No | Task-level annotations |
| `anonymization` | Object | Yes | Privacy metadata |

---

## Session Context

Environmental information about the browsing session.

```json
{
  "domain": "github.com",
  "page_path": "/features/copilot",
  "viewport": { "width": 1920, "height": 1080 },
  "device_type": "desktop",
  "input_method": "mouse"
}
```

**Fields:**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `domain` | string | Full domain name | `"github.com"` |
| `page_path` | string | URL path (hashed in storage) | `"/features/copilot"` |
| `viewport.width` | integer | Viewport width in pixels | `1920` |
| `viewport.height` | integer | Viewport height in pixels | `1080` |
| `device_type` | string | Device category | `"desktop"`, `"mobile"`, `"tablet"` |
| `input_method` | string | Input device type | `"mouse"`, `"trackpad"`, `"touch"` |

---

## Cursor Samples

Raw cursor physics data at 50Hz (configurable).

```json
[
  {
    "t": 0,
    "x": 145.5,
    "y": 892.0,
    "vx": 0.0,
    "vy": 0.0,
    "ax": 0.0,
    "ay": 0.0,
    "pressure": 1.0,
    "button_state": 0
  }
]
```

**Fields:**

| Field | Type | Description | Range |
|-------|------|-------------|-------|
| `t` | float | Milliseconds from trajectory start | ≥ 0 |
| `x` | float | X coordinate (viewport-relative) | 0 - viewport.width |
| `y` | float | Y coordinate (viewport-relative) | 0 - viewport.height |
| `vx` | float | X velocity (pixels/second) | -2000 to 2000 |
| `vy` | float | Y velocity (pixels/second) | -2000 to 2000 |
| `ax` | float | X acceleration (pixels/second²) | -10000 to 10000 |
| `ay` | float | Y acceleration (pixels/second²) | -10000 to 10000 |
| `pressure` | float | Pointer pressure (if available) | 0 - 1 |
| `button_state` | integer | Bitmask of pressed buttons | 0 - 7 |

**Button State Bitmask:**
- `0` = No button
- `1` = Left button
- `2` = Right button
- `4` = Middle button

---

## Interaction Events

Semantic events captured during the session.

```json
[
  {
    "t": 1250,
    "type": "hover_start",
    "x": 200,
    "y": 300,
    "target": {
      "tag": "A",
      "role": "link",
      "selector": "nav > a[href='/pricing']",
      "semantic_category": "link"
    }
  },
  {
    "t": 2100,
    "type": "click",
    "x": 200,
    "y": 300,
    "target": { ... },
    "outcome": "navigation"
  }
]
```

**Event Types:**

| Type | Description |
|------|-------------|
| `hover_start` | Mouse entered element (after 300ms dwell) |
| `hover_end` | Mouse left element |
| `mousedown` | Button pressed |
| `mouseup` | Button released |
| `click` | Full click (down + up) |
| `scroll` | Page scrolled |
| `keydown` | Keyboard pressed |
| `typing` | Text input detected |

**Target Object:**

| Field | Type | Description |
|-------|------|-------------|
| `tag` | string | HTML tag name (lowercase) |
| `role` | string | ARIA role or inferred role |
| `selector` | string | CSS selector (privacy-generalized) |
| `semantic_category` | string | Category: `link`, `button`, `input`, `text`, etc. |
| `bounding_box` | Object | Position and size (optional) |

---

## Task Annotations

User-provided or inferred task information.

```json
{
  "stated_goal": "compare pricing plans",
  "inferred_intent": "information_seeking",
  "completion_status": "success",
  "frustration_signals": []
}
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `stated_goal` | string | User-provided goal (optional) |
| `inferred_intent` | string | Model-predicted intent |
| `completion_status` | string | `success`, `failure`, `abandoned` |
| `frustration_signals` | Array | Detected frustration indicators |

**Intent Categories:**
- `information_seeking` - Looking for information
- `navigation` - Finding specific page
- `transaction` - Making a purchase/action
- `communication` - Sending messages
- `content_creation` - Writing/editing
- `entertainment` - Consuming media

---

## Anonymization Metadata

Privacy-related processing information.

```json
{
  "user_consent": true,
  "local_dp_applied": true,
  "personal_data_scrubbed": true,
  "hash_id": "a1b2c3d4e5f6"
}
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `user_consent` | boolean | Whether user consented to contribution |
| `local_dp_applied` | boolean | Whether client-side DP was applied |
| `personal_data_scrubbed` | boolean | Whether PII was removed |
| `hash_id` | string | Truncated hash for rate limiting (not for identification) |

---

## Database Storage Schema

In the server database, data is stored in anonymized form:

```sql
-- trajectories (metadata only)
CREATE TABLE trajectories (
  id TEXT PRIMARY KEY,
  domain_category TEXT,        -- e.g., "developer", "shopping"
  page_path_hash TEXT,         -- SHA256 hash
  viewport_width INTEGER,
  viewport_height INTEGER,
  device_type TEXT,
  input_method TEXT,
  sample_count INTEGER,
  duration_ms INTEGER,
  click_count INTEGER,
  hover_count INTEGER,
  scroll_count INTEGER,
  consent_verified INTEGER,
  expires_at TEXT
);

-- trajectory_samples (downsampled)
CREATE TABLE trajectory_samples (
  trajectory_id TEXT,
  t_ms INTEGER,
  x REAL,
  y REAL,
  vx REAL,
  vy REAL
);

-- interaction_events (generalized)
CREATE TABLE interaction_events (
  trajectory_id TEXT,
  t_ms INTEGER,
  event_type TEXT,
  target_tag TEXT,
  target_role TEXT,
  target_category TEXT
);
```

---

## Public Dataset Release

When releasing data publicly (e.g., on HuggingFace):

```json
{
  "version": "1.0.0",
  "release_date": "2026-04-09",
  "trajectories_count": 10000,
  "samples_count": 2500000,
  "privacy_guarantees": {
    "epsilon": 3.0,
    "k_anonymity": 5,
    "differential_privacy": true
  },
  "categories": {
    "developer": 3500,
    "shopping": 2500,
    "social": 2000,
    "search": 1500,
    "other": 500
  }
}
```

---

## Example: Complete Trajectory

```json
{
  "trajectory_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-04-09T14:00:00.000Z",
  "session_context": {
    "domain": "github.com",
    "page_path": "/features/copilot",
    "viewport": { "width": 1920, "height": 1080 },
    "device_type": "desktop",
    "input_method": "mouse"
  },
  "samples": [
    { "t": 0, "x": 145.5, "y": 892.0, "vx": 0.0, "vy": 0.0, "ax": 0.0, "ay": 0.0, "pressure": 1.0, "button_state": 0 },
    { "t": 20, "x": 145.8, "y": 891.5, "vx": 15.0, "vy": -25.0, "ax": 750.0, "ay": -2500.0, "pressure": 1.0, "button_state": 0 },
    { "t": 40, "x": 146.5, "y": 890.0, "vx": 35.0, "vy": -75.0, "ax": 1000.0, "ay": -2500.0, "pressure": 1.0, "button_state": 0 }
  ],
  "interaction_events": [
    { "t": 300, "type": "hover_start", "x": 200, "y": 300, "target": { "tag": "a", "role": "link", "semantic_category": "link" } },
    { "t": 1250, "type": "click", "x": 200, "y": 300, "target": { "tag": "a", "role": "link", "semantic_category": "link" }, "outcome": "navigation" }
  ],
  "task": {
    "inferred_intent": "information_seeking",
    "completion_status": "success"
  },
  "anonymization": {
    "user_consent": true,
    "local_dp_applied": true,
    "personal_data_scrubbed": true,
    "hash_id": "a1b2c3d4"
  }
}
```

---

## Validation Rules

All submitted trajectories must pass these validation rules:

1. **Sample rate:** Between 20-100 Hz
2. **Duration:** Between 5 seconds and 10 minutes
3. **Position bounds:** All coordinates within viewport
4. **Physics limits:** No impossible velocities (> 5000 px/s)
5. **Consent:** Must have `user_consent: true`
6. **Bot detection:** Trajectory must pass human-like movement check

---

## Changelog

This schema follows semantic versioning. See [CHANGELOG.md](../../CHANGELOG.md) for version history.