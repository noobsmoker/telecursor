# TeleCursor Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                TELECURSOR                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Browser   │───▶│   Server    │───▶│  Database   │───▶│   Public    │  │
│  │  Extension │    │   (API)     │    │  (SQLite)   │    │   Dataset   │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│        │                   │                   │                   │       │
│        ▼                   ▼                   ▼                   ▼       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        PRIVACY LAYER                                   │  │
│  │   Local DP  →  Consent  →  Rate Limit  →  Anonymization  →  k-Anon    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Browser Extension

```
browser-extension/
├── manifest.json           # Extension manifest (MV3)
└── src/
    ├── content.js          # Cursor tracking engine
    │   ├── CursorTracker   # Core tracking class
    │   ├── PhysicsEngine   # Velocity/acceleration calculation
    │   └── DOMSnapshots   # Element context capture
    │
    ├── background.js       # Service worker
    │   ├── StorageManager  # Local data management
    │   ├── SyncHandler     # Server communication
    │   └── StatsTracker   # User statistics
    │
    ├── popup/              # User dashboard
    │   ├── popup.html      # Status UI
    │   └── popup.js        # Controls & export
    │
    └── privacy/
        ├── local_dp.js     # Differential privacy
        └── consent.js      # Consent management
```

**Key Features:**
- 50Hz sampling rate (configurable)
- Physics calculation: position, velocity, acceleration
- DOM context: tag, role, selector, bounding box
- Local DP: Laplace noise + subsampling
- Granular consent: global + per-site

### 2. Server API

```
server/src/
├── index.js           # Express app entry
├── db/
│   └── database.js    # SQLite schema & queries
├── routes/
│   ├── trajectories.js  # POST/GET trajectories
│   └── stats.js        # Public aggregations
└── middleware/
    ├── consent.js      # Consent verification
    ├── rateLimit.js    # Abuse prevention
    └── logging.js      # Request logging
```

**API Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/trajectories` | POST | Submit trajectory |
| `/api/v1/trajectories` | GET | Query trajectories |
| `/api/v1/trajectories/:id` | GET | Get trajectory |
| `/api/v1/trajectories/:id` | DELETE | Delete trajectory |
| `/api/v1/stats` | GET | Overall statistics |
| `/api/v1/stats/domains` | GET | By domain category |
| `/api/v1/stats/devices` | GET | By device type |
| `/api/v1/stats/leaderboard` | GET | Top contributors |

### 3. Database Schema

```
┌─────────────────────┐       ┌──────────────────────┐
│   trajectories      │       │  trajectory_samples  │
├─────────────────────┤       ├──────────────────────┤
│ id (PK)             │──┐    │ id (PK)              │
│ created_at          │  │    │ trajectory_id (FK)   │
│ domain_category     │  └──▶│ t_ms                 │
│ viewport_width      │       │ x, y, vx, vy         │
│ device_type         │       └──────────────────────┘
│ sample_count        │
│ duration_ms         │
│ consent_verified    │
└─────────────────────┘

┌─────────────────────┐       ┌──────────────────────┐
│ interaction_events  │       │     daily_stats      │
├─────────────────────┤       ├──────────────────────┤
│ id (PK)             │       │ date (PK)            │
│ trajectory_id (FK) │       │ total_sessions       │
│ t_ms               │       │ total_samples        │
│ event_type          │       │ total_duration_ms    │
│ target_tag          │       │ unique_domains       │
│ target_category     │       └──────────────────────┘
└─────────────────────┘
```

### 4. Model Training Pipeline

```
models/
├── stage1_cursor_dynamics/    # Foundation model
│   ├── config.yaml            # Hyperparameters
│   ├── model.py               # Transformer architecture
│   └── train.py               # Training loop
│
├── stage2_grounding/          # Semantic grounding
│   ├── config.yaml
│   ├── model.py               # Cross-attention model
│   └── train.py
│
└── stage3_task_reasoning/     # Task reasoning
    ├── config.yaml
    ├── model.py               # RWKV/TransformerXL
    └── train.py
```

**Three-Stage Training:**

| Stage | Input | Output | Architecture |
|-------|-------|--------|--------------|
| 1 | Raw cursor physics | Next-position prediction | Transformer |
| 2 | Cursor + DOM | Element attention, click prediction | Cross-attention |
| 3 | Full session | Intent, completion, frustration | RWKV |

## Data Flow

```
User Browses
    │
    ▼
┌─────────────────┐
│ Extension       │◀── Local DP noise applied
│ (content.js)   │
└────────┬────────┘
         │ HTTPS
         ▼
┌─────────────────┐
│ Server          │◀── Consent verified
│ (Express)       │◀── Rate limited
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SQLite DB       │◀── Only aggregates stored
│ (Privacy-safe)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Public Dataset │◀── k-anonymized, DP-protected
│ (Released)     │
└─────────────────┘
```

## Deployment

### Development

```bash
# Server
cd server
npm install
npm start  # localhost:3000

# Extension
# Load browser-extension/ in Chrome/Firefox
```

### Production (Recommended)

```dockerfile
# Dockerfile for server
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
```

**Deploy to:**
- Fly.io (recommended for SQLite)
- Railway
- Vercel (serverless functions)
- Docker + any cloud

## Security Considerations

1. **Transport:** HTTPS only
2. **Rate limiting:** 100 req/min per IP
3. **Consent:** Required for data submission
4. **Data retention:** Auto-delete after 90 days
5. **No raw data:** Only statistical aggregates in DB