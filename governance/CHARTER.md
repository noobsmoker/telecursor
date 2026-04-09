# CURSOR COMMONS CHARTER (v1.0)

## Article I: Purpose

Cursor Commons exists to create open, ethical, privacy-preserving infrastructure for understanding human-computer interaction. All outputs serve public interest: accessibility, UX research, and human-centered AI.

## Article II: Core Principles

These principles require **90% supermajority** of all contributor classes to amend:

### 1. Data Sovereignty

- Contributors retain ownership of their raw data
- License to Cursor Commons is revocable at any time
- Users can export or delete their data

### 2. No Commercial Exclusivity

- No party may obtain exclusive rights to models or data
- All releases are open access
- No closed-source derivatives

### 3. Privacy by Design

- All published data meets differential privacy standards (ε ≤ 8.0 minimum, ε ≤ 3.0 default)
- Individual trajectories never published raw
- Regular privacy audits required

### 4. Transparency

- All training code, model weights, and dataset metadata are public
- No black boxes — every component is auditable
- Full documentation of data collection practices

### 5. Non-Discrimination

- Models must not be used for surveillance
- No worker monitoring without explicit consent
- No predictive policing or discriminatory applications

## Article III: Governance Structure

```
┌─────────────────────────────────────────────────────────────┐
│ STEERING COUNCIL (7 seats)                                 │
├─────────────────────────────────────────────────────────────┤
│ • 2 seats: Founding maintainers                             │
│ • 2 seats: Elected by code contributors                     │
│ • 2 seats: Elected by data contributors                     │
│ • 1 seat: External ethics/AI safety expert                   │
│                                                             │
│ Responsibilities:                                            │
│ • Model release approvals                                   │
│ • Privacy standard updates                                  │
│ • Budget allocation                                          │
│ • Conflict resolution                                        │
│ • Cannot: change license, sell data                          │
└─────────────────────────────────────────────────────────────┘
```

## Article IV: Contributor Classes

### Code Contributors

- Anyone who submits PRs merged into main repositories
- Voting power: weighted by recent contribution quality
- Elect representatives to steering council

### Data Contributors

- Users who contribute cursor telemetry via extension
- Voting power: proportional to validated contribution hours
- Retain ownership until contribution

### Researchers & Academics

- Partner institutions get advisory input
- Access to early datasets for research

## Article V: Decision Making

| Decision Type | Threshold | Quorum |
|--------------|-----------|--------|
| Technical changes | 50% | 3 voters |
| Policy updates | 66% | 5 voters |
| Charter amendments | 90% | All classes |
| Emergency suspension | 4/7 | Council vote |

## Article VI: Funding & Sustainability

- **Grants:** Primary revenue from foundations (NSF, Sloan, Mozilla)
- **Compute sponsors:** Cloud credits with no exclusivity
- **Services:** Cost-recovery API for non-commercial researchers
- **Corporate memberships:** Limited to 3, no steering council seats

**Transparency:** All finances published quarterly.

## Article VII: Intellectual Property

- **Code:** Apache 2.0
- **Models:** OpenRAIL-M (Responsible AI License)
- **Data:** CC-BY-SA with privacy overlay
- **Research:** Open access publication required

## Article VIII: Ethics Enforcement

The Ethics Committee can:
- Issue warnings
- Publicly censure violations
- Revoke license for model/data access
- Escalate to legal action for Charter violations

## Article IX: Amendments

This charter can be amended by:
1. Proposal by any contributor
2. 30-day public discussion period
3. 90% supermajority vote across all contributor classes
4. Signature by steering council

---

*Adopted: [Date]*
*Last amended: [Date]*
