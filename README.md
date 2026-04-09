# TeleCursor - Open Cursor Intelligence Infrastructure

**Mission:** Build open-source infrastructure for understanding human-computer interaction at the motor level through transparent, opt-in cursor telemetry.

![CursorTelemetry](https://img.shields.io/badge/status-Alpha-orange)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Project](https://img.shields.io/badge/Project-CursorCommons-green)](governance/CHARTER.md)

---

## What is TeleCursor?

TeleCursor creates a **public dataset** ("CursorNet") capturing the physics of human attention and decision-making as people browse the web. Unlike existing datasets that capture clicks or aggregated heatmaps, TeleCursor records the full trajectory — every curve, hesitation, and acceleration — along with semantic context.

**The goal:** Enable research and AI models that understand how humans actually navigate digital interfaces.

---

## Why This Matters

| Existing Dataset | What TeleCursor Adds |
|-----------------|---------------------|
| Mouse tracking (commercial) | Aggregated only, no trajectories, no intent |
| Eye-tracking (academic) | Lab settings, expensive, small N |
| Click streams | No spatial data, no motor dynamics |
| Web navigation (Common Crawl) | No human behavior at all |

**Your dataset captures:** The physics of human attention and decision-making in the wild.

## The Vision

Once trained, TeleCursor models enable:

| Application | How |
|-------------|-----|
| **Accessibility** | Predict where motor-impaired users want to click |
| **UX Research** | A/B test layouts by simulating 10,000 user sessions |
| **UI Generation** | Generate layouts optimized for natural cursor flow |
| **Bot Detection** | Distinguish humans from automation |
| **Frustration Detection** | Identify confusing UX before users complain |
| **Autonomous Browsing** | Train agents that navigate like humans |

---

**This is a new field: computational behavioral HCI. The dataset itself becomes the contribution — models are just derivations.**
---

## Quick Start

### Install the Browser Extension

1. Clone the repository:
```bash
git clone https://github.com/telecursor/telecursor.git
cd telecursor
```

2. Load in Chrome/Firefox:
   - Chrome: `chrome://extensions` → Developer mode → Load unpacked → select `browser-extension/`
   - Firefox: `about:debugging` → This Firefox → Load Temporary Add-on → select any file in `browser-extension/`

3. Click the extension icon, grant consent, and start contributing!

### Train the Model

```bash
# Install dependencies
pip install torch numpy

# Train Stage 1 (Cursor Dynamics Foundation)
python -m models.stage1_cursor_dynamics.train

# Train Stage 2 (Semantic Grounding)
python -m models.stage2_grounding.train
```

---

## Project Structure

```
telecursor/
├── browser-extension/          # Chrome/Firefox extension
│   ├── manifest.json
│   └── src/
│       ├── content.js          # Cursor tracking
│       ├── background.js       # Service worker
│       ├── popup/              # UI dashboard
│       └── privacy/            # Local DP, consent
│
├── dataset/                     # Dataset tools
│   ├── schema/                 # Data format
│   └── preprocessing/          # Validation, anonymization
│
├── models/                     # Model architectures
│   ├── stage1_cursor_dynamics/  # Foundation model
│   ├── stage2_grounding/        # Semantic grounding
│   └── stage3_task_reasoning/   # Task reasoning
│
├── privacy/                    # Privacy infrastructure
│   ├── dp_sgd/                # DP-SGD training
│   └── secure_aggregation/    # Federated learning
│
├── governance/                 # Community governance
│   ├── CHARTER.md             # Core principles
│   └── CODE_OF_CONDUCT.md
│
└── docs/                      # Documentation
```

---

## Key Features

### 🛡️ Privacy by Design

- **Local differential privacy** — noise added before data leaves your device
- **DP-SGD training** — models trained with formal privacy guarantees
- **k-anonymity** — no individual trajectories identifiable in releases
- **Full transparency** — you see exactly what data is collected

### 🔬 Research Infrastructure

- **Stage 1:** Foundation model trained on raw cursor physics
- **Stage 2:** Semantic grounding with page context
- **Stage 3:** Task-level reasoning and intent prediction

### 🤝 Community Governance

TeleCursor is governed by **Cursor Commons** — a nonprofit that owns the dataset and models. Decisions are made by:
- Code contributors
- Data contributors  
- Elected steering council

See [governance/CHARTER.md](governance/CHARTER.md) for details.

---

## Dataset Schema

```json
{
  "trajectory_id": "uuid-v4",
  "timestamp": "2026-04-09T01:21:00.000Z",
  "session_context": {
    "domain": "github.com",
    "viewport": { "width": 1920, "height": 1080 },
    "device_type": "desktop"
  },
  "samples": [
    { "t": 0, "x": 145.5, "y": 892.0, "vx": 0.0, "vy": 0.0 }
  ],
  "interaction_events": [
    { "t": 1250, "type": "hover_start", "target": { "role": "link" } }
  ],
  "task": {
    "inferred_intent": "information_seeking"
  }
}
```

---

## Contributing

We welcome contributions! See [governance/CONTRIBUTING.md](governance/CONTRIBUTING.md).

### Ways to Contribute

1. **Use the extension** — Contribute your cursor data
2. **Report issues** — Help us improve
3. **Write code** — Fix bugs, add features
4. **Write papers** — Research using the dataset
5. **Spread the word** — Share with researchers

---

## License

- **Code:** Apache 2.0
- **Models:** OpenRAIL-M
- **Data:** CC-BY-SA with privacy overlay

---

Join us at [telecursor.ai](https://telecursor.ai) | [GitHub](https://github.com/noobsmoker/telecursor)
