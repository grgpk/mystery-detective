"""Builders for the game's A2UI v0.9 catalog. The agent may only emit these components.

Components carry ids and short literal props; cards read live details (composure, clue text, statements)
from the AG-UI shared state, so one surface stays correct as the game progresses.
Must match frontend/components/a2ui/definitions.ts.
"""

from typing import Any, Literal

A2UI_VERSION = "v0.9"
CATALOG_ID = "https://lastalibi.game/a2ui/catalog/v1"

Tone = Literal["neutral", "alert", "success"]
Component = dict[str, Any]


def _component(component_id: str, name: str, **props: Any) -> Component:
    return {"id": component_id, "component": name, **{k: v for k, v in props.items() if v is not None}}


def stack(component_id: str, children: list[str], title: str | None = None) -> Component:
    return _component(component_id, "Stack", children=children, title=title)


def case_briefing() -> Component:
    return _component("root", "CaseBriefing")


def suspect_card(suspect_id: str) -> Component:
    return _component(f"suspect-{suspect_id}", "SuspectCard", suspectId=suspect_id)


def location_card(location_id: str) -> Component:
    return _component(f"location-{location_id}", "LocationCard", locationId=location_id)


def clue_card(clue_id: str, component_id: str = "root") -> Component:
    return _component(component_id, "ClueCard", clueId=clue_id)


def narration(text: str, title: str | None = None, tone: Tone = "neutral") -> Component:
    return _component("root", "NarrationBlock", title=title, text=text, tone=tone)


def confront_picker(suspect_id: str) -> Component:
    return _component("root", "ConfrontPicker", suspectId=suspect_id)


def accusation_form() -> Component:
    return _component("root", "AccusationForm")


def verdict_screen() -> Component:
    return _component("root", "VerdictScreen")


def surface_operations(surface_id: str, components: list[Component]) -> list[dict]:
    return [
        {"version": A2UI_VERSION, "createSurface": {"surfaceId": surface_id, "catalogId": CATALOG_ID}},
        {"version": A2UI_VERSION, "updateComponents": {"surfaceId": surface_id, "components": components}},
    ]


def roster(suspect_ids: list[str]) -> list[Component]:
    cards = [suspect_card(s) for s in suspect_ids]
    return [stack("root", [c["id"] for c in cards], title="Suspects"), *cards]


def map_panel(location_ids: list[str]) -> list[Component]:
    cards = [location_card(loc) for loc in location_ids]
    return [stack("root", [c["id"] for c in cards], title="The House"), *cards]


def clue_cards(clue_ids: list[str]) -> list[Component]:
    if len(clue_ids) == 1:
        return [clue_card(clue_ids[0])]
    cards = [clue_card(c, f"clue-{c}") for c in clue_ids]
    return [stack("root", [c["id"] for c in cards]), *cards]
