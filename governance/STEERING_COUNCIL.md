# Steering Council

This document defines the structure, responsibilities, and election process for the TeleCursor Steering Council, as established in the [CHARTER.md](./CHARTER.md).

---

## Overview

The Steering Council is the primary governance body for the TeleCursor project. It ensures alignment with the project's core principles: data sovereignty, privacy by design, transparency, and non-discrimination.

---

## Council Structure

| Seat | Type | Term | Selection Method |
|------|------|------|------------------|
| 1 | Founding Maintainer | Permanent | Appointment |
| 2 | Founding Maintainer | Permanent | Appointment |
| 3 | Code Contributor Representative | 2 years | Election |
| 4 | Code Contributor Representative | 2 years | Election |
| 5 | Data Contributor Representative | 2 years | Election |
| 6 | Data Contributor Representative | 2 years | Election |
| 7 | Ethics/AI Safety Expert | 2 years | Appointment |

### Seat Definitions

**Seats 1-2: Founding Maintainers**
- Reserved for original project founders
- Permanent seats (not subject to re-election)
- Can be revoked only for cause (see removal process below)

**Seats 3-4: Code Contributors**
- Elected by active code contributors
- Must have at least 100 commits in past 12 months
- Two-year terms, staggered (one election per year)

**Seats 5-6: Data Contributors**
- Elected by data contributors (institutions providing trajectory data)
- Must represent an organization with active data contribution
- Two-year terms, staggered (one election per year)

**Seat 7: Ethics/AI Safety Expert**
- Appointed by majority vote of existing council
- Should have demonstrated expertise in:
  - AI safety
  - Privacy-preserving machine learning
  - Data ethics
  - Fairness in ML systems

---

## Responsibilities

### Strategic
- **Model Release Approvals**: Review and approve release of new model versions
- **Privacy Standard Updates**: Update privacy standards as technology evolves
- **Budget Allocation**: Allocate project resources (infrastructure, grants, etc.)
- **Roadmap Planning**: Set project direction and priorities

### Operational
- **Conflict Resolution**: Mediate disputes between contributors or teams
- **Community Representation**: Represent TeleCursor in external forums
- **RFC Review**: Review and decide on RFCs (Request for Comments)

### Prohibited Actions
The council CANNOT:
- Change the project license (requires 2/3 community vote)
- Sell or commercialize contributor data
- Approve surveillance or military applications
- Remove seats without due process

---

## Election Process

### Code Contributor Elections

1. **Nomination** (30 days before election)
   - Self-nomination or nomination by another contributor
   - Must meet eligibility requirements (100+ commits in past year)
   - Submit brief statement of intent

2. **Voting** (14 days)
   - All code contributors with 20+ commits in past 6 months are eligible to vote
   - Single transferable vote (STV) system
   - Anonymous voting via ranked choice

3. **Term Start** (immediately after certification)
   - New member takes seat after results certified
   - Outgoing member serves transition period

### Data Contributor Elections

1. **Nomination** (30 days before election)
   - Organization nominates representative
   - Must have active data contribution agreement

2. **Voting** (14 days)
   - One vote per contributing organization
   - Weighted by data volume (log scale)

3. **Term Start** (immediately after certification)

### Ethics Expert Appointment

- Majority vote of existing council
- 2/3 approval required for first appointment
- No term limit, but annual review required

---

## Meetings

### Regular Meetings
- **Frequency**: Monthly
- **Duration**: 60-90 minutes
- **Attendance**: Open to all community members
- **Minutes**: Published within 48 hours

### Special Meetings
- **Called by**: Any 3 council members or 10% of community
- **Purpose**: Emergency decisions, urgent RFCs

### Decision Quorum
- **Required**: 4 of 7 members (including at least one from each seat type)
- **Voting**: Simple majority unless otherwise specified

---

## Removal Process

### For Cause
Council members may be removed for:
- Violation of code of conduct
- Inactivity (3+ consecutive meetings without notice)
- Misappropriation of project resources
- Actions contrary to project values

### Process
1. **Investigation**: Independent committee reviews allegations
2. **Hearing**: Member has opportunity to respond
3. **Vote**: 5/7 members must approve removal
4. **Appeal**: Community can overturn with 2/3 vote

### Replacement
- **Founding seats**: Appointed by remaining founding member
- **Elected seats**: Special election within 60 days
- **Ethics seat**: Appointed by majority of remaining council

---

## Current Council

*To be populated after first election*

| Seat | Name | Organization | Term Ends |
|------|------|--------------|-----------|
| 1 | TBD | - | - |
| 2 | TBD | - | - |
| 3 | TBD | - | - |
| 4 | TBD | - | - |
| 5 | TBD | - | - |
| 6 | TBD | - | - |
| 7 | TBD | - | - |

---

## Contact

- **Email**: steering@telecursor.org
- **Discussion**: #governance on Discord
- **Documentation**: See [CHARTER.md](./CHARTER.md) for full legal framework

---

## Related Documents

- [CHARTER.md](./CHARTER.md) - Full legal framework
- [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) - Community standards
- [CONTRIBUTING.md](../docs/CONTRIBUTING.md) - How to contribute
- [RFC Process](./RFC.md) - How to propose changes

---

*Last Updated: 2024-01*
*This document is subject to revision per the amendment process in CHARTER.md*