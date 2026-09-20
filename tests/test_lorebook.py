"""Character book (lorebook) matching: PLAN §4.3."""

from sparklchat.models.card import CharacterBook
from sparklchat.services.lorebook import MatchContext, entry_key, select_entries

HISTORY = ["Have you seen the brigade?", "No."]


def context(history=None, **overrides) -> MatchContext:
    values: dict = {"history": tuple(history if history is not None else HISTORY)}
    values.update(overrides)
    return MatchContext(**values)


def entry(**overrides) -> dict:
    values: dict = {
        "keys": ["brigade"],
        "content": "The SOS Brigade is a club.",
        "enabled": True,
        "insertion_order": 10,
        "extensions": {},
    }
    values.update(overrides)
    return values


def book(entries: list[dict], **overrides) -> CharacterBook:
    values: dict = {"extensions": {}, "entries": entries}
    values.update(overrides)
    return CharacterBook.model_validate(values)


def contents(matched) -> list[str]:
    return [item.content for item in matched.all]


def test_matches_a_key_in_recent_history() -> None:
    matched = select_entries(book([entry()]), HISTORY)
    assert contents(matched) == ["The SOS Brigade is a club."]


def test_ignores_entries_whose_keys_do_not_appear() -> None:
    matched = select_entries(book([entry(keys=["trombone"])]), HISTORY)
    assert contents(matched) == []


def test_matching_is_case_insensitive_by_default() -> None:
    matched = select_entries(book([entry(keys=["BRIGADE"])]), HISTORY)
    assert contents(matched) == ["The SOS Brigade is a club."]


def test_case_sensitive_entries_require_exact_case() -> None:
    exact = select_entries(book([entry(keys=["Brigade"], case_sensitive=True)]), HISTORY)
    assert contents(exact) == []

    lower = select_entries(book([entry(keys=["brigade"], case_sensitive=True)]), HISTORY)
    assert contents(lower) == ["The SOS Brigade is a club."]


def test_disabled_entries_are_skipped() -> None:
    matched = select_entries(book([entry(enabled=False)]), HISTORY)
    assert contents(matched) == []


def test_constant_entries_always_apply() -> None:
    matched = select_entries(book([entry(keys=[], constant=True)]), ["unrelated"])
    assert contents(matched) == ["The SOS Brigade is a club."]


def test_selective_requires_both_key_lists() -> None:
    books = book([entry(secondary_keys=["club"], selective=True)])

    assert contents(select_entries(books, ["the brigade is here"])) == []
    assert contents(select_entries(books, ["the brigade is a club"])) == [
        "The SOS Brigade is a club."
    ]


def test_selective_without_secondary_keys_never_matches() -> None:
    matched = select_entries(book([entry(selective=True)]), HISTORY)
    assert contents(matched) == []


def test_secondary_keys_are_ignored_without_selective() -> None:
    matched = select_entries(
        book([entry(secondary_keys=["nothing-here"], selective=False)]), HISTORY
    )
    assert contents(matched) == ["The SOS Brigade is a club."]


def test_entries_are_ordered_by_insertion_order() -> None:
    matched = select_entries(
        book(
            [
                entry(content="second", insertion_order=20),
                entry(content="first", insertion_order=5),
            ]
        ),
        HISTORY,
    )
    assert contents(matched) == ["first", "second"]


def test_position_splits_before_and_after_char() -> None:
    matched = select_entries(
        book(
            [
                entry(content="after", position="after_char"),
                entry(content="before", position="before_char"),
                entry(content="default", position=None),
            ]
        ),
        HISTORY,
    )
    assert [item.content for item in matched.before_char] == ["before", "default"]
    assert [item.content for item in matched.after_char] == ["after"]


def test_scan_depth_limits_the_history_window() -> None:
    books = book([entry(keys=["brigade"])], scan_depth=1)
    # Only the last message is scanned, so the key is out of scope.
    assert contents(select_entries(books, ["brigade", "nothing"])) == []
    assert contents(select_entries(books, ["nothing", "brigade"])) == ["The SOS Brigade is a club."]


def test_token_budget_drops_the_lowest_priority_first() -> None:
    books = book(
        [
            entry(content="a" * 40, insertion_order=1, priority=1),
            entry(content="b" * 40, insertion_order=2, priority=50),
        ],
        token_budget=12,
    )
    matched = select_entries(books, HISTORY)
    # Only one entry's worth of content fits; priority 1 is discarded first.
    assert contents(matched) == ["b" * 40]


def test_entries_without_priority_are_kept_over_low_priority_ones() -> None:
    books = book(
        [
            entry(content="low" * 10, insertion_order=1, priority=1),
            entry(content="high" * 10, insertion_order=2, priority=None),
        ],
        token_budget=12,
    )
    matched = select_entries(books, HISTORY)
    assert contents(matched) == ["high" * 10]


