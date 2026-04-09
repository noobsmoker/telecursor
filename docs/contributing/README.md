# Contributing to TeleCursor

Thank you for your interest in contributing to TeleCursor! We welcome contributions from users, developers, researchers, and advocates.

## Ways to Contribute

### 1. Use the Extension & Contribute Data

The simplest way to contribute is to **use the extension** while browsing. Each session contributes to the public dataset.

**How to start:**
1. Load the extension in Chrome/Firefox
2. Open the popup and click to enable tracking
3. Browse normally — your cursor data is now part of CursorNet

**What you get:**
- Dashboard showing your contribution stats
- Ability to export your data
- Right to delete your data anytime

### 2. Report Issues

Found a bug or have a feature request?

1. **Search** existing issues first
2. **Create** a new issue with:
   - Clear title
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details

**Issue Templates:**
- [Bug Report](https://github.com/noobsmoker/telecursor/issues/new?template=bug.md)
- [Feature Request](https://github.com/noobsmoker/telecursor/issues/new?template=feature.md)
- [Privacy Concern](https://github.com/noobsmoker/telecursor/issues/new?template=privacy.md)

### 3. Write Code

We need developers at all levels:

**Quick Wins (Good first issues):**
- Fix typos in documentation
- Add unit tests
- Improve error messages
- UI/UX improvements

**Core Development:**
- Browser extension features
- Server API improvements
- Model architecture changes
- Privacy enhancements

**Process:**
```bash
# 1. Fork the repository
git fork https://github.com/noobsmoker/telecursor

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/telecursor.git
cd telecursor

# 3. Create a feature branch
git checkout -b feature/my-awesome-feature

# 4. Make your changes
# ... write code ...

# 5. Test your changes
npm test  # or specific test commands

# 6. Commit with DCO sign-off
git commit -s -m "Add awesome feature"

# 7. Push and create PR
git push origin feature/my-awesome-feature
# Then open PR on GitHub
```

**Developer Certificate of Origin (DCO):**
By contributing, you agree to the [DCO](https://developercertificate.org/). This is simply signing off that you have the right to contribute.

### 4. Write Documentation

Good documentation is crucial for adoption:

- **Fix typos** — Every typo matters
- **Add examples** — Show, don't just tell
- **Translate** — Help non-English speakers
- **Improve guides** — Make onboarding smoother

### 5. Use the Dataset for Research

Researchers are vital to TeleCursor's mission:

**Getting Access:**
1. Read the [dataset documentation](api/schema/)
2. Review the [privacy policy](privacy/)
3. Cite TeleCursor in your paper

**Suggested Citations:**

*Dataset:*
```
TeleCursor (2026). CursorNet: Open Cursor Telemetry Dataset.
https://github.com/noobsmoker/telecursor
```

*Model:*
```
TeleCursor (2026). CursorDynamics-Base-v1 Model.
https://github.com/noobsmoker/telecursor/releases
```

**Research Areas:**
- Human-computer interaction
- Accessibility tools
- UI/UX optimization
- Bot detection
- User behavior modeling

### 6. Spread the Word

- ⭐ Star the repo
- 🐦 Tweet about it
- 📝 Write a blog post
- 🎤 Give a talk
- 👥 Tell your friends

## Project Structure

```
telecursor/
├── browser-extension/      # Chrome/Firefox extension
│   └── src/
│       ├── content.js      # Cursor tracking
│       ├── background.js   # Service worker
│       └── popup/          # UI
│
├── server/                 # Data collection server
│   └── src/
│       ├── index.js        # Express app
│       ├── db/             # SQLite
│       ├── routes/         # API endpoints
│       └── middleware/     # Auth, rate limiting
│
├── models/                 # ML models
│   ├── stage1_cursor_dynamics/
│   ├── stage2_grounding/
│   └── stage3_task_reasoning/
│
├── docs/                  # Documentation
│   ├── architecture/
│   ├── api/
│   ├── privacy/
│   └── contributing/
│
└── governance/             # Community governance
    └── CHARTER.md
```

## Development Setup

### Prerequisites

- Node.js 18+
- npm 9+
- Git

### Quick Start

```bash
# Clone
git clone https://github.com/noobsmoker/telecursor.git
cd telecursor

# Install server dependencies
cd server && npm install

# Install extension (no deps needed, vanilla JS)

# Run server
npm start

# Load extension in browser
# chrome://extensions → Load unpacked → browser-extension/
```

### Running Tests

```bash
# Server tests (when available)
cd server && npm test

# Linting
npm run lint
```

## Code Style

### JavaScript (Extension)
- Vanilla JS (no frameworks)
- 2-space indentation
- ES6+ features
- JSDoc for documentation

### Node.js (Server)
- ES Modules (`import`/`export`)
- Async/await over callbacks
- meaningful variable names

### Python (Models)
- PEP 8
- Type hints where helpful
- docstrings for functions

## Pull Request Guidelines

1. **One feature per PR** — Keep changes focused
2. **Write tests** — Especially for bug fixes
3. **Update docs** — If changing behavior, update docs
4. **Fill the template** — Provide context in PR description
5. **Be responsive** — Address review comments

### PR Review Process

1. Automated checks run (lint, test)
2. At least one maintainer reviews
3. Address feedback
4. Squash and merge

## Recognition

Contributors are recognized in:
- README.md contributors section
- Release notes
- Community spotlight

## Code of Conduct

We are committed to a welcoming environment. Please read our [Code of Conduct](governance/CODE_OF_CONDUCT.md).

**Key points:**
- Be respectful
- Welcome newcomers
- Accept constructive criticism
- Focus on what's best for the community

---

## Getting Help

- **Discord:** [Join our community](https://discord.gg/telecursor) (coming soon)
- **GitHub Discussions:** [Q&A](https://github.com/noobsmoker/telecursor/discussions)
- **Email:** contact@telecursor.ai

We look forward to building the future of cursor intelligence together!