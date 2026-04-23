# TeleCursor

[![CI/CD](https://github.com/noobsmoker/telecursor/actions/workflows/ci.yml/badge.svg)](https://github.com/noobsmoker/telecursor/actions)
[![Node.js](https://img.shields.io/node/v20.svg)](https://nodejs.org)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/github/license/noobsmoker/telecursor)](LICENSE)

Open infrastructure for cursor behavior research. Dataset and models for understanding human-computer interaction at the motor level.

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Differential Privacy** | ε ≤ 3.0 local DP in browser before transmission |
| **Causal Transformers** | RoPE + SwiGLU architecture for cursor dynamics |
| **Bot Detection** | Automated trajectory filtering with ML classifiers |
| **Manifest V3** | Modern Chrome/Firefox extension |
| **Docker Ready** | One-command deployment with docker-compose |
| **Cursor Glow** | Visual feedback when tracking is active |
| **Open Data** | CC-BY-SA licensed dataset with privacy overlay |

## Overview

TeleCursor collects opt-in cursor telemetry with formal differential privacy guarantees (ε ≤ 3.0) and trains foundation models on human navigation patterns. The system comprises:

- **Browser extension**: Captures cursor trajectories with local privacy enforcement
- **Server**: Receives, validates, and stores anonymized telemetry
- **Dataset**: Curated behavioral data with bot detection and quality filtering
- **Models**: Causal transformers (RoPE, SwiGLU) with physics-informed constraints

All components are open source. Data collection is strictly opt-in. No exclusive commercial rights reserved.

## Documentation

| Doc | Description |
|-----|-------------|
| [📐 Architecture](docs/ARCHITECTURE.md) | System design, components, data flow |
| [🔌 API Reference](docs/API.md) | REST endpoints, schemas, authentication |
| [🔒 Privacy Policy](docs/PRIVACY.md) | Differential privacy guarantees, threat model |
| [🤝 Contributing](docs/CONTRIBUTING.md) | Development setup, code standards, PR process |
| [📋 Data Schema](docs/API.md#data-schemas) | Trajectory, sample, and event structures |

## Repository Structure

```
telecursor/
├── browser-extension/ # Chrome/Firefox extension (Manifest V3)
│ ├── src/
│ │ ├── content.js # Cursor capture and local processing
│ │ ├── background.js # Upload queue and sync
│ │ ├── privacy/ # Local differential privacy implementation
│ │ └── utils/ # Circular buffers, compression
│ └── manifest.json
├── server/ # Node.js API server
│ ├── src/
│ │ ├── index.js # Express server, rate limiting
│ │ ├── db/ # SQLite with WAL mode
│ │ ├── validation/ # JSON Schema, bot detection
│ │ └── privacy/ # Aggregation, k-anonymity
│ └── package.json
├── models/ # PyTorch training pipeline
│ └── stage1_cursor_dynamics/
│ ├── model.py # Causal transformer with RoPE
│ ├── train.py # Training loop with checkpointing
│ ├── dataset.py # Trajectory loader, tokenizer
│ ├── config.yaml # Hyperparameters
│ └── bot_detector.py # Automated trajectory filtering
├── dataset/ # Data processing utilities
│ └── preprocessing/
├── docs/ # Documentation
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── PRIVACY.md
│   └── CONTRIBUTING.md
└── docker-compose.yml # Deployment configuration
```

## Quick Start

### One-Line Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/noobsmoker/telecursor/main/install.sh | bash
```

### Prerequisites

- Node.js 20+
- Python 3.10+
- Chrome 109+ or Firefox 115+

### Server

```bash
cd server
npm install
npm run dev
```

Server runs at `http://localhost:3000` with hot reload.

### Browser Extension

1. Open Chrome → Extensions → Developer mode
2. Load unpacked → Select `browser-extension/`
3. Configure server URL in extension options

### Model Training

```bash
cd models/stage1_cursor_dynamics
pip install -r requirements.txt
python train.py --data-dir /path/to/trajectories --config config.yaml
```

## Privacy Architecture

Local differential privacy (Laplace mechanism, ε=3.0) applied in browser before transmission. Server receives only noisy aggregates. See [docs/PRIVACY.md](docs/PRIVACY.md) for formal guarantees and threat model.

## Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md). Key areas:

- Model architecture (causal transformers, efficient attention)
- Privacy engineering (secure aggregation, k-anonymity)
- Browser extension (Manifest V3, Web Crypto API)
- Data quality (bot detection, validation)

## License

MIT License. See [LICENSE](LICENSE). Data contributions are licensed under CC-BY-SA with privacy overlay.

## Citation

```bibtex
@software{telecursor2025,
 title={TeleCursor: Open Infrastructure for Cursor Behavior Research},
 author={TeleCursor Contributors},
 year={2025},
 url={https://github.com/noobsmoker/telecursor}
}
```

## Contact

- Issues: [GitHub Issues](https://github.com/noobsmoker/telecursor/issues)
- Security: security@telecursor.ai
- Research: research@telecursor.ai