# Contributing to TeleCursor

## Development Setup

```bash
# One-line install (Recommended)
curl -fsSL https://raw.githubusercontent.com/noobsmoker/telecursor/main/install.sh | bash

# Manual setup
git clone https://github.com/noobsmoker/telecursor.git
cd telecursor

# Server
cd server
npm install
cp .env.example .env
npm run dev

# Extension
cd ../browser-extension
# Load unpacked in Chrome developer mode

# Models
cd ../models/stage1_cursor_dynamics
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Contribution Areas

### High Priority

| Area | Skills | Issues |
|------|--------|--------|
| Model architecture | PyTorch, transformers, CUDA | #model-help |
| Privacy engineering | Differential privacy, cryptography | #privacy |
| Data quality | Statistics, anomaly detection | #data-quality |
| Browser extension | JavaScript, Web Crypto, Manifest V3 | #extension |

### Medium Priority

- Documentation and tutorials
- Performance optimization
- Testing infrastructure
- Deployment automation

## Pull Request Process

1. **Issue first**: Create or claim an issue
2. **Branch**: `git checkout -b feature/description`
3. **Commits**: Conventional commits (`feat:`, `fix:`, `docs:`, `privacy:`)
4. **Tests**: Include unit tests for new code
5. **Privacy**: If handling data, include privacy impact statement
6. **PR template**: Fill out all sections

### PR Checklist

- [ ] Code follows style guide (ESLint, Black, rustfmt)
- [ ] Tests pass (`npm test`, `pytest`)
- [ ] Privacy review (if applicable)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated

## Code Standards

### JavaScript (Extension)

- ES2022+, async/await preferred
- Web Crypto API for all randomness
- No `console.log` in production (use debug utility)
- Strict mode enabled

### Python (Models)

- Type hints required
- Black formatting (88 char line length)
- Docstrings: Google style
- Tests: pytest with 80% coverage target

### Privacy Requirements

All contributions handling user data must:

1. Apply differential privacy before transmission
2. Validate all inputs (JSON Schema)
3. Log access (no raw data in logs)
4. Include privacy test demonstrating ε budget

## Review Process

| Change Type | Required Reviews |
|-------------|------------------|
| Documentation | 1 |
| Bug fix | 1 + tests |
| Feature | 2 |
| Privacy-related | 2 + privacy team |
| Security | 2 + security review |

## Communication

- **Discord**: [invite link]
- **GitHub Discussions**: Architecture questions
- **GitHub Issues**: Bug reports, feature requests
- **Email**: security@telecursor.ai (security issues only)

## Recognition

Contributors are recognized in:

- README.md contributors section
- Release notes
- Annual report

Significant contributions (maintainer-level) are invited to the steering council.