"""Tests for clausewitz_parser — Stellaris 4.3.4."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import pytest

from engine.clausewitz_parser import (
    parse_file,
    parse_save,
    parse_string,
    parse_text,
)


class TestParseString:

    def test_simple_key_value(self) -> None:
        d = parse_string('name = "Test Empire"')
        assert d["name"] == "Test Empire"

    def test_numeric_values(self) -> None:
        d = parse_string("energy = 500\nminerals = 1200")
        assert d["energy"] == 500
        assert d["minerals"] == 1200

    def test_float_values(self) -> None:
        d = parse_string("ratio = 0.75")
        assert d["ratio"] == 0.75

    def test_bool_yes_no(self) -> None:
        d = parse_string("is_player = yes\nis_ai = no")
        assert d["is_player"] is True
        assert d["is_ai"] is False

    def test_nested_block(self) -> None:
        d = parse_string('empire = { name = "UNE" type = "default" }')
        assert isinstance(d["empire"], dict)
        assert d["empire"]["name"] == "UNE"
        assert d["empire"]["type"] == "default"

    def test_deeply_nested(self) -> None:
        text = """
        country = {
            government = {
                type = "democracy"
                civics = {
                    civic = "technocracy"
                }
            }
        }
        """
        d = parse_string(text)
        assert d["country"]["government"]["type"] == "democracy"
        assert d["country"]["government"]["civics"]["civic"] == "technocracy"

    def test_array_values(self) -> None:
        d = parse_string('traits = { "Intelligent" "Thrifty" "Strong" }')
        assert isinstance(d["traits"], list)
        assert "Intelligent" in d["traits"]
        assert len(d["traits"]) == 3

    def test_comments_stripped(self) -> None:
        d = parse_string("# This is a comment\nenergy = 100 # inline comment")
        assert d["energy"] == 100
        assert "#" not in str(d)

    def test_duplicate_keys_become_list(self) -> None:
        d = parse_string('ethic = "militarist"\nethic = "materialist"')
        assert isinstance(d["ethic"], list)
        assert len(d["ethic"]) == 2

    def test_operators(self) -> None:
        d = parse_string("check_variable = { which = my_var value > 5 }")
        assert isinstance(d["check_variable"], dict)

    def test_empty_block(self) -> None:
        d = parse_string("empty = { }")
        assert d["empty"] == {} or d["empty"] == []

    def test_unmatched_quote_does_not_crash(self) -> None:
        # Finding 4: corrupted saves should not crash the engine
        d = parse_string('name = "broken string without closing quote')
        assert "name" in d

    def test_empty_input(self) -> None:
        d = parse_string("")
        assert d == {}

    def test_anonymous_nested_blocks(self) -> None:
        """Parser must handle { { key=val } { key=val } } patterns.

        This is how Stellaris saves represent lists of objects: policies,
        player blocks, pop groups, etc.
        """
        text = """
        active_policies = {
            { policy = "diplomatic_stance" selected = "expansionist" }
            { policy = "war_philosophy" selected = "unrestricted" }
        }
        """
        d = parse_string(text)
        policies = d["active_policies"]
        assert isinstance(policies, list)
        assert len(policies) == 2
        assert policies[0]["policy"] == "diplomatic_stance"
        assert policies[1]["selected"] == "unrestricted"

    def test_anonymous_blocks_with_nested_values(self) -> None:
        """Player block: { { name="Fintz" country=0 } }"""
        text = 'player = { { name = "Fintz" country = 0 } }'
        d = parse_string(text)
        player = d["player"]
        assert isinstance(player, list)
        assert len(player) == 1
        assert player[0]["name"] == "Fintz"
        assert player[0]["country"] == 0

    def test_country_block_as_dict(self) -> None:
        """country = { 0 = { ... } 1 = { ... } } should parse as dict."""
        text = """
        country = {
            0 = { name = "Empire A" type = "default" }
            1 = { name = "Empire B" type = "default" }
        }
        """
        d = parse_string(text)
        assert isinstance(d["country"], dict)
        assert d["country"]["0"]["name"] == "Empire A"
        assert d["country"]["1"]["name"] == "Empire B"


class TestParseSave:

    def test_parse_sav_zip(self, tmp_path: Path) -> None:
        """Parse a minimal .sav file (ZIP with meta + gamestate)."""
        sav_path = tmp_path / "test.sav"
        with zipfile.ZipFile(sav_path, "w") as zf:
            zf.writestr("meta", 'date = "2230.06.15"\nname = "Test"')
            zf.writestr("gamestate", 'date = "2230.06.15"\ncountry = { }')

        result = parse_save(sav_path)
        assert "meta" in result
        assert "gamestate" in result
        assert result["meta"]["date"] == "2230.06.15"
        assert result["meta"]["name"] == "Test"

    def test_parse_sav_missing_meta(self, tmp_path: Path) -> None:
        sav_path = tmp_path / "no_meta.sav"
        with zipfile.ZipFile(sav_path, "w") as zf:
            zf.writestr("gamestate", "energy = 100")

        result = parse_save(sav_path)
        assert "meta" not in result
        assert result["gamestate"]["energy"] == 100


class TestParseFile:

    def test_parse_txt_file(self, tmp_path: Path) -> None:
        txt = tmp_path / "test.txt"
        txt.write_text('key = "value"\nnumber = 42', encoding="utf-8")
        d = parse_file(txt)
        assert d["key"] == "value"
        assert d["number"] == 42
