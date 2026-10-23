import pytest

from app.engine import clue_engine
from app.engine.clue_engine import GameRuleError


def test_examine_reveals_location_clues_and_spends_a_turn(case, progress):
    outcome = clue_engine.examine(case, progress, "guest_wing")
    assert outcome.new_clues == ["c3", "c13"]
    assert progress.turns_left == 14
    assert progress.examined_locations == ["guest_wing"]


def test_examine_twice_or_unknown_location_is_rejected(case, progress):
    clue_engine.examine(case, progress, "study")
    with pytest.raises(GameRuleError):
        clue_engine.examine(case, progress, "study")
    with pytest.raises(GameRuleError):
        clue_engine.examine(case, progress, "ballroom")
    assert progress.turns_left == 14


def test_three_questions_per_turn_to_same_suspect(case, progress):
    for _ in range(3):
        clue_engine.interrogate(case, progress, "s2", [])
    assert progress.turns_left == 14
    clue_engine.interrogate(case, progress, "s2", [])
    assert progress.turns_left == 13
    clue_engine.interrogate(case, progress, "s3", [])
    assert progress.turns_left == 12


def test_first_interrogation_records_the_alibi_lie(case, progress):
    outcome = clue_engine.interrogate(case, progress, "s2", [])
    [statement] = outcome.new_statements
    assert statement.kind == "alibi"
    assert statement.lie_id == "s2_lie_alibi"


def test_suspect_without_alibi_lie_gets_plain_alibi_statement(case, progress):
    outcome = clue_engine.interrogate(case, progress, "s3", [])
    assert [s.kind for s in outcome.new_statements] == ["alibi"]
    assert outcome.new_statements[0].lie_id is None


def test_topic_triggers_lie_statement_once(case, progress):
    clue_engine.interrogate(case, progress, "s2", ["garden"])
    clue_engine.interrogate(case, progress, "s2", ["garden"])
    garden = [s for s in progress.statements if s.lie_id == "s2_lie_garden"]
    assert len(garden) == 1


def test_topic_unlocks_interrogation_clue(case, progress):
    outcome = clue_engine.interrogate(case, progress, "s3", ["garden"])
    assert outcome.new_clues == ["c8"]
    assert "c8" in outcome.allowed_reveals


def test_confront_with_genuine_contradiction(case, progress):
    clue_engine.interrogate(case, progress, "s2", ["garden"])
    clue_engine.examine(case, progress, "guest_wing")
    lie_statement = next(s for s in progress.statements if s.lie_id == "s2_lie_garden")

    outcome = clue_engine.confront(case, progress, "s2", [lie_statement.id, "c3"])

    assert outcome.contradiction is not None
    assert progress.composure["s2"] == 70
    assert "c9" in outcome.new_clues
    assert progress.last_contradiction.from_ == lie_statement.id


def test_confront_order_does_not_matter_and_only_counts_once(case, progress):
    clue_engine.interrogate(case, progress, "s2", ["garden"])
    clue_engine.examine(case, progress, "guest_wing")
    st = next(s for s in progress.statements if s.lie_id == "s2_lie_garden")
    assert clue_engine.confront(case, progress, "s2", ["c3", st.id]).contradiction
    assert clue_engine.confront(case, progress, "s2", ["c3", st.id]).contradiction is None
    assert progress.composure["s2"] == 70


def test_confront_non_contradiction_spends_turn(case, progress):
    clue_engine.interrogate(case, progress, "s2", [])
    clue_engine.examine(case, progress, "study")
    alibi = progress.statements[0]
    before = progress.turns_left
    outcome = clue_engine.confront(case, progress, "s2", [alibi.id, "c6"])
    assert outcome.contradiction is None
    assert progress.turns_left == before - 1
    assert progress.composure["s2"] == 100


def test_confront_rejects_unrevealed_items(case, progress):
    clue_engine.interrogate(case, progress, "s2", ["garden"])
    st = progress.statements[-1]
    with pytest.raises(GameRuleError):
        clue_engine.confront(case, progress, "s2", [st.id, "c3"])  # c3 not found yet
    assert progress.composure["s2"] == 100


def test_confront_against_wrong_suspect_does_nothing(case, progress):
    clue_engine.interrogate(case, progress, "s2", ["garden"])
    clue_engine.examine(case, progress, "guest_wing")
    st = next(s for s in progress.statements if s.lie_id == "s2_lie_garden")
    assert clue_engine.confront(case, progress, "s3", [st.id, "c3"]).contradiction is None


def test_secret_revealed_when_composure_crosses_threshold(case, progress):
    clue_engine.interrogate(case, progress, "s2", ["garden", "will"])
    clue_engine.examine(case, progress, "guest_wing")
    clue_engine.examine(case, progress, "study")
    garden = next(s for s in progress.statements if s.lie_id == "s2_lie_garden")
    will = next(s for s in progress.statements if s.lie_id == "s2_lie_will")

    first = clue_engine.confront(case, progress, "s2", [garden.id, "c3"])  # 100 -> 70
    assert first.revealed_secrets == []
    second = clue_engine.confront(case, progress, "s2", [will.id, "c5"])  # 70 -> 40
    assert second.revealed_secrets == ["s2_sec"]
    assert second.new_statements[-1].kind == "confession"


def test_running_out_of_turns_moves_to_accusing(case, progress):
    progress.turns_left = 1
    clue_engine.examine(case, progress, "study")
    assert progress.phase == "accusing"
    with pytest.raises(GameRuleError):
        clue_engine.examine(case, progress, "library")


def test_mood_bands():
    assert [clue_engine.mood_for(c) for c in (100, 60, 30, 10)] == ["calm", "guarded", "nervous", "cracking"]
