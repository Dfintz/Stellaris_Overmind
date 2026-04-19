# Stellaris 4.3.4 Domain Knowledge

> **Use when:** You need to verify game mechanics, understand empire design, or validate
> that code references real Stellaris 4.3.4 features. This skill provides curated domain
> knowledge so the LLM does not hallucinate game mechanics.

---

## Ethics (Stellaris 4.3.4)

### Standard Ethics (can be Fanatic)
- **Militarist / Fanatic Militarist** — war, fleet power, claims cost reduction
- **Pacifist / Fanatic Pacifist** — stability, admin cap, diplomatic weight
- **Xenophile / Fanatic Xenophile** — diplomacy, trade, envoys
- **Xenophobe / Fanatic Xenophobe** — border friction, pop growth, closed borders
- **Materialist / Fanatic Materialist** — research, robot assembly
- **Spiritualist / Fanatic Spiritualist** — unity, temples, robot restriction
- **Egalitarian / Fanatic Egalitarian** — consumer goods, factions, specialists
- **Authoritarian / Fanatic Authoritarian** — slavery, influence, worker output

### Gestalt Ethics
- **Gestalt Consciousness** (Hive Mind)
- **Machine Intelligence**

---

## Government Types

| Type | Decision Structure | Leader Influence |
|------|-------------------|-----------------|
| Imperial | Ruler dominant | 80% ruler weight |
| Democracy | Elected leader, faction influence | ~20% ruler, spread across voices |
| Oligarchy | Council of elites | ~40% ruler, 2-4 strong voices |
| Dictatorial | Single ruler, no election | 70% ruler weight |
| Hive Mind | Unified consciousness | Single voice |
| Machine Intelligence | Logic modules | Optimization-based |

---

## Origins (Common, 4.3.4)

| Origin | Key Mechanic |
|--------|-------------|
| Prosperous Unification | Standard start, extra resources |
| Void Dwellers | Start on habitats, planet habitability penalty |
| Shattered Ring | Start on ringworld segment, boosted research |
| Life-Seeded | Start on Gaia world (size 25), can't colonize non-Gaia early |
| Necrophage | Convert prepatent pops, unique growth |
| Scion | Fallen Empire patron, gifted fleet |
| Synthetic Fertility | Synth assembly from start |
| Hegemon | Start leading a federation |
| Common Ground | Start in a federation |
| Doomsday | Homeworld explodes, must relocate |
| Clone Army | Clone pops, growth cap |

---

## Resource Types

- **Energy Credits** — maintenance, trade
- **Minerals** — buildings, districts, ships
- **Food** — pop growth, trade
- **Alloys** — ships, starbases, megastructures
- **Consumer Goods** — research, unity, specialists
- **Influence** — claims, edicts, expansion
- **Unity** — traditions, ambitions

### Strategic Resources
- Volatile Motes, Exotic Gases, Rare Crystals, Zro, Dark Matter, Living Metal, Nanites

---

## Ship Classes (4.3.4)

| Class | Role | Unlock |
|-------|------|--------|
| Corvette | Evasion screen | Start |
| Destroyer | Point defense, screen | Early tech |
| Cruiser | Balanced, carrier option | Mid tech |
| Battleship | Heavy damage, artillery | Mid-late tech |
| Titan | Fleet buff, perdition beam | Late tech |
| Colossus | Planet killer / shield | Ascension perk |
| Juggernaut | Mobile starbase | Late tech + perk |

---

## Allowed AI Actions → Game Mapping

| Action | Game Equivalent |
|--------|----------------|
| EXPAND | Build outposts, claim systems |
| BUILD_FLEET | Queue ships at shipyards |
| IMPROVE_ECONOMY | Build districts/buildings, reassign jobs |
| FOCUS_TECH | Adjust research priority |
| DIPLOMACY | Send proposals (NAP, trade, federation) |
| PREPARE_WAR | Fabricate claims, shift to alloys |
| DEFEND | Rally fleets, build defensive starbases |
| CONSOLIDATE | Fix deficits, reduce overextension |
| COLONIZE | Send colony ship |
| BUILD_STARBASE | Upgrade/construct starbases |

---

## Version-Specific Notes (4.3.4)

- Pop growth is logarithmic (S-curve with empire size)
- Starbase cap matters for chokepoint strategy
- Administrative capacity affects research/unity penalties
- Fleet composition counters are real (e.g., PD vs missiles)
- Megastructure construction requires specific ascension perks
- Repeatables scale infinitely but with increasing cost