def test_zero_token_budget_means_unlimited() -> None:
    books = book([entry(content="x" * 400)], token_budget=0)
    assert len(contents(select_entries(books, HISTORY))) == 1


def test_recursive_scanning_pulls_in_chained_entries() -> None:
    books = book(
        [
            entry(content="The brigade meets in the club room.", keys=["brigade"]),
            entry(
                content="The club room is on the third floor.",
                keys=["club room"],
            ),
        ],
        recursive_scanning=True,
    )
    matched = select_entries(books, HISTORY)
    assert len(contents(matched)) == 2


def test_recursive_scanning_is_off_by_default() -> None:
    books = book(
        [
            entry(content="The brigade meets in the club room.", keys=["brigade"]),
            entry(keys=["club room"], content="Third floor."),
        ]
    )
    matched = select_entries(books, HISTORY)
    assert len(contents(matched)) == 1


def test_recursive_scanning_terminates_on_a_trigger_loop() -> None:
    books = book(
        [
            entry(content="alpha bravo", keys=["brigade"]),
            entry(content="bravo alpha", keys=["bravo"]),
        ],
        recursive_scanning=True,
    )
    matched = select_entries(books, HISTORY)
    assert len(contents(matched)) == 2


def test_no_book_yields_nothing() -> None:
    assert select_entries(None, HISTORY).all == []


# --- V3: regex keys --------------------------------------------------------


def test_use_regex_matches_a_pattern_in_the_history() -> None:
    books = book([entry(keys=[r"brig\w+"], use_regex=True)])
    assert contents(select_entries(books, HISTORY)) == ["The SOS Brigade is a club."]


def test_use_regex_supports_the_pattern_literal_with_flags() -> None:
    books = book([entry(keys=["/BRIGADE/i"], use_regex=True)])
    assert contents(select_entries(books, HISTORY)) == ["The SOS Brigade is a club."]


def test_use_regex_does_not_do_plain_substring_matching() -> None:
    # An anchored pattern has to be a real regex match, not a substring hit.
    books = book([entry(keys=["^brigade$"], use_regex=True)])
    assert contents(select_entries(books, HISTORY)) == []


def test_an_invalid_regex_never_matches() -> None:
    books = book([entry(keys=["(unclosed"], use_regex=True)])
    assert contents(select_entries(books, HISTORY)) == []


def test_constant_and_secondary_keys_are_ignored_with_use_regex() -> None:
    # `constant` is ignored, so the regex key still has to match.
    constant = book([entry(keys=[r"brig\w+"], constant=True, use_regex=True)])
    assert contents(select_entries(constant, ["unrelated"], context=context(["unrelated"]))) == []

    # `secondary_keys` is ignored even with `selective`.
    selective = book(
        [entry(keys=[r"brig\w+"], secondary_keys=["missing"], selective=True, use_regex=True)]
    )
    assert contents(select_entries(selective, HISTORY)) == ["The SOS Brigade is a club."]


# --- V3: decorators --------------------------------------------------------


def test_decorator_lines_are_stripped_from_the_content() -> None:
    books = book([entry(content="@@activate\nMATCHED")])
    matched = select_entries(books, HISTORY)
    assert contents(matched) == ["MATCHED"]


def test_activate_forces_a_match_without_keys() -> None:
    books = book([entry(keys=[], content="@@activate\nALWAYS")])
    assert contents(select_entries(books, ["nothing"], context=context(["nothing"]))) == ["ALWAYS"]


def test_dont_activate_suppresses_an_otherwise_matching_entry() -> None:
    books = book([entry(content="@@dont_activate\nNOPE")])
    assert contents(select_entries(books, HISTORY)) == []


def test_activate_beats_dont_activate() -> None:
    books = book([entry(content="@@dont_activate\n@@activate\nYES")])
    assert contents(select_entries(books, HISTORY)) == ["YES"]


def test_exclude_keys_suppresses_a_match() -> None:
    books = book([entry(content="@@exclude_keys No.\nNOPE")])
    assert contents(select_entries(books, HISTORY)) == []


def test_additional_keys_are_extra_triggers() -> None:
    books = book([entry(keys=["brigade"], content="@@additional_keys trombone\nMATCHED")])
    assert contents(select_entries(books, ["a trombone"], context=context(["a trombone"]))) == [
        "MATCHED"
    ]


def test_scan_depth_decorator_overrides_the_book_depth() -> None:
    books = book([entry(content="@@scan_depth 1\nMATCHED")], scan_depth=4)
    assert contents(select_entries(books, ["brigade", "nothing"])) == []
    assert contents(select_entries(books, ["nothing", "brigade"])) == ["MATCHED"]


def test_activate_only_after_waits_for_enough_assistant_turns() -> None:
    books = book([entry(content="@@activate_only_after 3\nLATE")])
    assert contents(select_entries(books, HISTORY, context=context(assistant_count=2))) == []
    assert contents(select_entries(books, HISTORY, context=context(assistant_count=3))) == ["LATE"]


