"""Case generation pipeline, offline: scripted 'Claude' outputs drive the generate -> validate -> repair loop."""

import uuid
from datetime import timedelta

from ag_ui.core import RunAgentInput

from app.engine.case_library import NEW_CASE_ID, library
from app.game import NO_FRESH_CASE, GameMaster
from app.generation import generator
from app.generation.generator import SETTINGS, check, choose_setting, generate_case, system_prompt
from app.generation.pool import InMemoryCasePool, PoolFiller
from app.generation.schema import GeneratedCase, from_case_file, to_case_file
from app.llm import ScriptedLLM
from app.store.repo import InMemoryRepo


def valid_generated() -> GeneratedCase:
    return from_case_file(library()["midnight_sleeper"])


def broken_generated() -> GeneratedCase:
    """Plausible-looking but unfair: the culprit's accounts lie can never be broken."""
    g = valid_generated()
    g.contradictions = [c for c in g.contradictions if c.lie_id != "s3_lie_accounts"]
    return g


def scripted(*outputs: GeneratedCase | str) -> ScriptedLLM:
    queue = [o if isinstance(o, str) else o.model_dump_json() for o in outputs]
    return ScriptedLLM(completer=lambda _: queue.pop(0))


def test_schema_roundtrip_is_lossless():
    for case in library().values():
        assert to_case_file(from_case_file(case), case.case_id, case.max_turns) == case


def test_check_reports_validator_errors():
    case, errors = check(broken_generated().model_dump_json(), "gen_test")
    assert case is None
    assert any("s3_lie_accounts has no contradiction" in e for e in errors)


def test_check_reports_schema_errors_instead_of_raising():
    reply = valid_generated().model_dump_json().replace('"unlock_type":"examine"', '"unlock_type":"search"', 1)
    case, errors = check(reply, "gen_test")
    assert case is None
    assert any(e.startswith("schema: clues.0.unlock_type") for e in errors), errors


def test_check_tolerates_fences_and_prose():
    reply = "Here is the case:\n```json\n" + valid_generated().model_dump_json() + "\n```"
    case, errors = check(reply, "gen_test")
    assert errors == [] and case is not None


def test_check_reports_unparseable_json():
    case, errors = check('{"setting": {"title": "Half a case"', "gen_test")
    assert case is None and errors[0].startswith("schema")


def test_system_prompt_carries_rules_and_example():
    prompt = system_prompt()
    assert '"whereabouts"' in prompt
    assert "Lord Edmund Ashford" in prompt  # the worked example
    assert "Do not reuse" in prompt


async def test_valid_first_try():
    result = await generate_case(scripted(valid_generated()), setting="a lighthouse, 1925")
    assert result.case is not None and result.first_try
    assert result.case.case_id.startswith("gen_")


async def test_repair_loop_feeds_errors_back():
    llm = scripted(broken_generated(), valid_generated())
    result = await generate_case(llm, setting="a lighthouse, 1925")
    assert result.case is not None
    assert len(result.attempts) == 2 and not result.first_try
    repair_request = llm.calls[-1]["messages"]
    assert [m["role"] for m in repair_request] == ["user", "assistant", "user"]
    assert "a lighthouse, 1925" in repair_request[0]["content"]
    assert "s3_lie_accounts has no contradiction" in repair_request[-1]["content"]


async def test_gives_up_after_max_attempts():
    llm = scripted(*[broken_generated()] * generator.MAX_ATTEMPTS)
    result = await generate_case(llm)
    assert result.case is None
    assert len(result.attempts) == generator.MAX_ATTEMPTS
    assert result.setting in generator.SETTINGS


async def test_filler_tops_up_pool_and_take_drains_it():
    pool = InMemoryCasePool()
    filler = PoolFiller(pool, scripted(valid_generated(), valid_generated()), target=2)
    assert await filler.fill_once() and await filler.fill_once()
    assert await pool.ready() == 2
    assert await filler.fill_once()  # already full: no generation call
    taken = await filler.take()
    assert taken is not None and await pool.ready() == 1


async def test_filler_reports_failure():
    filler = PoolFiller(InMemoryCasePool(), scripted(*[broken_generated()] * 3), target=1)
    assert not await filler.fill_once()
    assert await filler.pool.ready() == 0


