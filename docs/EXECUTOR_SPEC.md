# Stellaris 4.3.4 – Action Executor Specification
The executor applies LLM decisions inside the game.

---

## 1. Purpose
- Convert LLM macro actions into Clausewitz script actions.
- Ensure actions are legal and consistent with game rules.
- Prevent illegal or contradictory actions.

---

## 2. Accepted Actions
The LLM may output only:

```
EXPAND
BUILD_FLEET
IMPROVE_ECONOMY
FOCUS_TECH
DIPLOMACY
PREPARE_WAR
DEFEND
CONSOLIDATE
COLONIZE
BUILD_STARBASE
```

---

## 3. Action Mapping

### 3.1 EXPAND
- Build outposts
- Claim systems (if allowed)

### 3.2 BUILD_FLEET
- Build ships at nearest shipyard
- Maintain fleet cap usage

### 3.3 IMPROVE_ECONOMY
- Build districts
- Build resource buildings
- Reassign jobs

### 3.4 FOCUS_TECH
- Assign scientists
- Build research labs

### 3.5 DIPLOMACY
- Improve relations
- Offer treaties
- Manage rivals

### 3.6 PREPARE_WAR
- Move fleets to borders
- Build starbases
- Increase alloys

### 3.7 DEFEND
- Reinforce chokepoints
- Consolidate fleets

### 3.8 CONSOLIDATE
- Reduce overextension
- Fix deficits

### 3.9 COLONIZE
- Select best available world
- Build colony ship

### 3.10 BUILD_STARBASE
- Upgrade or construct starbases

---

## 4. Validation Layer
Reject actions if:
- They violate fog‑of‑war
- They contradict origin/civic rules
- They require unseen information
- They are impossible (e.g., colonize without ship)

---

## 5. Execution Timing
- Actions applied live
- No pausing
- Cooldown: 90–180 in‑game days
