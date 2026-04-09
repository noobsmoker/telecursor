# API Reference

## Base URL

```
Production: https://api.telecursor.ai
Development: http://localhost:3000
```

## Endpoints

### Health Check

```
GET /health
```

Returns server health status.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-04-09T14:00:00.000Z",
  "version": "0.1.0"
}
```

---

### Submit Trajectory

```
POST /api/v1/trajectories
```

Submit cursor trajectory data from the browser extension.

**Headers:**
```
Content-Type: application/json
X-Telemetry-Consent: true
```

**Request Body:**
```json
{
  "session_context": {
    "domain": "github.com",
    "page_path": "/features/copilot",
    "viewport": { "width": 1920, "height": 1080 },
    "device_type": "desktop",
    "input_method": "mouse"
  },
  "samples": [
    { "t": 0, "x": 145.5, "y": 892.0, "vx": 0.0, "vy": 0.0, "ax": 0.0, "ay": 0.0, "button_state": 0 }
  ],
  "interaction_events": [
    { "t": 1250, "type": "click", "x": 200, "y": 300, "target": { "tag": "A", "role": "link" } }
  ],
  "anonymization": {
    "user_consent": true,
    "local_dp_applied": true
  }
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "trajectory_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Trajectory recorded successfully"
}
```

**Error Responses:**
- `400 Bad Request` — Missing required fields
- `403 Forbidden` — Consent not verified
- `429 Too Many Requests` — Rate limit exceeded
- `500 Internal Server Error` — Server error

---

### Get Trajectory

```
GET /api/v1/trajectories/:id
```

Retrieve a specific trajectory by ID.

**Response:**
```json
{
  "trajectory_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-04-09T14:00:00.000Z",
  "session_context": {
    "domain_category": "developer",
    "viewport": { "width": 1920, "height": 1080 },
    "device_type": "desktop",
    "input_method": "mouse"
  },
  "stats": {
    "sample_count": 250,
    "duration_ms": 5000,
    "click_count": 3,
    "hover_count": 12,
    "scroll_count": 2
  },
  "samples": [
    { "t": 0, "x": 145, "y": 892, "vx": 0, "vy": 0 }
  ],
  "interaction_events": [
    { "t_ms": 1250, "event_type": "click", "x": 200, "y": 300, "target_tag": "A", "target_role": "link", "target_category": "link" }
  ]
}
```

---

### Query Trajectories

```
GET /api/v1/trajectories
```

Query trajectories with filters.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `domain_category` | string | - | Filter by domain category |
| `device_type` | string | - | Filter by device type |
| `min_samples` | number | - | Minimum sample count |
| `limit` | number | 100 | Results per page (max 1000) |
| `offset` | number | 0 | Pagination offset |

**Example:**
```
GET /api/v1/trajectories?domain_category=developer&device_type=desktop&limit=10
```

**Response:**
```json
{
  "trajectories": [
    { "id": "...", "created_at": "...", "domain_category": "developer", ... }
  ],
  "limit": 10,
  "offset": 0
}
```

---

### Delete Trajectory

```
DELETE /api/v1/trajectories/:id
```

Delete a trajectory (user data deletion request).

**Response:**
```json
{
  "success": true,
  "message": "Trajectory deleted"
}
```

---

### Get Statistics

```
GET /api/v1/stats
```

Get overall aggregated statistics.

**Response:**
```json
{
  "summary": {
    "total_sessions": 15420,
    "total_samples": 3855000,
    "total_duration_hours": 1070,
    "unique_domains": 12
  },
  "today": {
    "total_sessions": 234,
    "total_samples": 58500
  },
  "weekly": [
    { "date": "2026-04-03", "total_sessions": 2100, "total_samples": 525000 },
    { "date": "2026-04-04", "total_sessions": 2350, "total_samples": 587500 }
  ],
  "updated_at": "2026-04-09T14:00:00.000Z"
}
```

---

### Get Domain Statistics

```
GET /api/v1/stats/domains
```

Get statistics grouped by domain category.

**Response:**
```json
{
  "domains": [
    {
      "category": "developer",
      "session_count": 5420,
      "total_samples": 1355000,
      "avg_samples": 250,
      "total_duration_hours": 376,
      "avg_duration_ms": 5000
    }
  ]
}
```

---

### Get Device Statistics

```
GET /api/v1/stats/devices
```

Get statistics grouped by device type and input method.

**Response:**
```json
{
  "devices": [
    {
      "device_type": "desktop",
      "input_method": "mouse",
      "session_count": 12000,
      "total_samples": 3000000
    }
  ]
}
```

---

### Get Leaderboard

```
GET /api/v1/stats/leaderboard
```

Get top contributing domains (last 30 days).

**Response:**
```json
{
  "period": "last_30_days",
  "domains": [
    { "rank": 1, "category": "developer", "contribution_count": 5420, "total_samples": 1355000 }
  ]
}
```

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| POST /api/v1/trajectories | 100/minute/IP |
| GET /api/v1/* | 200/minute/IP |

**Response Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1712676240
```

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Missing required fields: session_context, samples, anonymization"
}
```

### 403 Forbidden
```json
{
  "error": "User consent required for data submission"
}
```

### 404 Not Found
```json
{
  "error": "Trajectory not found"
}
```

### 429 Too Many Requests
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 30
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error"
}
```

---

## Client Integration

### JavaScript (Browser Extension)

```javascript
async function submitTrajectory(data) {
  const response = await fetch('https://api.telecursor.ai/api/v1/trajectories', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Telemetry-Consent': 'true'
    },
    body: JSON.stringify(data)
  });
  
  return response.json();
}
```

### Python

```python
import requests

def submit_trajectory(data: dict) -> dict:
    response = requests.post(
        'https://api.telecursor.ai/api/v1/trajectories',
        json=data,
        headers={'X-Telemetry-Consent': 'true'}
    )
    return response.json()
```