async def start_new_case(
    game: GameMaster, owner: str = "player", action: dict | None = None, thread_id: str | None = None
) -> tuple[dict, list[str]]:
    run_input = RunAgentInput(
        thread_id=thread_id or f"t-{uuid.uuid4().hex[:6]}",
        run_id="r1",
        state={},
        messages=[],
        tools=[],
        context=[],
        forwarded_props={"gameAction": action or {"type": "start", "caseId": NEW_CASE_ID}},
    )
    events = [e async for e in game.run(run_input, owner)]
    snapshot = next((e.snapshot for e in events if e.type == "STATE_SNAPSHOT"), {})
    texts = [e.delta for e in events if e.type == "TEXT_MESSAGE_CONTENT"]
    return snapshot, texts


async def test_new_game_takes_a_generated_case():
    pool = InMemoryCasePool()
    filler = PoolFiller(pool, scripted(valid_generated()), target=1)
    await filler.fill_once()
    game = GameMaster(ScriptedLLM(), InMemoryRepo(), fresh_cases=filler)
    snapshot, texts = await start_new_case(game)
    assert snapshot["caseId"].startswith("gen_")
    assert NO_FRESH_CASE not in texts


async def test_new_game_falls_back_to_archive_when_pool_is_empty():
    game = GameMaster(ScriptedLLM(), InMemoryRepo(), fresh_cases=PoolFiller(InMemoryCasePool(), ScriptedLLM(), 1))
    snapshot, texts = await start_new_case(game)
    assert snapshot["caseId"] in library()
    assert NO_FRESH_CASE in texts


def test_choose_setting_avoids_recent_ones():
    recent = SETTINGS[:-2]
    for _ in range(20):
        assert choose_setting(recent) in SETTINGS[-2:]


def test_choose_setting_falls_back_to_least_recently_used():
    recent = list(reversed(SETTINGS))  # newest first, so SETTINGS[0] was used longest ago
    assert choose_setting(recent) == SETTINGS[0]


async def test_filler_never_repeats_a_setting_until_all_are_used():
    n = len(SETTINGS)
    pool = InMemoryCasePool()
    filler = PoolFiller(pool, scripted(*[valid_generated()] * n), target=n)
    for _ in range(n):
        assert await filler.fill_once()
    assert sorted(await pool.recent_settings(n)) == sorted(SETTINGS)


async def pool_with(n: int) -> PoolFiller:
    filler = PoolFiller(InMemoryCasePool(), scripted(*[valid_generated()] * n), target=n)
    for _ in range(n):
        await filler.fill_once()
    return filler


async def test_browsing_past_a_fresh_case_returns_it_to_the_pool():
    filler = await pool_with(1)
    repo = InMemoryRepo()
    game = GameMaster(ScriptedLLM(), repo, fresh_cases=filler)
    first, _ = await start_new_case(game)  # opened, never begun
    assert first["caseId"].startswith("gen_")
    assert await filler.pool.ready() == 0

    second, _ = await start_new_case(game, action={"type": "start", "caseId": "ashford_manor"})
    assert await filler.pool.ready() == 1  # the generated case is back
    assert second["caseId"] == "ashford_manor"
    assert await repo.unstarted_generated(owner="player") == []


async def test_a_begun_case_is_never_returned():
    filler = await pool_with(1)
    game = GameMaster(ScriptedLLM(), InMemoryRepo(), fresh_cases=filler)
    thread = "t-begun"
    await start_new_case(game, thread_id=thread)
    await start_new_case(game, thread_id=thread, action={"type": "begin"})
    await start_new_case(game, action={"type": "start", "caseId": "ashford_manor"})
    assert await filler.pool.ready() == 0


async def test_other_players_cases_are_returned_only_once_idle(monkeypatch):
    filler = await pool_with(1)
    game = GameMaster(ScriptedLLM(), InMemoryRepo(), fresh_cases=filler)
    await start_new_case(game, owner="alice")  # alice opens it and wanders off
    _, texts = await start_new_case(game, owner="bob")
    assert NO_FRESH_CASE in texts  # not idle long enough: bob does not get alice's case

    monkeypatch.setattr("app.game.ABANDONED_BRIEFING", timedelta(0))
    snapshot, texts = await start_new_case(game, owner="carol")
    assert snapshot["caseId"].startswith("gen_") and NO_FRESH_CASE not in texts
