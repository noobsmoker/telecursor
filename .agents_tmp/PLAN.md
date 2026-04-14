# TeleCursor Comprehensive Implementation Plan

**Generated:** 2026-04-14

This plan provides a comprehensive roadmap to complete the TeleCursor project infrastructure, addressing all gaps identified between the current codebase and the vision outlined in SPEC.md.

---

## 1. OBJECTIVE

Complete the TeleCursor infrastructure by implementing missing components, expanding coverage, and aligning the codebase with the architectural vision defined in SPEC.md. The project aims to build open-source infrastructure for cursor behavior research with differential privacy guarantees, a three-stage model pipeline, and proper governance.

---

## 2. CONTEXT SUMMARY

### Current State

| Component | Status | Details |
|-----------|--------|---------|
| Browser Extension | ✅ Complete | Manifest V3 with local DP, consent management |
| Server API | ✅ Complete | Express server with rate limiting, consent middleware, ClickHouse |
| Stage 1 Model | ✅ Complete | RoPE + SwiGLU causal transformer, physics constraints |
| Privacy Framework | ⚠️ Partial | Laplace/Gaussian mechanisms, federated learning skeleton |
| Monitoring | ⚠️ Config Only | Prometheus/Grafana configs exist, not integrated |
| Governance | ⚠️ Partial | Charter exists, missing steering council docs |
| Tests | ⚠️ Sparse | Only model tests exist (test_model.py, test_bot_detector.py) |

### Gaps vs SPEC.md

The SPEC.md defines a three-stage model pipeline with supporting infrastructure:

