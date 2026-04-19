---
applyTo: '**'
---

# Code Review — Breadth Pass

> **Model:** Sonnet 4.6
> **Purpose:** Find as many concrete, actionable issues as possible through systematic compliance
> checking, fog-of-war verification, and ruleset consistency analysis.

Your full coding standards are in `.github/copilot-instructions.md` and `CLAUDE.md` — those
documents are the authority.

**Rules of engagement:**

- Distinguish between direct observations and inferences
- For every assertion, cite the specific file and code segment
- State confidence: **HIGH** (code evidence), **MEDIUM** (strong inference), **LOW** (assumption)
- Do NOT list strengths — only findings, fixes, and test suggestions
- Do NOT mention items with `# TODO` comments as issues

---

## MANDATORY FIRST STEP: Context Sufficiency Check

### Step 1 — Inventory what you have

- File path, contents (one sentence), layer classification

### Step 2 — Determine scope

> **Scope: 🧠 Engine** / **🎮 Mod** / **📋 Ruleset** / **🔗 Bridge**

### Step 3 — Identify missing files

### Step 4 — Proceed or request

---

## Review Passes

### Pass 1 — Fog-of-War Compliance
For every piece of game state touched:
- Is it filtered by intel level?
- Could it leak hidden information?
- Does the validator catch fog-of-war violations?

**Severity:** CRITICAL if hidden data could reach the LLM.

### Pass 2 — Action Whitelist Compliance
- Are all actions from the allowed list?
- Does the validator reject unknown actions?
- Is the decision format correct (`ACTION` / `TARGET` / `REASON`)?

**Severity:** HIGH if non-whitelisted actions can pass through.

### Pass 3 — Ruleset Hierarchy
- Is the override order correct (Origin > Ethics > Civics > Traits > Meta)?
- Are there conflicting modifiers that aren't resolved?
- Do origin overrides actually override lower layers?

**Severity:** HIGH if hierarchy is broken.

### Pass 4 — Version Lock
- Does any code reference mechanics not in Stellaris 4.3.4?
- Is meta curated (not LLM-generated)?
- Does `GAME_VERSION` match `"4.3.4"` everywhere?

**Severity:** MEDIUM if version mismatch is isolated, HIGH if systemic.

### Pass 5 — Python Quality
- Type annotations complete?
- `from __future__ import annotations` present?
- Error handling appropriate (ValueError, not silent)?
- No circular imports?

**Severity:** LOW to MEDIUM depending on impact.

### Pass 6 — Test Coverage
- Are fog-of-war edge cases tested?
- Are validator rejection paths tested?
- Are all origin types covered in ruleset generation tests?
- Are LLM response parsing edge cases tested?

**Severity:** MEDIUM if untested paths exist.

---

## Output Format

For each finding:

```
### Finding [N]: [Title]
**File:** `path/to/file.py`
**Severity:** CRITICAL / HIGH / MEDIUM / LOW
**Confidence:** HIGH / MEDIUM / LOW
**Evidence:** [exact code segment]
**Issue:** [what is wrong]
**Fix:** [what to do]
```
