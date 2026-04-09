# Privacy & Security

TeleCursor is built on a **privacy-first** principle. We believe that understanding human-computer interaction should not come at the cost of individual privacy.

## Our Privacy Philosophy

1. **Transparency** — You see exactly what we collect
2. **Control** — You can export, delete, or opt-out anytime
3. **Minimization** — We collect only what's necessary
4. **Protection** — Technical guarantees beyond legal promises

## What We Collect

### ✅ What We Capture

| Data | Purpose | Privacy |
|------|---------|---------|
| Cursor position (x, y) | Movement patterns | Local DP noise |
| Velocity (vx, vy) | Speed patterns | Derived from position |
| Timestamps | Timing analysis | Rounded to 10ms |
| DOM tags | Interaction context | Generalized |
| Device type | Platform analysis | Coarse category |
| Viewport size | Layout analysis | Binned |

### ❌ What We Never Capture

- Typed text or form inputs
- Passwords or authentication data
- Personal identifiers (name, email, etc.)
- Full page content or URLs
- Browsing history
- Screen recordings

## Technical Protection Layers

### Layer 1: Local Differential Privacy

Before any data leaves your device, we apply local DP:

```javascript
// Laplace noise added to coordinates
const scale = sensitivity / epsilon;  // epsilon = 3.0
x_noisy = x + Laplace(0, scale);
```

**Privacy guarantee:** Even if the server is compromised, individual points are **plausibly deniable**.

```javascript
// Temporal subsampling
// Each point kept with 70% probability
trajectory = trajectory.filter(() => Math.random() < 0.7);

// Coordinate generalization
x_bucket = Math.floor(x / 100) * 100;  // 100px buckets
```

### Layer 2: Consent Management

We implement **informed consent** at multiple levels:

```javascript
// Granular consent options
{
  global_opt_in: false,
  site_specific: {
    "github.com": true,
    "amazon.com": false
  },
  data_retention: "90_days",
  download_my_data: true
}
```

**Your rights:**
- Grant/revoke consent anytime
- Per-site opt-in/out
- Export all your data (JSON)
- Delete all your data instantly

### Layer 3: Server-Side Processing

On the server, we further process data:

```python
# Domain categorization (no raw domains stored)
"github.com" → "developer"
"amazon.com" → "shopping"

# Path hashing
"/noobsmoker/project" → "sha256:abc123..."

# Aggregation
# Only statistical summaries stored long-term
# Raw samples deleted after 24 hours
```

### Layer 4: k-Anonymity

When releasing the public dataset:

```python
# Ensure each record is indistinguishable from k-1 others
# k >= 5 required for release

# Quasi-identifiers generalized:
# - viewport: binned to 100px
# - device_type: grouped to 3 categories
# - time_of_day: bucketed to 4 periods
```

## Differential Privacy Details

### Formal Guarantees

| Parameter | Value | Meaning |
|-----------|-------|---------|
| ε (epsilon) | 3.0 | Strong privacy |
| δ (delta) | 1e-5 | Failure probability |
| Sensitivity | 10px | Max change |
| Clipping | 1.0 | Per-sample norm |

**What this means:** An adversary with arbitrary side information cannot determine whether any specific user's data is in the dataset with probability > 33%.

### Training with DP-SGD

When training models on cursor data:

```python
# PyTorch + Opacus
from opacus import PrivacyEngine

privacy_engine = PrivacyEngine()
model, optimizer, dataloader = privacy_engine.make_private(
    module=model,
    optimizer=optimizer,
    data_loader=dataloader,
    noise_multiplier=1.1,
    max_grad_norm=1.0
)
```

**Result:** Models trained with (ε ≤ 3.0)-differential privacy.

## Data Retention

| Data Type | Retention | Deletion |
|-----------|-----------|----------|
| Raw samples | 24 hours | Automatic |
| Aggregates | 90 days | Automatic |
| User stats | Until delete | On request |
| Consent state | Until delete | On request |

## Compliance

### GDPR (Europe)
- ✅ Right to access
- ✅ Right to rectification
- ✅ Right to erasure ("right to be forgotten")
- ✅ Data portability
- ✅ Consent basis

### CCPA (California)
- ✅ Right to know
- ✅ Right to delete
- ✅ Right to opt-out

### IRB Considerations
For research use, we recommend:
- Consultation with your institution's IRB
- Use of our DP-trained models (already approved)
- Citation of this privacy documentation

## Security Measures

### Transport
- HTTPS only (TLS 1.3)
- HSTS header
- No HTTP fallback

### Rate Limiting
- 100 requests/minute per IP
- Automatic blocking of abuse

### Database
- SQLite with WAL mode
- Automatic data expiration
- No PII columns

## Auditing

We commit to:
- Annual third-party privacy audit
- Published audit reports
- Transparent incident reporting

---

## Questions?

If you have privacy concerns or need to exercise your rights:

1. **GitHub Issues:** [github.com/noobsmoker/telecursor/issues](https://github.com/noobsmoker/telecursor/issues)
2. **Email:** [contact@telecursor.ai](mailto:contact@telecursor.ai)

We respond within 48 hours.