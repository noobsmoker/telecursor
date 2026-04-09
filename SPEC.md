# TeleCursor - Open Cursor Intelligence Infrastructure

**Mission:** Build open-source infrastructure for understanding human-computer interaction at the motor level through transparent, opt-in cursor telemetry.

**The Vision:** A public dataset ("CursorNet") capturing the physics of human attention and decision-making in the wild — enabling research and models that understand how humans actually navigate the web.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          TELECURSOR                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐ │
│  │  Extension   │───▶│   Dataset    │───▶│  Training Pipeline   │ │
│  │  (Collection)│    │   (Curated)  │    │  (Models)            │ │
│  └──────────────┘    └──────────────┘    └──────────────────────┘ │
│                                                                     │
│  Privacy Layer: DP-SGD, k-anonymity, local noise                   │
│  Governance: Cursor Commons (501c3), steering council              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
telecursor/
├── SPEC.md                          # This file
├── README.md                        # Landing page
│
├── browser-extension/               # Chrome/Firefox extension
│   ├── manifest.json
│   ├── src/
│   │   ├── background.js           # Service worker
│   │   ├── content.js              # Cursor tracking
│   │   ├── popup/                   # User dashboard
│   │   ├── options/                 # Settings
│   │   └── privacy/
│   │       ├── local_dp.js         # Local differential privacy
│   │       └── consent.js          # Consent management
│   └── README.md
│
├── dataset/                         # Dataset schema & tools
│   ├── schema/
│   │   └── trajectory.schema.json  # Data format
│   ├── preprocessing/
│   │   ├── validator.js            # Bot detection
│   │   └── anonymizer.py           # k-anonymity, DP
│   └── README.md
│
├── models/                          # Model architectures
│   ├── stage1_cursor_dynamics/     # Foundation model
│   │   ├── config.yaml
│   │   ├── model.py
│   │   └── train.py
│   ├── stage2_grounding/           # Semantic grounding
│   │   ├── config.yaml
│   │   ├── model.py
│   │   └── train.py
│   └── stage3_task_reasoning/      # Task reasoning
│       ├── config.yaml
│       ├── model.py
│       └── train.py
│
├── privacy/                         # Privacy infrastructure
│   ├── dp_sgd/
│   │   ├── trainer.py              # DP--SGD training
│   │   └── config.py
│   ├── secure_aggregation/
│   │   └── server.py               # Federated learning
│   └── audit/
│       └── report.py               # Privacy auditing
│
├── governance/                      # Community governance
│   ├── CHARTER.md                  # Core principles
│   ├── STEERING_COUNCIL.md
│   ├── CONTRIBUTING.md
│   └── CODE_OF_CONDUCT.md
│
└── docs/
    ├── SPEC.md                     # Full technical spec
    ├── DATASET.md                  # Dataset documentation
    └── ETHICS.md                   # Ethics guidelines
```

---

## Dataset Schema (CursorNet)

### Core Trajectory Record

```json
{
  "trajectory_id": "uuid-v4",
  "timestamp": "2026-04-09T01:21:00.000Z",
  "session_context": {
    "domain": "github.com",
    "page_path": "/features/copilot",
    "viewport": {"width": 1920, "height": 1080},
    "device_type": "desktop",
    "input_method": "mouse"
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
      "pressure": 1.0,
      "button_state": 0
    }
  ],
  "interaction_events": [
    {
      "t": 1250,
      "type": "hover_start",
      "target": {
        "selector": "nav > a[href='/pricing']",
        "tag": "A",
        "role": "link",
        "text_content": "Pricing",
        "bounding_box": {"x": 120, "y": 45, "w": 60, "h": 24}
      }
    }
  ],
  "task": {
    "stated_goal": "compare pricing plans",
    "inferred_intent": "information_seeking",
    "completion_status": "success"
  },
  "anonymization": {
    "ip_hash": "sha256-truncated",
    "geographic_region": "US-West",
    "personal_data_scrubbed": true
  }
}
```

---

## Training Stages

### Stage 1: Cursor Dynamics Foundation Model
- **Architecture:** Transformer over cursor trajectories
- **Objective:** Next-position prediction (like language modeling)
- **Context:** 20,048 samples (~40 seconds at 50Hz)
- **Output:** Distribution over next position

### Stage 2: Semantic Grounding
- **Input:** Cursor trajectories + DOM structure
- **Output:** Element attention, click prediction, intent classification
- **Fusion:** Cross-attention between cursor and page

### Stage 3: Task-Level Reasoning
- **Input:** Full session history
- **Output:** Intent, task completion, frustration detection
- **Architecture:** RWKV or Mamba (sub-quadratic for long sequences)

---

## Privacy Guarantees

| Threat | Mitigation |
|--------|------------|
| Membership inference | DP-SGD training (ε ≤ 3.0) |
| Attribute inference | Per-user gradient clipping |
| Reconstruction | Local DP noise + k-anonymity |
| Linkage | k-anonymity in release (k≥5) |

---

## Governance: Cursor Commons

- **Type:** 501(c)(3) or equivalent nonprofit
- **Steering Council:** 7 seats (2 founders, 2 code, 2 data, 1 ethics)
- **Core Principles:** Data sovereignty, no commercial exclusivity, privacy by design, transparency, non-discrimination

---

## Key Hyperparameters

### Stage 1 (Foundation)
- `d_model`: 768
- `n_layers`: 12
- `n_heads`: 12
- `context_window`: 20,048
- `lr`: 3e-4
- `batch_size`: 512 (global)
- `precision`: bf16-mixed

### Stage 2 (Grounding)
- `lr`: 1e-4 (fine-tuning)
- Unfreeze encoder at step 100,000

### Stage 3 (Reasoning)
- `d_model`: 1024
- `n_layers`: 24
- RL fine-tuning with PPO

---

## Success Metrics

- [ ] Browser extension deployed with 100+ beta users
- [ ] 1000+ hours of validated cursor trajectories
- [ ] Stage 1 model trained and released
- [ ] First public dataset release (DP-protected)
- [ ] Governance structure established
- [ ] Research paper published

---

## Why This Matters

| Existing Dataset | What TeleCursor Adds |
|-----------------|---------------------|
| Mouse tracking (commercial) | No trajectories, no intent |
| Eye-tracking (academic) | Lab settings, expensive, small N |
| Click streams | No spatial data, no motor dynamics |
| Web navigation (Common Crawl) | No human behavior at all |

**Your dataset captures:** The physics of human attention and decision-making in the wild — enabling accessibility tools, UX research, UI generation, bot detection, and autonomous browsing agents trained on actual human behavior.
