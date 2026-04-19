# Stellaris 4.3.4 – State Exporter Specification
The exporter is a Clausewitz mod component that outputs **only legal information** to the LLM.

---

## 1. Purpose
- Provide the LLM with **known information only**.
- Respect **fog‑of‑war** and **intel levels**.
- Emit **event‑driven snapshots** to reduce load.

---

## 2. Export Frequency
Triggered by:
- War declarations
- Border changes
- Fleet detection
- Economy thresholds
- Colonization opportunities
- Diplomatic changes
- Every 90 in‑game days (heartbeat)

---

## 3. Export Format
JSON file containing:

### 3.1 Empire State
- Resources (minerals, alloys, energy, CG, unity)
- Fleet power (known fleets only)
- Starbases (owned)
- Planets (owned)
- Pop count (approximate if intel low)

### 3.2 Diplomacy
- Known empires
- Relations
- Treaties
- Rivalries
- Federations
- Subjects

### 3.3 Military Intel
- Known enemy fleets (sensor range only)
- Known starbases
- Known borders

### 3.4 Restrictions
Do NOT export:
- Hidden fleets
- Unknown systems
- Enemy economy (unless intel high)
- Crisis spawn info
- AI personality flags

---

## 4. File Output
- Overwrite a single JSON file per empire.
- Use deterministic formatting.

---

## 5. Security
Exporter must guarantee:
- No god‑mode information
- No hidden modifiers
- No internal Stellaris AI data
