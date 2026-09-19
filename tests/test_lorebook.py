"""Character book (lorebook) matching: PLAN §4.3."""

from sparklchat.models.card import CharacterBook
from sparklchat.services.lorebook import select_entries

HISTORY = ["Have you seen the brigade?", "No."]


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
