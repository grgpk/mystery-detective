import pytest

from app.agents.narrator import judge_system, narrator_system
from app.engine import hints
from app.engine.case_library import NEW_CASE_ID, library
from app.game import NO_FRESH_CASE, GameMaster
from app.generation.generator import choose_setting, generate_case, system_prompt
from app.generation.pool import InMemoryCasePool, PoolFiller
from app.llm import ScriptedLLM
from app.store.repo import InMemoryRepo
from app.themes import DEFAULT_THEME, THEMES, theme
from tests.test_generation import scripted, start_new_case, valid_generated


def test_themes_are_complete():
    assert DEFAULT_THEME in THEMES and len(THEMES) >= 5
    for t in THEMES.values():
        assert len(t.settings) >= 5 and len(set(t.settings)) == len(t.settings)
        assert all([t.label, t.blurb, t.voice, t.genre, t.authority, t.gathering, t.fair_play])
    assert theme("no-such-theme").id == DEFAULT_THEME


def test_each_theme_gets_its_own_prompt():
    prompts = {t: system_prompt(t) for t in THEMES}
    assert len(set(prompts.values())) == len(THEMES)
    sci_fi = prompts["sci_fi"]
    assert THEMES["sci_fi"].voice in sci_fi and "camera footage" in sci_fi
    assert "Lord Edmund Ashford" in sci_fi  # the worked example is shared
    assert "1920s/30s detective novel" not in sci_fi


async def test_generated_case_carries_its_theme():
    result = await generate_case(scripted(valid_generated()), theme_id="fantasy")
    assert result.case is not None and result.case.theme == "fantasy"
    assert result.setting in THEMES["fantasy"].settings


def test_settings_rotate_within_a_theme():
    options = THEMES["disco"].settings
    assert choose_setting(list(options[:-1]), theme_id="disco") == options[-1]


@pytest.fixture
async def pool_with_one_sci_fi():
    filler = PoolFiller(InMemoryCasePool(), scripted(valid_generated()), targets={DEFAULT_THEME: 0, "sci_fi": 1})
    assert await filler.most_needed() == "sci_fi"
    assert await filler.fill_once()
    assert await filler.most_needed() is None
    return filler


async def test_pool_keeps_themes_apart(pool_with_one_sci_fi):
    filler = pool_with_one_sci_fi
    assert (await filler.pool.ready("sci_fi"), await filler.pool.ready(DEFAULT_THEME)) == (1, 0)
    assert await filler.take(DEFAULT_THEME) is None
    case = await filler.take("sci_fi")
    assert case is not None and case.theme == "sci_fi"


async def test_new_game_gets_the_requested_theme_or_the_archive(pool_with_one_sci_fi):
    game = GameMaster(ScriptedLLM(), InMemoryRepo(), fresh_cases=pool_with_one_sci_fi)
    _, texts = await start_new_case(game, owner="a", action={"type": "start", "caseId": NEW_CASE_ID, "theme": "disco"})
    assert NO_FRESH_CASE in texts  # no disco case ready: archive, never a different theme
    state, texts = await start_new_case(
        game, owner="b", action={"type": "start", "caseId": NEW_CASE_ID, "theme": "sci_fi"}
    )
    assert state["caseId"].startswith("gen_") and NO_FRESH_CASE not in texts


def test_theme_voice_reaches_narration_and_hints():
    case = library()["ashford_manor"].model_copy(update={"theme": "sci_fi"})
    assert "space station" in narrator_system(case)
    assert "the observation deck" in judge_system(case)
    assert "the Station Commander" in hints.hint_text(case, hints.Step("accuse"), explicit=True)
    golden = library()["ashford_manor"]
    assert "golden-age" in narrator_system(golden) and "the drawing room" in judge_system(golden)
