"""
Clausewitz Text Parser — Pure Python parser for Paradox save/script files.

Parses the Clausewitz key=value text format into Python dicts and lists.
No external dependencies.  Handles:
  - key = value pairs
  - key = { nested blocks }
  - Arrays (lists of values inside braces)
  - Quoted strings
  - Comments (# to end of line)
  - Operators: =, <, >, <=, >=

Stellaris saves (.sav) are ZIP files containing:
  - ``meta``      — game metadata (version, date, player)
  - ``gamestate`` — full game state in Clausewitz text format

Performance notes:
  - Parses ~5 MB gamestate in ~2-4 seconds (pure Python)
  - Sufficient for autosave polling (every few game-months)
  - If performance becomes a bottleneck, swap in the Rust parser from
    stellaris-dashboard (maturin + jomini)
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import TextIO

# Token patterns
_COMMENT = re.compile(r"#[^\n]*")
_TOKEN = re.compile(r"[^\s={}<>]+")


def parse_save(path: str | Path) -> dict:
    """Parse a Stellaris ``.sav`` file (ZIP) and return ``{meta, gamestate}``."""
    path = Path(path)
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        result: dict = {}
        if "meta" in names:
            with zf.open("meta") as f:
                result["meta"] = parse_text(io.TextIOWrapper(f, encoding="utf-8"))
        if "gamestate" in names:
            with zf.open("gamestate") as f:
                result["gamestate"] = parse_text(io.TextIOWrapper(f, encoding="utf-8"))
        return result


def parse_file(path: str | Path) -> dict:
    """Parse a single Clausewitz text file."""
    with open(path, encoding="utf-8-sig") as f:
        return parse_text(f)


def parse_text(source: TextIO | str) -> dict:
    """Parse Clausewitz text from a file-like object or string."""
    if isinstance(source, str):
        source = io.StringIO(source)
    tokens = _tokenize(source.read())
    return _parse_block(iter(tokens), top_level=True)


def parse_string(text: str) -> dict:
    """Parse Clausewitz text from a string."""
    return parse_text(text)


# ------------------------------------------------------------------ #
# Tokenizer
# ------------------------------------------------------------------ #

def _tokenize(text: str) -> list[str]:
    """Convert raw text into a flat token list."""
    # Strip comments
    text = _COMMENT.sub("", text)
    tokens: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        # Whitespace
        if c in " \t\r\n":
            i += 1
            continue
        # Braces
        if c in "{}":
            tokens.append(c)
            i += 1
            continue
        # Quoted string
        if c == '"':
            end = text.find('"', i + 1)
            if end == -1:
                end = n - 1  # unterminated quote — take rest of input
            tokens.append(text[i : end + 1])  # keep quotes for later
            i = end + 1
            continue
        # Operators
        if c in "=<>!":
            j = i + 1
            while j < n and text[j] in "=<>!":
                j += 1
            tokens.append(text[i:j])
            i = j
            continue
        # Bare token (word, number, yes/no)
        m = _TOKEN.match(text, i)
        if m:
            tokens.append(m.group())
            i = m.end()
            continue
        # Skip unknown chars
        i += 1
    return tokens


# ------------------------------------------------------------------ #
# Recursive descent parser
# ------------------------------------------------------------------ #

def _parse_block(tokens, top_level: bool = False) -> dict:
    """Parse a { ... } block into a dict.

    Duplicate keys are handled by converting the value to a list.
    """
    result: dict = {}

    while True:
        tok = _next(tokens)
        if tok is None:
            break
        if tok == "}":
            if top_level:
                continue  # stray closing brace at top level
            break

        # Look ahead for operator
        peek = _next(tokens)

        if peek in ("=", "<", ">", "<=", ">=", "!="):
            # key = value
            key = _unquote(tok)
            value = _parse_value(tokens)
            _dict_add(result, key, value)
        elif peek == "{":
            # key { block } (no operator — treat key as list item or sub-block)
            # This happens in arrays like: names = { "a" "b" }
            # where tok is a value and peek starts a new block
            key = _unquote(tok)
            value = _parse_block(tokens)
            _dict_add(result, key, value)
        elif peek == "}":
            # Single token before close brace — it's a list item
            _dict_add(result, _unquote(tok), True)
            if not top_level:
                break
        elif peek is None:
            # EOF after key — treat as flag
            _dict_add(result, _unquote(tok), True)
            break
        else:
            # Two consecutive bare tokens — could be array entries
            # Put tok back conceptually and try as array
            _dict_add(result, _unquote(tok), True)
            # Process peek as next key
            if peek not in ("}", "{"):
                peek2 = _next(tokens)
                if peek2 in ("=", "<", ">", "<=", ">="):
                    value = _parse_value(tokens)
                    _dict_add(result, _unquote(peek), value)
                elif peek2 == "{":
                    value = _parse_block(tokens)
                    _dict_add(result, _unquote(peek), value)
                elif peek2 == "}":
                    _dict_add(result, _unquote(peek), True)
                    if not top_level:
                        break
                elif peek2 is not None:
                    _dict_add(result, _unquote(peek), True)
                    _dict_add(result, _unquote(peek2), True)

    return result


def _parse_value(tokens):
    """Parse a right-hand-side value (scalar or block)."""
    tok = _next(tokens)
    if tok is None:
        return ""
    if tok == "{":
        return _parse_brace_content(tokens)
    return _coerce(tok)


def _parse_brace_content(tokens):
    """Parse content inside { ... }.

    Returns a list if all entries are bare values (array), otherwise a dict.

    Handles three Clausewitz patterns:
      1. ``{ key=val key=val }``       → dict
      2. ``{ "a" "b" "c" }``           → list of scalars
      3. ``{ { k=v } { k=v } }``       → list of dicts (anonymous blocks)
    """
    items: list = []
    pairs: dict = {}
    is_dict = False

    while True:
        tok = _next(tokens)
        if tok is None or tok == "}":
            break

        # Anonymous nested block: { { ... } { ... } }
        if tok == "{":
            nested = _parse_block(tokens)  # reads until matching }
            items.append(nested)
            continue

        peek = _next(tokens)

        if peek in ("=", "<", ">", "<=", ">=", "!="):
            # key = value → this is a dict block
            is_dict = True
            key = _unquote(tok)
            value = _parse_value(tokens)
            _dict_add(pairs, key, value)
        elif peek == "{":
            # Could be dict entry without = or nested block
            key = _unquote(tok)
            value = _parse_block(tokens)
            is_dict = True
            _dict_add(pairs, key, value)
        elif peek == "}":
            # End of block — tok is last array item
            items.append(_coerce(tok))
            break
        elif peek is None:
            items.append(_coerce(tok))
            break
        else:
            # Two consecutive values — array mode
            items.append(_coerce(tok))
            items.append(_coerce(peek))

    if is_dict:
        # Mix array items into dict if any exist
        if items:
            pairs["_array"] = items
        return pairs
    return items if items else pairs


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _next(tokens):
    """Get next token from iterator, or None at end."""
    return next(tokens, None)


def _unquote(s: str) -> str:
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s


def _coerce(s: str):
    """Convert string to int, float, bool, or keep as string."""
    s = _unquote(s)
    if s == "yes":
        return True
    if s == "no":
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _dict_add(d: dict, key: str, value) -> None:
    """Add to dict, converting to list on duplicate keys."""
    if key not in d:
        d[key] = value
    else:
        existing = d[key]
        if isinstance(existing, list) and not isinstance(value, list):
            existing.append(value)
        else:
            d[key] = [existing, value]
