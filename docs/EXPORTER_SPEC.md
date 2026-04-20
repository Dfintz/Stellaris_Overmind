# Stellaris 4.3.4 – State Exporter Specification
The exporter extracts game state from autosave files and outputs **only legal information** to the LLM.

---

## 1. Purpose
- Provide the LLM with **known information only**.
- Respect **fog‑of‑war** and **intel levels**.
- Parse Stellaris autosave files directly (no Clausewitz exporter mod needed).
- Support both player mode (single empire) and AI mode (multiple empires).

---

## 2. Export Method (Autosave Parsing)
The Python engine watches the Stellaris `save games/` directory for new `.sav` files.
Each `.sav` is a ZIP archive containing `gamestate` and `meta` in Clausewitz text format.

The `save_reader.py` module:
1. Detects new saves via file modification time (polls every 2s)
2. Parses the `.sav` ZIP → Clausewitz text → Python dict
3. Identifies the player's country via `gamestate.player[0].country`
4. Extracts empire data (economy, fleets, diplomacy, planets, tech, etc.)
5. Applies fog-of-war filtering based on intel levels
6. Detects triggering events (war, contact, economy thresholds)
7. Outputs a state snapshot dict

No Clausewitz state exporter mod is required — the autosave parser replaces it entirely.

---

## 3. Export Format
JSON-serializable dict containing:

### 3.1 Empire State
- Resources (energy, minerals, food, alloys, CG, influence, unity + monthly net)
- Fleet power and composition (owned fleets only)
- Starbases (upgraded, with modules and buildings)
- Planets (name, class, size, pops, districts, stability, crime, designation)
- Leaders (class, level, traits)
- Naval capacity and empire size

### 3.2 Technology
- Researched technologies (full list)
- Current research queues (physics, society, engineering)
- Tech count

### 3.3 Traditions & Perks
- Completed traditions
- Taken ascension perks

### 3.4 Policies & Edicts
- Active policies (policy → selected option)
- Active edicts

### 3.5 Diplomacy
- Known empires (filtered by intel level)
- Relations, attitudes, treaties
- Active wars (side, war goal, exhaustion)

### 3.6 Intel-Level Filtering
Data about foreign empires is filtered by intel level:
- **None (0)** — name + attitude only
- **Low (10)** — government type, ethics
- **Medium (30)** — fleet power estimate
- **High (60)** — detailed fleet comp, tech level, economy values
- **Full (90)** — everything

### 3.7 Restrictions
Do NOT expose to the LLM:
- Hidden fleets (outside sensor range)
- Unknown systems
- Enemy economy (unless intel ≥ high)
- Crisis spawn info
- Internal Stellaris AI personality flags

---

## 4. AI Mode (Multi-Empire)
In AI mode, the exporter extracts state for each AI country separately:
- Each AI empire gets its own fog-of-war-filtered snapshot
- Player empire is always excluded
- Primitives, enclaves, pirates are skipped
- Fallen Empires optionally excluded

---

## 5. Event Detection
Events are detected by comparing consecutive state snapshots:
- `GAME_START` — first snapshot
- `WAR_DECLARED` / `WAR_ENDED` — war list changes
- `BORDER_CONTACT_NEW_EMPIRE` — new empire in known list
- `COLONY_ESTABLISHED` — new colony
- `ECONOMY_DEFICIT` — resource drops below 0
- `FLEET_LOST` — fleet power drops > 30%
- `TECH_RESEARCHED` — new tech completed
- `HEARTBEAT` — no significant change
