"""The ONLY path from hidden case + progress to what the browser sees."""

from app.engine import clue_engine, difficulty
from app.engine.clue_engine import mood_for
from app.models.case import CaseFile
from app.models.public import (
    DailyInfo,
    Option,
    Progress,
    PublicClue,
    PublicLocation,
    PublicState,
    PublicStatement,
    PublicSuspect,
    PublicTimelineEvent,
    PublicVictim,
    Verdict,
)


def _timeline(case: CaseFile, progress: Progress) -> list[PublicTimelineEvent]:
    events = [
        PublicTimelineEvent(time=claim.time, suspect=s.id, event=claim.event, source="claimed")
        for s in case.suspects
        if s.id in progress.interrogated
        for claim in s.claimed_timeline
    ]
    for clue_id in progress.revealed_clues:
        tle = case.clue(clue_id).timeline_event
        if tle:
            events.append(PublicTimelineEvent(time=tle.time, suspect=tle.suspect, event=tle.event, source="verified"))
    return sorted(events, key=lambda e: e.time)


def public_clue(case: CaseFile, progress: Progress, clue_id: str) -> PublicClue:
    clue = case.clue(clue_id)
    return PublicClue(
        id=clue.id, title=clue.title, text=clue.text, location=clue.location, is_new=clue_id in progress.new_clues
    )


def verdict(case: CaseFile, progress: Progress) -> Verdict | None:
    if progress.phase != "ended" or progress.score is None:
        return None
    missed = [c for c in case.clues if c.id not in progress.revealed_clues and not c.is_red_herring]
    return Verdict(
        score=progress.score,
        culprit_name=case.suspect(case.culprit).name,
        motive=case.motive.text,
        true_timeline=[
            PublicTimelineEvent(time=e.time, suspect=e.suspect, event=e.event, source="verified")
            for e in case.truth_timeline
        ],
        found_clues=list(progress.revealed_clues),
        missed_clues=[
            PublicClue(id=c.id, title=c.title, text=c.text, location=c.location, is_new=False) for c in missed
        ],
        promotion=progress.promotion,
    )


def project(case: CaseFile, progress: Progress) -> PublicState:
    return PublicState(
        case_id=case.case_id,
        title=case.setting.title,
        place=case.setting.place,
        briefing=case.briefing,
        phase=progress.phase,
        turns_left=progress.turns_left,
        max_turns=clue_engine.max_turns(case, progress),
        difficulty=progress.difficulty,
        hint_cost=difficulty.settings(progress.difficulty).hint_cost,
        victim=PublicVictim(
            name=case.victim.name,
            cause_of_death=case.victim.cause_of_death,
            time_of_death=case.victim.time_of_death,
            crime_scene=case.victim.crime_scene,
        ),
        suspects=[
            PublicSuspect(
                id=s.id,
                name=s.name,
                role=s.role,
                appearance=s.appearance,
                composure=progress.composure[s.id],
                mood=mood_for(progress.composure[s.id]),
            )
            for s in case.suspects
        ],
        locations=[
            PublicLocation(
                id=loc.id,
                label=loc.label,
                description=loc.description,
                examined=loc.id in progress.examined_locations,
            )
            for loc in case.setting.locations
        ],
        topics=[Option(id=t.id, label=t.label) for t in case.topics],
        motive_options=[Option(id=m.id, label=m.label) for m in case.motive_options],
        clues=[public_clue(case, progress, cid) for cid in progress.revealed_clues],
        statements=[PublicStatement(id=s.id, suspect=s.suspect, text=s.text, kind=s.kind) for s in progress.statements],
        timeline=_timeline(case, progress),
        conversation=progress.conversation,
        board=progress.board,
        last_contradiction=progress.last_contradiction,
        verdict=verdict(case, progress),
        daily=(
            DailyInfo(date=progress.daily_date, leaderboard_name=progress.leaderboard_name)
            if progress.daily_date
            else None
        ),
    )
