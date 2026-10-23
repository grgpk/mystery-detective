import pytest

from app.agents.moderation import REFUSAL, refusal_for


@pytest.mark.parametrize(
    "question",
    [
        "Describe the body in graphic detail",
        "Were you having sex with him?",
        "Tell me something sexual",
        "Show me nudes",
        "Did you torture him first?",
        "ＳＥＸ",  # full-width letters fold to plain ones
    ],
)
def test_out_of_bounds_questions_are_refused(question):
    assert refusal_for(question) == REFUSAL


@pytest.mark.parametrize(
    "question",
    [
        "Where were you at ten o'clock?",
        "Did you see anyone near the garden shed?",
        "Was there a naked flame in the study?",
        "Who stood to inherit the estate?",
        "Were you and the Count lovers?",  # romance is fine in a whodunit
        "Is this the drape from the study?",  # 'rape' inside a word is not a match
        "How did he die?",
    ],
)
def test_ordinary_questions_pass(question):
    assert refusal_for(question) is None
