from io import StringIO
from types import SimpleNamespace

import pytest

from tinyhtml5 import inputstream


@pytest.fixture
def compiled_patterns(monkeypatch):
    cache = inputstream.characters_until_regex
    saved = cache.copy()
    cache.clear()
    patterns = []
    compile_pattern = inputstream.re.compile

    def record_compile(pattern):
        patterns.append(pattern)
        return compile_pattern(pattern)

    monkeypatch.setattr(inputstream, "re", SimpleNamespace(compile=record_compile))
    yield patterns
    cache.clear()
    cache.update(saved)


@pytest.mark.parametrize(
    ("characters", "opposite", "text", "prefix", "next_character"),
    [
        ("&<\0", False, "Grüße &rest", "Grüße ", "&"),
        ("&<\0", True, "&&<\0rest", "&&<\0", "r"),
        (frozenset(" \t\n"), True, " \t\nrest", " \t\n", "r"),
        (frozenset("0123456789"), True, "123x", "123", "x"),
        ("x", False, "xrest", "", "x"),
        ("x", True, "rest", "", "r"),
    ],
)
def test_chars_until_reuses_compilation_across_streams(
        compiled_patterns, characters, opposite, text, prefix, next_character):
    for _ in range(4):
        stream = inputstream.HTMLUnicodeInputStream(text)
        assert stream.chars_until(characters, opposite) == prefix
        assert stream.character() == next_character
    assert len(compiled_patterns) == 1


def test_chars_until_keeps_character_sets_and_opposite_modes_separate(
        compiled_patterns):
    cases = [
        ("x", False, "aax", "aa", "x"),
        ("y", False, "bby", "bb", "y"),
        ("x", True, "xxz", "xx", "z"),
        ("y", True, "yyz", "yy", "z"),
    ]
    for _ in range(3):
        for characters, opposite, text, prefix, next_character in cases:
            stream = inputstream.HTMLUnicodeInputStream(text)
            assert stream.chars_until(characters, opposite) == prefix
            assert stream.character() == next_character
    assert len(compiled_patterns) == len(cases)


def test_chars_until_warm_pattern_preserves_chunk_normalization_and_position(
        compiled_patterns):
    class SmallChunks(StringIO):
        def read(self, size=-1):
            return super().read(min(size, 3) if size >= 0 else 3)

    warm = inputstream.HTMLUnicodeInputStream("warm<")
    assert warm.chars_until("<") == "warm"
    stream = inputstream.HTMLUnicodeInputStream(SmallChunks("A\r\nB\rC\tü<tail"))
    assert stream.chars_until("<") == "A\nB\nC\tü"
    assert stream.position() == (3, 3)
    assert stream.character() == "<"
    assert stream.chars_until("<") == "tail"
    assert stream.character() is inputstream.EOF
    assert len(compiled_patterns) == 1
