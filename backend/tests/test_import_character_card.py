"""Port of `src/tests/import-character-card.test.ts` — keep the two in sync."""

from app.services.import_character_card import CharacterCardV2, parse_character_card

SAMPLE_CARD = CharacterCardV2.model_validate(
    {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": "Your wife and daughter",
            "description": (
                "{{char}} is roleplaying as two characters. \r\n\r\n{{user}} wife Janette:\r\n"
                "[Name: Janette]\r\n[Age: 29]\r\n[Gender: Female]\r\n[Role: Wife]\r\n\r\n"
                "[Appearance: Janette is a striking woman with long, silky brunette hair.]\r\n\r\n"
                "[Personality: Janette is the cornerstone of the household, embodying qualities "
                "of care, love, and productivity.]\r\n\r\n"
                "[Speech: Janette speaks with a calm yet firm tone.]"
            ),
            "personality": "Caring, protective, nurturing",
            "scenario": "{{user}} is living with his loyal wife and childish daughter",
            "first_mes": "*The heated light of sun enters your bedroom*",
            "mes_example": "",
            "creator_notes": "Leave review/publish chats.",
            "system_prompt": "",
            "post_history_instructions": "",
            "alternate_greetings": [],
            "tags": ["female", "human", "original", "sfw"],
            "character_version": "main",
            "avatar": "http://example.com/avatar.png",
            "creator": "saikato",
            "extensions": {},
        },
    }
)


def test_extracts_basic_fields():
    result = parse_character_card(SAMPLE_CARD, 1)
    assert result.name == "Your wife and daughter"
    assert result.age == 29
    assert result.pronouns == "she/her"
    assert result.scenario == "{{user}} is living with his loyal wife and childish daughter"
    assert result.first_mes == "*The heated light of sun enters your bedroom*"


def test_parses_personality_from_personality_field():
    result = parse_character_card(SAMPLE_CARD, 1)
    assert result.personality_traits == "Caring, protective, nurturing"


def test_parses_tags_into_interests():
    result = parse_character_card(SAMPLE_CARD, 1)
    assert "female" in result.interests
    assert "sfw" in result.interests


def test_parses_speech_into_writing_style():
    result = parse_character_card(SAMPLE_CARD, 1)
    assert "calm yet firm" in result.writing_style


def test_extracts_appearance_from_description():
    result = parse_character_card(SAMPLE_CARD, 1)
    assert "long, silky brunette hair" in result.appearance


def test_builds_additional_prompt_from_creator_notes():
    result = parse_character_card(SAMPLE_CARD, 1)
    assert "Creator notes" in result.additional_prompt
    assert "Leave review/publish chats" in result.additional_prompt


def test_infers_relationship_status_from_description():
    result = parse_character_card(SAMPLE_CARD, 1)
    assert result.relationship_status == "Married"
