# Privacy Architecture

## Threat Model

| Threat | Mitigation | Verification |
|--------|-----------|--------------|
| Membership inference | DP-SGD training, ε ≤ 3.0 | Privacy accountant |
| Attribute inference | Per-user gradient clipping | Gradient norm monitoring |
| Reconstruction | Local Laplace noise + server aggregation | Sensitivity analysis |
| Linkage attack | k-anonymity (k=5), coarse timestamps | k-anonymity verification |
| Timing correlation | Event-level differential privacy | Interval obfuscation |

## Local Differential Privacy

Applied in browser extension before any network transmission.

### Parameters

| Parameter | Default | Strict | Minimal |
|-----------|---------|--------|---------|
| ε (epsilon) | 3.0 | 1.0 | 8.0 |
| δ (delta) | 10⁻⁵ | 10⁻⁶ | 10⁻⁵ |
| Position noise | ±4px | ±2px | ±8px |
| Velocity noise | ±20px/s | ±10px/s | ±40px/s |

### Mechanisms

**Numeric attributes** (position, velocity, acceleration): Laplace mechanism

```
noise ~ Laplace(0, sensitivity/ε)
```

**Categorical attributes** (button state): Randomized response

```
P(report true value) = e^ε / (e^ε + |domain| - 1)
```

## Server-Side Protections

### Input Validation

- Trajectory length: 10-10,000 samples
- Duration: 5s-10min
- Velocity clamping: 0-5000 px/s
- Rejection of impossible physics (jerk > 100,000 px/s³)

### Storage

- Encryption at rest: AES-256-GCM
- Key rotation: 90 days
- Access logging: All queries logged, 1-year retention

### Aggregation

Public dataset releases meet:
- k-anonymity: k ≥ 5
- ℓ-diversity: ℓ ≥ 2 for sensitive attributes
- t-closeness: t ≤ 0.2 for numerical distributions

## User Rights

| Right | Implementation |
|-------|---------------|
| Access | Export all raw data (JSON download) |
| Deletion | Immediate removal, 30-day backup purge |
| Portability | Standard JSON format |
| Rectification | Not applicable (raw behavioral data) |
| Restriction | Pause collection without deletion |
| Objection | Opt-out of research aggregation |

## Verification

Privacy guarantees are verified through:

1. **Unit tests**: Differential privacy mechanisms (statistical tests on noise distribution)
2. **Integration tests**: End-to-end privacy pipeline
3. **External audit**: Annual third-party privacy audit
4. **Open verification**: All privacy code open source, reproducible analysis

## Contact

Privacy questions: privacy@telecursor.ai 
Security issues: security@telecursor.ai (PGP key available)