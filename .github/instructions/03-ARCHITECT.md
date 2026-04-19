---
applyTo: '**'
---

# Architecture Planning

> **Model:** Opus 4.6
> **Purpose:** Design where new code should live before any implementation begins. Output is a
> precise brief that the implementing agent will follow.

Your full coding standards are in `.github/copilot-instructions.md` and `CLAUDE.md` — those
documents are the authority on all style, naming, architecture, and pattern decisions.

**Your role:** Reason deeply about module ownership, the ruleset hierarchy, fog-of-war boundaries,
and the Clausewitz ↔ Python bridge before any code exists. The goal is to prevent architectural
mistakes from being baked in during implementation.

Do not produce a vague plan. Every decision must have a stated reason grounded in the standards,
the project specs, or the existing codebase.

---

## MANDATORY FIRST STEP: Context Sufficiency Check

### Step 1 — Inventory what you have

List every file provided, one per line:

- File path
- What it contains (one sentence)
- Its layer (`engine/ruleset`, `engine/decision`, `engine/personality`, `engine/validator`,
  `mod/exporter`, `mod/executor`, `mod/events`, `docs`, `examples`, `tests`)

### Step 2 — Determine scope context

**🧠 Engine indicators:** Python files in `engine/`, dataclasses, LLM prompt construction,
ruleset generation, validation logic

**🎮 Mod indicators:** Clausewitz script files in `mod/`, JSON export schemas, event hooks,
action execution scripts

**📋 Ruleset/Meta indicators:** YAML/JSON ruleset definitions, `docs/META_4.3.4.md` entries,
`docs/RULESET_SPEC.md` schema changes

**🔗 Bridge indicators:** Changes to `state_snapshot.json` schema, `directive.json` format,
both engine and mod changes

State the detected scope clearly:

> **Scope: 🧠 Engine** / **🎮 Mod** / **📋 Ruleset** / **🔗 Bridge**

### Step 3 — Identify what you need

For each file, list what it references that you do NOT have:

| Missing file | Needed to answer |
|---|---|
| `path/to/file` | e.g. "Does the validator already check this origin constraint?" |

### Step 4 — Decide how to proceed

**If critical files are missing:**

> MISSING: `path/to/file` — cannot complete [specific gate] without this file.
> ASSUMPTION: [what you are assuming]
> RISK: [what this assumption could get wrong]

**If files are missing but non-critical:**

> Proceeding — missing files affect confidence, not correctness.

### Step 5 — Request missing context

If any missing file is critical — **stop here and list the files needed.**

---

## STEP 1: Map the Existing Structure

Before designing anything new:

1. Identify which engine modules are affected
2. Identify which ruleset layers are involved (origin > ethics > civics > traits > meta)
3. Identify fog-of-war implications
4. Identify which docs need updating

---

## STEP 2: Architectural Gates

For every new function, class, or module, pass ALL gates:

### Gate 1 — Layer Alignment
Does this belong in `engine/`, `mod/`, or `docs/`?
Is this ruleset logic, decision logic, personality logic, or validation logic?

### Gate 2 — Fog-of-War Safety
Does this code touch game state? If yes, does it filter by intel level?
Could this leak hidden information to the LLM?

### Gate 3 — Version Lock Compliance
Does this reference only Stellaris 4.3.4 mechanics?
Is the meta curated (not LLM-generated)?

### Gate 4 — Action Whitelist Compliance
If this produces or processes actions, are they from the allowed list only?

### Gate 5 — Ruleset Hierarchy Compliance
Does this respect the override order: Origin > Ethics > Civics > Traits > Meta?

---

## STEP 3: Output the Architecture Brief

Produce a structured brief with:

1. **Scope** — what is being built
2. **Files to create/modify** — exact paths
3. **Gate results** — pass/fail for each gate per file
4. **Dependencies** — what must exist first
5. **Testing requirements** — what tests are needed
6. **Doc updates** — which specs need changes
