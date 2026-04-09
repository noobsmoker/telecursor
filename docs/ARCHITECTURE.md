# System Architecture

## Data Flow

```
┌─────────────────┐ ┌──────────────────┐ ┌─────────────────┐
│ Browser │ │ Server │ │ Training │
│ Extension │────▶│ API │────▶│ Pipeline │
│ │ │ │ │ │
│ • Capture │ │ • Validation │ │ • Bot detection │
│ • Local DP │ │ • Deduplication │ │ • Tokenization │
│ • Compression │ │ • Storage │ │ • Training │
└─────────────────┘ └──────────────────┘ └─────────────────┘
```

## Browser Extension

### Cursor Capture (`content.js`)

- **Sampling rate**: 50Hz (configurable, 20-100Hz)
- **Buffer**: Circular buffer, O(1) insertion
- **Velocity**: Moving average over 5 samples
- **Privacy**: Laplace noise (scale=2/ε) applied locally

### Background Processing (`background.js`)

- **Queue**: In-memory with IndexedDB backup
- **Batching**: 10 trajectories or 60 seconds
- **Retry**: Exponential backoff, 3 attempts
- **Encryption**: TLS 1.3 for transport

## Server

### API Endpoints

| Endpoint | Method | Description | Rate Limit |
|----------|--------|-------------|------------|
| `/api/v1/trajectories` | POST | Submit trajectory batch | 100/min |
| `/api/v1/health` | GET | Health check | None |
| `/api/v1/stats` | GET | Dataset statistics | 10/min |
| `/metrics` | GET | Prometheus metrics | Internal |

### Database Schema

```sql
-- Trajectories table
CREATE TABLE trajectories (
 id TEXT PRIMARY KEY,
 created_at INTEGER NOT NULL,
 domain TEXT,
 page_path TEXT,
 duration_ms INTEGER,
 sample_count INTEGER,
 bot_score REAL,
 privacy_epsilon REAL,
 data BLOB -- Compressed JSON
);

-- Indexes for query performance
CREATE INDEX idx_trajectories_domain ON trajectories(domain);
CREATE INDEX idx_trajectories_created ON trajectories(created_at);
CREATE INDEX idx_trajectories_bot ON trajectories(bot_score) 
 WHERE bot_score < 0.7;
```

## Model Architecture

### Stage 1: Cursor Dynamics

**Input**: Tokenized trajectory `[seq_len, 11]`

- x, y: 1024 bins each (viewport quantized)
- vx, vy: 512 bins each (log-scaled velocity)
- ax, ay: 256 bins each (acceleration)
- Signs: 2 bins each (direction)
- Button: 8 bins (bitmask)

**Architecture**:

| Component | Specification |
|-----------|---------------|
| Embedding | 7 × 96 = 672 → 768 (projection) |
| Positional | RoPE (rotary), base=10000 |
| Attention | Causal masking, 12 heads |
| FFN | SwiGLU, 4× expansion |
| Layers | 12 |
| Parameters | ~75M |

**Training**:

- Objective: Next-position prediction (cross-entropy)
- Physics loss: Velocity/acceleration/jerk constraints
- Gradient checkpointing: Enabled for sequences >1024
- Mixed precision: bfloat16

### Stage 2: Semantic Grounding (Planned)

Graph transformer over DOM structure with cross-attention to cursor state.

## Privacy Implementation

### Local Differential Privacy (Browser)

```javascript
// Laplace mechanism
function addNoise(value, sensitivity, epsilon) {
 const scale = sensitivity / epsilon;
 const u = secureRandom() - 0.5;
 return value + (-scale * Math.sign(u) * Math.log(1 - 2 * Math.abs(u)));
}
```

- **ε**: 3.0 (default), 1.0 (strict mode), 8.0 (minimal)
- **Sensitivity**: Position=2px, Velocity=10px/s, Acceleration=100px/s²
- **Mechanism**: Laplace for numeric, randomized response for categorical

### Server-Side Aggregation

- **k-anonymity**: k=5 for public releases
- **Differential privacy**: Gaussian mechanism (σ=1.0) on gradients during federated learning
- **Retention**: 90 days raw, indefinite for anonymized aggregates

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Capture latency | <5ms | ~2ms |
| Upload batch | <2s | ~800ms |
| Training step | <500ms | ~350ms |
| Inference | <50ms | ~30ms |
| Memory (extension) | <50MB | ~35MB |
| Memory (training) | <16GB | ~12GB |