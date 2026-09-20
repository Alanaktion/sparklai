"""Character Card V3 lorebook decorator parsing."""

from sparklchat.services.decorators import Decorators, parse_decorators, strip_decorators


def test_parses_integer_decorator_and_removes_line() -> None:
    decorators, content = parse_decorators("@@depth 4\nA quiet room.")
    assert decorators.depth == 4
    assert content == "A quiet room."


def test_parses_negative_integer_for_depth() -> None:
    decorators, _ = parse_decorators("@@depth -2")
    assert decorators.depth == -2


def test_parses_flags_without_values() -> None:
    content = (
        "@@keep_activate_after_match\n@@dont_activate\n@@activate\n@@ignore_on_max_context\nbody"
    )
    decorators, stripped = parse_decorators(content)
    assert decorators.keep_activate_after_match is True
    assert decorators.dont_activate is True
    assert decorators.activate is True
    assert decorators.ignore_on_max_context is True
    assert stripped == "body"


def test_flag_with_a_value_is_ignored() -> None:
    decorators, content = parse_decorators("@@activate yes\nbody")
    assert decorators.activate is False
    assert content == "body"


def test_role_valid_and_normalised() -> None:
    decorators, _ = parse_decorators("@@role System")
    assert decorators.role == "system"


def test_role_invalid_is_ignored() -> None:
    decorators, content = parse_decorators("@@role narrator\nbody")
    assert decorators.role is None
    assert content == "body"


def test_position_stored_verbatim() -> None:
    decorators, _ = parse_decorators("@@position after_desc")
    assert decorators.position == "after_desc"


def test_empty_position_is_ignored() -> None:
    decorators, _ = parse_decorators("@@position")
    assert decorators.position is None


def test_is_user_icon_and_is_greeting() -> None:
    decorators, _ = parse_decorators("@@is_user_icon https://example.com/icon.png\n@@is_greeting 1")
    assert decorators.is_user_icon == "https://example.com/icon.png"
    assert decorators.is_greeting == 1


def test_names_match_exactly() -> None:
    decorators, _ = parse_decorators("@@activate_only_after 3\n@@activate")
    assert decorators.activate_only_after == 3
    assert decorators.activate is True


def test_additional_keys_accumulate_across_occurrences() -> None:
    decorators, _ = parse_decorators("@@additional_keys a, b\n@@additional_keys c")
    assert decorators.additional_keys == (("a", "b"), ("c",))


def test_additional_keys_honours_escaped_comma() -> None:
    decorators, _ = parse_decorators(r"@@additional_keys foo\,bar, baz")
    assert decorators.additional_keys == (("foo,bar", "baz"),)


def test_exclude_keys_splits_and_unescapes_commas() -> None:
    decorators, _ = parse_decorators(r"@@exclude_keys a\, b, c, , d")
    assert decorators.exclude_keys == ("a, b", "c", "d")


def test_exclude_keys_first_occurrence_wins() -> None:
    decorators, _ = parse_decorators("@@exclude_keys a\n@@exclude_keys b")
    assert decorators.exclude_keys == ("a",)


def test_disable_ui_prompt_accumulates() -> None:
    decorators, _ = parse_decorators("@@disable_ui_prompt a\n@@disable_ui_prompt b")
    assert decorators.disable_ui_prompt == ("a", "b")


def test_unknown_primary_uses_fallback() -> None:
    decorators, content = parse_decorators("@@unknown_thing 4\n@@@activate_only_after 4\nbody")
    assert decorators.activate_only_after == 4
    assert content == "body"


def test_chain_picks_first_recognised_fallback() -> None:
    decorators, content = parse_decorators(
        "@@unknown 1\n@@@also_unknown 2\n@@@depth 3\n@@@scan_depth 5\nbody"
    )
    assert decorators.depth == 3
    assert decorators.scan_depth is None
    assert content == "body"


def test_recognised_primary_wins_over_fallback() -> None:
    decorators, _ = parse_decorators("@@depth 2\n@@@scan_depth 9")
    assert decorators.depth == 2
    assert decorators.scan_depth is None


def test_long_fallback_chain() -> None:
    content = "@@a 1\n@@@b 2\n@@@c 3\n@@@d 4\n@@@depth 7\nbody"
    decorators, stripped = parse_decorators(content)
    assert decorators.depth == 7
    assert stripped == "body"


def test_invalid_value_does_not_fall_back() -> None:
    decorators, content = parse_decorators("@@depth nope\n@@@scan_depth 5\nbody")
    assert decorators.depth is None
    assert decorators.scan_depth is None
    assert content == "body"


def test_first_occurrence_wins_for_repeated_decorator() -> None:
    decorators, _ = parse_decorators("@@depth 1\n@@depth 2")
    assert decorators.depth == 1


def test_blank_line_ends_a_chain() -> None:
    decorators, content = parse_decorators("@@unknown 1\n\n@@@depth 3\nbody")
    assert decorators.depth == 3
    assert content == "body"


def test_unknown_decorator_lines_are_still_stripped() -> None:
    decorators, content = parse_decorators("@@totally_unknown 5\n@@another_unknown\nText")
    assert decorators == Decorators()
    assert content == "Text"


def test_content_without_decorators_is_unchanged() -> None:
    original = "First line.\n\nThird line.\n  indented."
    decorators, content = parse_decorators(original)
    assert decorators == Decorators()
    assert content == original


def test_internal_structure_is_preserved() -> None:
    decorators, content = parse_decorators("@@depth 1\n  indented\n\nplain")
    assert decorators.depth == 1
    assert content == "  indented\n\nplain"


def test_leading_whitespace_before_decorator() -> None:
    decorators, content = parse_decorators("   @@depth 4\nbody")
    assert decorators.depth == 4
    assert content == "body"


def test_content_of_only_decorators_is_empty() -> None:
    decorators, content = parse_decorators("@@depth 3\n@@unknown\n@@@scan_depth 1")
    assert decorators.depth == 3
    assert decorators.scan_depth == 1
    assert content == ""


def test_empty_content() -> None:
    decorators, content = parse_decorators("")
    assert decorators == Decorators()
    assert content == ""


def test_strip_decorators_matches_parse_decorators() -> None:
    content = "@@depth 2\nHello\n@@role system\n"
    assert strip_decorators(content) == parse_decorators(content)[1]
    assert strip_decorators(content) == "Hello"