- **Stage 2 (Semantic Grounding)** - NOT IMPLEMENTED
- **Stage 3 (Task Reasoning)** - NOT IMPLEMENTED  
- **dataset/schema/** - Directory missing
- **privacy/dp_sgd/** - Directory missing  
- **privacy/secure_aggregation/** - Just a skeleton in federated_learning.py
- **privacy/audit/** - Directory missing
- **STEERING_COUNCIL.md** - Missing
- **CODE_OF_CONDUCT.md** - Missing
- **requirements.txt** - Missing (no centralized dependencies)

### Technical Stack

- **Frontend Extension:** JavaScript (Manifest V3), local DP
- **Server:** Node.js/Express, ClickHouse, rate limiting
- **Models:** PyTorch, RoPE, SwiGLU, FlashAttention
- **Privacy:** Laplace/Gaussian mechanisms, federated learning
- **Infrastructure:** Docker, Prometheus, Grafana

---

## 3. APPROACH OVERVIEW

This plan follows a **layered implementation strategy** organized by subsystem priority:

1. **Foundation First:** Create missing directories, schemas, and dependencies
2. **Model Pipeline:** Implement Stage 2 and Stage 3 models to complete the spec
3. **Privacy Infrastructure:** Build DP-SGD trainer and audit modules
4. **Testing & Quality:** Expand test coverage across all components
5. **Governance:** Complete missing governance documentation
6. **Production:** Docker optimization and CI/CD

This approach ensures dependencies are satisfied before dependent components, reducing refactoring overhead.

---

## 4. IMPLEMENTATION STEPS

### Phase 1: Foundation & Schema

#### Step 1.1: Create Centralized Dependencies
- **Goal:** Establish a unified dependency management system
- **Method:** Create `requirements.txt` for Python and ensure `package.json` covers all Node.js deps
- **Reference:** `server/package.json`, existing Python imports

#### Step 1.2: Create Dataset Schema
- **Goal:** Define formal JSON schema for CursorNet trajectories
- **Method:** Create `dataset/schema/trajectory.schema.json` matching SPEC.md structure
- **Reference:** SPEC.md lines 94-145, existing trajectory structure

#### Step 1.3: Create Dataset Preprocessing Modules
- **Goal:** Implement data validation and anonymization
- **Method:** Create `dataset/preprocessing/validator.js` and `dataset/preprocessing/anonymizer.py`
- **Reference:** Existing `dataset/preprocessing/bot_detector.py`

---

### Phase 2: Model Pipeline (Stage 2 & 3)

#### Step 2.1: Implement Stage 2 - Semantic Grounding Model
- **Goal:** Build model that fuses cursor trajectories with DOM structure
- **Method:** Create `models/stage2_grounding/model.py` with cross-attention between cursor and page embeddings
- **Reference:** SPEC.md lines 157-160, Stage 1 model architecture

#### Step 2.2: Implement Stage 2 Training Pipeline
- **Goal:** Create training loop for semantic grounding
- **Method:** Create `models/stage2_grounding/train.py` with element attention and click prediction heads
- **Reference:** `models/stage1_cursor_dynamics/train.py`

#### Step 2.3: Implement Stage 2 Config
- **Goal:** Define hyperparameters for Stage 2
- **Method:** Create `models/stage2_grounding/config.yaml` with fine-tuning schedule (unfreeze at step 100,000)
- **Reference:** SPEC.md lines 199-201

#### Step 2.4: Implement Stage 3 - Task Reasoning Model
- **Goal:** Build model for session-level intent and task completion prediction
- **Method:** Create `models/stage3_task_reasoning/model.py` using sub-quadratic architecture (Mamba/RWKV)
- **Reference:** SPEC.md lines 162-166

#### Step 2.5: Implement Stage 3 Training Pipeline
- **Goal:** Create training loop with RL fine-tuning
- **Method:** Create `models/stage3_task_reasoning/train.py` with PPO for task reasoning
- **Reference:** SPEC.md lines 203-206

#### Step 2.6: Implement Stage 3 Config
- **Goal:** Define hyperparameters for Stage 3
- **Method:** Create `models/stage3_task_reasoning/config.yaml` with d_model=1024, n_layers=24
- **Reference:** SPEC.md lines 203-206

---

### Phase 3: Privacy Infrastructure

#### Step 3.1: Implement DP-SGD Trainer
- **Goal:** Enable differential privacy in model training
- **Method:** Create `privacy/dp_sgd/trainer.py` with gradient clipping and noise addition
- **Reference:** SPEC.md line 171-176, existing privacy_framework.py

#### Step 3.2: Implement DP-SGD Config
- **Goal:** Define DP-SGD hyperparameters
- **Method:** Create `privacy/dp_sgd/config.py` with epsilon, delta, max_grad_norm settings
- **Reference:** config.yaml privacy section

#### Step 3.3: Implement Secure Aggregation
- **Goal:** Complete federated learning server implementation
- **Method:** Enhance `privacy/federated/federated_learning.py` with secure aggregation protocol
- **Reference:** SPEC.md line 75, existing federated_learning.py

#### Step 3.4: Implement Privacy Audit Module
- **Goal:** Create tools for privacy budget tracking and auditing
- **Method:** Create `privacy/audit/report.py` with epsilon tracking, attack simulation
- **Reference:** SPEC.md line 77

---

### Phase 4: Testing & Quality Assurance

#### Step 4.1: Expand Server Tests
- **Goal:** Test API endpoints, middleware, database operations
- **Method:** Create `tests/test_server.js` with integration tests for trajectories, stats routes
- **Reference:** `server/src/index.js`, routes

#### Step 4.2: Expand Privacy Tests
- **Goal:** Test privacy mechanisms and DP guarantees
- **Method:** Create `tests/test_privacy.py` for Laplace, Gaussian, and composition
- **Reference:** `privacy/modular/privacy_framework.py`

#### Step 4.3: Expand Extension Tests
- **Goal:** Test cursor tracking, local DP, consent management
- **Method:** Create `tests/test_extension.js` with unit tests for content.js components
- **Reference:** `browser-extension/src/content.js`

#### Step 4.4: Add Integration Tests
- **Goal:** Test end-to-end data flow
- **Method:** Create `tests/test_integration.py` covering extension → server → model pipeline
- **Reference:** Full system integration

#### Step 4.5: Add Bot Detector Tests
- **Goal:** Expand test coverage for trajectory filtering
- **Method:** Enhance `tests/test_bot_detector.py` with more edge cases
- **Reference:** Existing test_bot_detector.py

---

### Phase 5: Governance Documentation

#### Step 5.1: Create Steering Council Document
- **Goal:** Define council structure and election process
- **Method:** Create `governance/STEERING_COUNCIL.md` with 7-seat structure per Charter
- **Reference:** `governance/CHARTER.md` lines 43-58

#### Step 5.2: Create Code of Conduct
- **Goal:** Establish community standards
- **Method:** Create `governance/CODE_OF_CONDUCT.md` based on Contributor Covenant
- **Reference:** Charter Article V

---

### Phase 6: Production Readiness

#### Step 6.1: Optimize Docker Configuration
- **Goal:** Improve production Docker setup
- **Method:** Update `server/Dockerfile` with multi-stage build, non-root user, health checks
- **Reference:** Existing server/Dockerfile

#### Step 6.2: Add Health Check Integration
- **Goal:** Connect monitoring to server health endpoints
- **Method:** Update `monitoring/prometheus/prometheus.yml` to scrape server metrics
- **Reference:** SPEC.md success metrics

#### Step 6.3: Create CI/CD Workflow
- **Goal:** Automate testing and deployment
- **Method:** Create `.github/workflows/ci.yml` with test, lint, build stages
- **Reference:** README.md CI badge

---

## 5. TESTING AND VALIDATION

### Success Criteria per Phase

| Phase | Validation | Expected Outcome |
|-------|------------|------------------|
| 1 | Schema validates sample trajectory | JSON schema valid, sample data passes |
| 2 | Stage 2/3 models train without error | Loss converges, metrics logged |
| 3 | DP-SGD maintains ε ≤ 3.0 | Privacy budget tracked accurately |
| 4 | All test suites pass (≥80% coverage) | Green CI pipeline |
| 5 | Governance docs reviewed | Steering council document published |
| 6 | Docker image builds, server responds | Health checks pass |

### Test Coverage Targets

- **Models:** ≥90% (existing tests + Stage 2/3 tests)
- **Server:** ≥80% (routes, middleware, DB)
- **Privacy:** ≥85% (mechanisms, DP guarantees)
- **Extension:** ≥70% (core tracking, DP)

### Validation Commands

```bash
# Run all Python tests
cd models/stage1_cursor_dynamics && python -m pytest ../../tests/ -v

# Run Node.js tests  
cd server && npm test

# Build Docker
docker build -t telecursor/server:latest ./server

# Validate schema
node -e "const schema = require('./dataset/schema/trajectory.schema.json'); console.log('Valid')"
```
