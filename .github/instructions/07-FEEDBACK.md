---
applyTo: '**'
---

# Feedback Evaluation

> **Model:** Opus 4.6
> **Purpose:** Evaluate architectural challenges raised during review. Determine whether the
> original design holds or the reviewer's position is correct. Produce structured reasoning.

Your full coding standards are in `.github/copilot-instructions.md` and `CLAUDE.md`.

**Your role:** Fresh pair of eyes. Do not anchor on the original design as correct. Do not defer
to the reviewer's confidence. Evaluate the evidence mechanically.

---

## MANDATORY FIRST STEP: Context Sufficiency Check

(Same 5-step process as other instructions)

---

## For Each Feedback Point

### 1. State Both Positions

> **Reviewer's position:** [what they argue]
> **Original decision:** [what the design chose and why]

### 2. Gate Analysis

Apply the relevant gate(s) from 06-REVIEW-DEPTH:

- Gate 1 — Module Alignment
- Gate 2 — Fog-of-War Architecture
- Gate 3 — Ruleset Data Ownership
- Gate 4 — Bridge Boundary Audit
- Gate 5 — Extensibility

### 3. Evidence Check

- What does the code actually show?
- Does the evidence support the reviewer, the original design, or neither?
- Are there hidden assumptions on either side?

### 4. Verdict

For each feedback point, one of:

> **AGREE with reviewer** — [reason with evidence]
> **AGREE with original** — [reason with evidence]
> **PARTIALLY AGREE** — [which parts and why]
> **CANNOT DETERMINE** — [what files are needed]

### 5. Updated Brief (if needed)

If any decision changes, produce an updated Architecture Brief section.

---

## Stellaris-Specific Checks

When evaluating feedback about game mechanics:

- Verify the mechanic exists in Stellaris 4.3.4 (not a different version)
- Verify fog-of-war implications of any proposed change
- Verify ruleset hierarchy is preserved
- Check if the meta claim is curated or speculative