def test_activate_only_every_runs_on_a_cycle() -> None:
    books = book([entry(content="@@activate_only_every 2\nEVERY-OTHER")])
    assert contents(select_entries(books, HISTORY, context=context(assistant_count=3))) == []
    assert contents(select_entries(books, HISTORY, context=context(assistant_count=4))) == [
        "EVERY-OTHER"
    ]


def test_keep_activate_after_match_sticks_once_seen_twice() -> None:
    books = book([entry(keys=["nothing-here"], content="@@keep_activate_after_match\nKEPT")])
    key = entry_key(books.entries[0])
    counts = {key: 2}

    assert contents(select_entries(books, HISTORY)) == []
    assert contents(select_entries(books, HISTORY, context=context(activation_counts=counts))) == [
        "KEPT"
    ]


def test_dont_activate_after_match_stops_once_seen_twice() -> None:
    books = book([entry(content="@@dont_activate_after_match\nFIRST-ONLY")])
    key = entry_key(books.entries[0])
    counts = {key: 2}

    assert contents(select_entries(books, HISTORY)) == ["FIRST-ONLY"]
    assert contents(select_entries(books, HISTORY, context=context(activation_counts=counts))) == []


def test_is_greeting_matches_only_the_active_greeting() -> None:
    books = book([entry(content="@@is_greeting 1\nALT-GREETING")])
    assert contents(select_entries(books, HISTORY, context=context(greeting_index=0))) == []
    assert contents(select_entries(books, HISTORY, context=context(greeting_index=1))) == [
        "ALT-GREETING"
    ]


def test_is_user_icon_matches_the_active_icon() -> None:
    books = book([entry(content="@@is_user_icon Ash\nASH-ONLY")])
    other = context(user_icon="Misty")
    active = context(user_icon="Ash")

    assert contents(select_entries(books, HISTORY, context=other)) == []
    assert contents(select_entries(books, HISTORY, context=active)) == ["ASH-ONLY"]


def test_ignore_on_max_context_only_matches_below_the_limit() -> None:
    books = book([entry(content="@@ignore_on_max_context\nROOM-ONLY")])
    roomy = context(token_count=10, max_context_tokens=100)
    full = context(token_count=100, max_context_tokens=100)

    assert contents(select_entries(books, HISTORY, context=roomy)) == ["ROOM-ONLY"]
    assert contents(select_entries(books, HISTORY, context=full)) == []


def test_ignore_on_max_context_entries_are_not_dropped_by_the_budget() -> None:
    books = book(
        [
            entry(content="@@ignore_on_max_context\n" + "a" * 40, insertion_order=1, priority=1),
            entry(content="b" * 40, insertion_order=2, priority=50),
        ],
        token_budget=12,
    )
    matched = select_entries(books, HISTORY)
    assert contents(matched) == ["a" * 40]


def test_depth_decorator_moves_an_entry_into_the_chat_log() -> None:
    books = book([entry(content="@@depth 1\nIN-CHAT")])
    matched = select_entries(books, HISTORY)

    assert [item.content for item in matched.chat] == ["IN-CHAT"]
    assert matched.before_char == []


def test_position_decorator_keeps_the_entry_out_of_the_chat_log() -> None:
    books = book([entry(content="@@position after_desc\nNEAR-DESC")])
    matched = select_entries(books, HISTORY)

    assert matched.chat == []
    assert matched.before_char[0].decorators.position == "after_desc"


def test_position_wins_over_depth() -> None:
    books = book([entry(content="@@depth 1\n@@position scenario\nIN-SCENARIO")])
    matched = select_entries(books, HISTORY)

    assert matched.chat == []
    assert matched.before_char[0].decorators.position == "scenario"


def test_recursive_scanning_reveals_hidden_keys() -> None:
    books = book(
        [
            entry(keys=["brigade"], content="The brigade meets at {{hidden_key:club room}}."),
            entry(keys=["club room"], content="Third floor."),
        ],
        recursive_scanning=True,
    )
    assert len(contents(select_entries(books, HISTORY))) == 2


def test_hidden_keys_are_not_scanned_without_recursion() -> None:
    books = book(
        [
            entry(keys=["brigade"], content="The brigade meets at {{hidden_key:club room}}."),
            entry(keys=["club room"], content="Third floor."),
        ]
    )
    assert len(contents(select_entries(books, HISTORY))) == 1


def test_comment_macros_in_the_history_are_not_matched() -> None:
    books = book([entry(keys=["brigade"])])
    # `{{// …}}` is a comment, so it must not count as a trigger.
    assert contents(select_entries(books, ["{{// brigade}}"])) == []
    assert contents(select_entries(books, ["{{comment: brigade}}"])) == []
