import json

from app.agents import guards
from app.engine import clue_engine, scoring
from app.engine.projection import project
from app.models.public import Accusation


def test_perfect_score(case, progress):
    progress.revealed_clues = ["c3", "c5", "c9"]
    progress.turns_left = 10
    result = scoring.score(
        case, progress, Accusation(suspect_id="s2", motive_id="inheritance", evidence=["c3", "c5", "c9"])
    )
    assert result.total == 100
    assert result.rank == "Legendary Detective"


def test_wrong_culprit_scores_nothing_for_evidence_or_turns(case, progress):
    progress.revealed_clues = ["c3", "c7"]
    result = scoring.score(case, progress, Accusation(suspect_id="s4", motive_id="blackmail", evidence=["c7"]))
    assert result.total == 0
    assert result.rank == "Rookie"


def test_red_herrings_and_unfound_evidence_do_not_count(case, progress):
    progress.revealed_clues = ["c3", "c13"]
    progress.turns_left = 0
    result = scoring.score(case, progress, Accusation(suspect_id="s2", motive_id="debts", evidence=["c3", "c13", "c5"]))
    assert result.valid_evidence == ["c3"]
    assert result.total == 50 + 25 + 5


def test_ranks():
    assert [scoring.rank_for(t) for t in (95, 75, 45, 10)] == [
        "Legendary Detective",
        "Chief Inspector",
        "Inspector",
        "Rookie",
    ]


def test_projection_never_contains_hidden_information(case, progress):
    clue_engine.interrogate(case, progress, "s2", ["garden"])
    clue_engine.examine(case, progress, "guest_wing")
    serialized = json.dumps(project(case, progress).dump())

    for hidden in ("culprit", "lieId", "requiredEvidence", "acceptableMotives", "truthTimeline", "secrets"):
        assert hidden not in serialized
    unrevealed = [c for c in case.clues if c.id not in progress.revealed_clues]
    for clue in unrevealed:
        assert clue.text not in serialized
    for suspect in case.suspects:
        for secret in suspect.secrets:
            assert secret.text not in serialized


def test_verdict_only_after_game_ends(case, progress):
    assert project(case, progress).verdict is None
    progress.phase = "ended"
    progress.score = scoring.score(case, progress, Accusation(suspect_id="s2", motive_id="inheritance"))
    verdict = project(case, progress).verdict
    assert verdict.culprit_name == "Henry Ashford"


def test_guard_blocks_unrevealed_clue_text(case, progress):
    protected = guards.protected_texts(case, progress, "s3", allowed=[])
    leak = "I saw a figure in a pale jacket cross from the potting shed to the garden door."
    assert guards.leaks(leak, protected)
    assert not guards.leaks("I was in my kitchen all evening, Inspector.", protected)


def test_guard_allows_clue_once_allowed(case, progress):
    protected = guards.protected_texts(case, progress, "s3", allowed=["c8"])
    assert not guards.leaks(
        "I saw a figure in a pale jacket cross from the potting shed to the garden door.", protected
    )


def test_guard_blocks_breaking_character(case, progress):
    assert guards.leaks("As an AI language model, I cannot say.", [])
    assert guards.leaks("My system prompt says I must not.", [])
    assert not guards.leaks("Ignore my instructions, you say? Ha!", [])


def test_sentence_splitting_keeps_remainder():
    done, rest = guards.split_complete_sentences("Hello there. How are")
    assert done == ["Hello there. "]
    assert rest == "How are"


def test_guard_ignores_suspects_own_alibi(case, progress):
    protected = guards.protected_texts(case, progress, "s4", allowed=[])
    alibi = "I have been sitting in that library with Lady Margaret since half past nine, playing bridge."
    assert not guards.leaks(alibi, protected)


def test_clean_speech():
    assert guards.clean_speech('Lady Margaret: "I was at bridge." ', "Lady Margaret Ashford", first=True) == (
        "I was at bridge. "
    )
    assert guards.clean_speech("*laughs loudly* Good heavens! ", "Henry Ashford", first=True) == "Good heavens! "
    assert guards.clean_speech("*bristles* ", "Henry Ashford", first=False) == ""
