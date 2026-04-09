# API Reference

## Authentication

Currently unauthenticated for telemetry submission. Rate limiting by IP with fallback to proof-of-work for abuse resistance.

Future: Ed25519 client certificates for authenticated contributions.

## Endpoints

### POST /api/v1/trajectories

Submit cursor trajectory batch.

**Request**

```http
POST /api/v1/trajectories
Content-Type: application/json
X-Telemetry-Consent: true
X-Client-Version: 0.2.0

{
 "trajectories": [
 {
 "trajectory_id": "uuid-v4",
 "timestamp": "2025-01-15T10:30:00.000Z",
 "session_context": {
 "domain": "example.com",
 "page_path": "/products",
 "viewport": {"width": 1920, "height": 1080}
 },
 "samples": [
 {
 "t": 0,
 "x": 145.5,
 "y": 892.0,
 "vx": 0.0,
 "vy": 0.0,
 "ax": 0.0,
 "ay": 0.0,
 "button_state": 0
 }
 ],
 "anonymization": {
 "epsilon": 3.0,
 "mechanism": "laplace",
 "user_consent": true
 }
 }
 ]
}
```

**Response**

```http
201 Created
Content-Type: application/json

{
 "received": 1,
 "accepted": 1,
 "rejected": 0,
 "errors": []
}
```

**Error Responses**

| Status | Code | Description |
|--------|------|-------------|
| 400 | invalid_json | Malformed request body |
| 400 | validation_failed | Schema validation error |
| 400 | bot_detected | Trajectory flagged as automated |
| 429 | rate_limited | Too many requests |
| 413 | payload_too_large | Batch exceeds 10MB |
| 500 | internal_error | Server error (rare) |

### GET /api/v1/health

Health check and system status.

**Response**

```http
200 OK

{
 "status": "healthy",
 "timestamp": "2025-01-15T10:30:01.000Z",
 "version": "0.2.0",
 "database": {
 "connected": true,
 "latency_ms": 2
 },
 "queue": {
 "pending": 0,
 "processing": 0
 }
}
```

### GET /api/v1/stats

Dataset statistics (public).

**Response**

```http
200 OK

{
 "total_trajectories": 15420,
 "total_samples": 8923410,
 "unique_domains": 342,
 "avg_duration_ms": 45000,
 "bot_rate": 0.03,
 "privacy_budget_consumed": {
 "epsilon_total": 3.0,
 "epsilon_used": 0.0
 }
}
```

### GET /metrics

Prometheus metrics endpoint.

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| POST /trajectories | 100 | 60 seconds |
| GET /health | None | - |
| GET /stats | 10 | 60 seconds |
| GET /metrics | Internal | - |

Exceeding limits returns 429 with `Retry-After` header.

## SDKs

- JavaScript (browser): Included in extension
- Python: `pip install telecursor-client` (planned)

## Changelog

### 2025-01-15 (v0.2.0)

- Added batch submission
- Added bot detection
- Added rate limiting

### 2025-01-01 (v0.1.0)

- Initial API
- Single trajectory submission