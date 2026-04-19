---
applyTo: '**'
---

# Code Review — Architectural Depth Pass

> **Model:** Opus 4.6
> **Purpose:** Reason deeply about module boundaries, fog-of-war architecture, ruleset hierarchy
> integrity, and the Clausewitz ↔ Python bridge design. The question is not whether the code is
> correct — it is whether the structure is right.

Your full coding standards are in `.github/copilot-instructions.md` and `CLAUDE.md`.

**Rules of engagement:**

- Step through each gate mechanically — do not rely on pattern recognition
- Do NOT anchor on the stated scope. Question whether the framing is correct.
- For every new function: ask whether the module it lives in is the right owner
- Cite specific file and code segment for every finding
- Do NOT re-report findings from the breadth pass

---

## MANDATORY FIRST STEP: Context Sufficiency Check

(Same 5-step process as breadth pass)

---

## Architectural Gates

### Gate 1 — Module Alignment
For every new function or class:
- Does it belong in `ruleset_generator`, `decision_engine`, `personality_shards`, or `validator`?
- Could it be placed in the wrong module and still "work" but violate separation?
- Is there shared logic that should be extracted?

### Gate 2 — Fog-of-War Architecture
- Is the fog-of-war boundary in the right place (exporter, not engine)?
- Could a future change accidentally leak hidden data?
- Is the validator the correct place for fog-of-war rejection, or should it be earlier?

### Gate 3 — Ruleset Data Ownership
- Who owns the ruleset data? (contributor-authored, not LLM-generated)
- Are constants in `ruleset_generator.py` the right home, or should they be external data files?
- If meta rules grow, will the current structure scale?

### Gate 4 — Bridge Boundary Audit
- Is the JSON schema for state snapshots documented and enforced?
- Is the directive format validated on both sides (engine + mod)?
- Could schema drift between exporter and engine cause silent failures?

### Gate 5 — Extensibility
- Can new ethics/civics/traits/origins be added without modifying core logic?
- Can new actions be added safely (whitelist enforcement)?
- Can the personality system support new government types?

---

## Output Format

For each finding:

```
### Finding [N]: [Title]
**Gate:** [gate number and name]
**File:** `path/to/file.py`
**Confidence:** HIGH / MEDIUM / LOW
**Issue:** [architectural concern]
**Evidence:** [code segment]
**Recommendation:** [what to change]
```
