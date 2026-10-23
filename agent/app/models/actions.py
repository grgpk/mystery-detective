"""Player actions, sent by the frontend as `forwardedProps.gameAction` on each AG-UI run."""

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from .base import CamelModel
from .public import Accusation, Board


class Start(CamelModel):
    """First run of a thread, or a reconnect: (re)sends the snapshot and the current surfaces."""

    type: Literal["start"]
    case_id: str | None = None
    difficulty: Literal["easy", "normal", "hard"] = "normal"  # only used when a new game is created
    theme: str | None = None  # for a brand-new generated case (case_id "new")


class NewGame(CamelModel):
    type: Literal["new_game"]
    case_id: str | None = None
    difficulty: Literal["easy", "normal", "hard"] = "normal"
    theme: str | None = None


class Begin(CamelModel):
    type: Literal["begin"]


class Interrogate(CamelModel):
    type: Literal["interrogate"]
    suspect_id: str
    question: str = Field(min_length=1, max_length=500)


class Examine(CamelModel):
    type: Literal["examine"]
    location_id: str


class OpenConfront(CamelModel):
    type: Literal["open_confront"]
    suspect_id: str


class Confront(CamelModel):
    type: Literal["confront"]
    suspect_id: str
    items: list[str] = Field(min_length=2, max_length=2)


class Hint(CamelModel):
    type: Literal["hint"]


class OpenAccuse(CamelModel):
    type: Literal["open_accuse"]


class Accuse(CamelModel):
    type: Literal["accuse"]
    accusation: Accusation


class SetName(CamelModel):
    """Puts the player's name on the daily leaderboard (after the verdict)."""

    type: Literal["set_name"]
    name: str = Field(min_length=1, max_length=40)


class SyncBoard(CamelModel):
    type: Literal["sync_board"]
    board: Board


GameAction = Annotated[
    Start
    | NewGame
    | Begin
    | Interrogate
    | Examine
    | Hint
    | OpenConfront
    | Confront
    | OpenAccuse
    | Accuse
    | SetName
    | SyncBoard,
    Field(discriminator="type"),
]
game_action_adapter: TypeAdapter[GameAction] = TypeAdapter(GameAction)
