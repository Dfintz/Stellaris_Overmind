"""Audit script — check strategic_knowledge completeness."""
from engine.strategic_knowledge import (
    TRADITION_TREES, ASCENSION_PERKS, MEGASTRUCTURES,
    WAR_GOALS, FEDERATION_TYPES, DESIGNATIONS,
)

print("=== TRADITIONS (have", len(TRADITION_TREES), ") ===")
for name in sorted(TRADITION_TREES):
    t = TRADITION_TREES[name]
    print(f"  {name}: focus={t.get('focus','?')} gestalt={t.get('gestalt_variant','-')}")

# Wiki lists 17 tradition trees
wiki_trees = [
    "Adaptability", "Harmony", "Commerce", "Diplomacy", "Discovery",
    "Domination", "Expansion", "Prosperity", "Supremacy", "Fortification",
    "Enmity", "Politics", "Subterfuge", "Aptitude", "Statecraft",
    "Archivism", "Domestication",
]
missing_trees = [t for t in wiki_trees if t not in TRADITION_TREES]
print(f"\n  MISSING traditions: {missing_trees}")

print("\n=== ASCENSION PERKS (have", len(ASCENSION_PERKS), ") ===")

# Wiki lists these perks
wiki_perks = [
    # Tier 0
    "Technological Ascendancy", "Executive Vigor", "Interstellar Dominion",
    "One Vision", "Mastery of Nature", "Shared Destiny", "Voidborne",
    "Galactic Wonders", "Eternal Vigilance", "Nihilistic Acquisition",
    "Enigmatic Engineering", "Transcendent Learning", "Imperial Prerogative",
    "Consecrated Worlds", "Universal Transactions", "Lord of War",
    "Mechromancy", "Archaeo-Engineers", "Xeno-Compatibility", "Hydrocentric", "Detox",
    # Tier 1
    "Grasp the Void", "World Shaper", "Galactic Weather Control",
    # Tier 2
    "Synthetic Evolution", "The Flesh is Weak", "Mind Over Matter",
    "Biomorphosis", "Synthetic Age", "Interdimensional Processing",
    "Galactic Force Projection", "Master Builders", "Arcology Project",
    "Hive Worlds", "Machine Worlds",
    # Tier 3
    "Defender of the Galaxy", "Galactic Contender", "Colossus Project",
    "Galactic Nemesis", "Cosmogenesis", "Behemoth Fury", "Galactic Hyperthermia",
]
missing_perks = [p for p in wiki_perks if p not in ASCENSION_PERKS]
print(f"  MISSING perks ({len(missing_perks)}): {missing_perks}")

print("\n=== MEGASTRUCTURES (have", len(MEGASTRUCTURES), ") ===")

wiki_megas = [
    "Dyson Sphere", "Matter Decompressor", "Science Nexus", "Ring World",
    "Sentry Array", "Strategic Coordination Center", "Mega Art Installation",
    "Interstellar Assembly", "Mega Shipyard", "Gateway", "Hyper Relay",
    "Habitat", "Orbital Ring", "Deep Space Citadel", "Arc Furnace",
    "Quantum Catapult", "Aetherophasic Engine", "Synaptic Lathe",
    "Grand Archive", "Behemoth Egg", "Shroud Seal", "Galactic Crucible",
]
missing_megas = [m for m in wiki_megas if m not in MEGASTRUCTURES]
print(f"  MISSING megastructures ({len(missing_megas)}): {missing_megas}")

print("\n=== SUMMARY ===")
print(f"  Traditions: {len(TRADITION_TREES)}/17 ({len(missing_trees)} missing)")
print(f"  Perks: {len(ASCENSION_PERKS)}/{len(wiki_perks)} ({len(missing_perks)} missing)")
print(f"  Megastructures: {len(MEGASTRUCTURES)}/{len(wiki_megas)} ({len(missing_megas)} missing)")
print(f"  War Goals: {len(WAR_GOALS)}")
print(f"  Federations: {len(FEDERATION_TYPES)}")
print(f"  Designations: {len(DESIGNATIONS)}")
