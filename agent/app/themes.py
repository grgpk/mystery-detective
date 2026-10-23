"""Themes for generated cases: setting ideas, the writing voice, and fair-play rules specific to the genre.

Hand-written archive cases are all Golden Age. The engine never looks at the theme; it shapes only what the
generator writes and how the narrator, judge and game master phrase things.
"""

from dataclasses import dataclass

DEFAULT_THEME = "golden_age"


@dataclass(frozen=True)
class Theme:
    id: str
    label: str
    blurb: str
    voice: str  # how the case is written, for the generator
    genre: str  # how the narrator and judge describe the story they are telling
    authority: str  # who is waiting for the detective's answer
    gathering: str  # where the culprit is unmasked
    fair_play: str  # genre rules that keep the case solvable by deduction
    settings: tuple[str, ...]


THEMES: dict[str, Theme] = {
    t.id: t
    for t in (
        Theme(
            id="golden_age",
            label="Golden Age",
            blurb="Country houses, night trains and grand hotels, 1920s-30s",
            voice="the voice of a 1920s/30s golden-age detective novel",
            genre="a 1920s fair-play murder mystery, in the dry, observant voice of a golden-age detective novel",
            authority="the Chief Constable",
            gathering="the drawing room",
            fair_play="Period technology only: telephones and telegrams, no fingerprint databases or CCTV.",
            settings=(
                "a lighthouse keeper's cottage on a storm-cut Cornish island, 1925",
                "an archaeologists' dig house outside Luxor, 1934",
                "a supra feast in a wine merchant's house in Tbilisi's old town, 1927",
                "a crumbling Venetian palazzo during Carnival, 1929",
                "a transatlantic ocean liner in mid-crossing, 1932",
                "a Highland shooting lodge cut off by floods, 1926",
                "a Hollywood film studio's sound stage after hours, 1938",
                "a Cambridge college on the night of the May Ball, 1931",
                "a remote tea estate bungalow in the Ceylon hills during the monsoon, 1933",
                "a Monte Carlo casino villa during the Grand Prix, 1930",
                "a Swiss sanatorium high above Davos, 1928",
                "a Paris couture house the night before a collection is shown, 1935",
            ),
        ),
        Theme(
            id="sci_fi",
            label="Space station",
            blurb="Orbital habitats and deep-space crews, 2190s",
            voice="the cool, precise voice of classic science fiction (think a locked-room mystery in orbit)",
            genre="a fair-play murder mystery aboard a space station in the 2190s, in the cool, precise voice of "
            "classic science fiction",
            authority="the Station Commander",
            gathering="the observation deck",
            fair_play="Technology must not make the case trivial: no camera footage or logs of the murder itself "
            "(they were wiped, offline, or never existed), no mind-reading, no teleporters. Clues are physical and "
            "testimonial, as in any whodunit.",
            settings=(
                "a mining station orbiting Jupiter's moon Io, 2193",
                "a generation ship's hydroponics deck halfway to Proxima, 2197",
                "a luxury orbital hotel above Earth on its opening night, 2191",
                "a research outpost on the dark side of the Moon during a solar storm, 2194",
                "a deep-space relay station cut off by a comms blackout, 2196",
            ),
        ),
        Theme(
            id="disco",
            label="1970s disco",
            blurb="Glitter balls, recording studios and penthouse parties",
            voice="the voice of a 1970s crime novel: warm, wry and stylish",
            genre="a fair-play murder mystery in the 1970s disco era, in the warm, wry voice of a 1970s crime novel",
            authority="the Captain of Detectives",
            gathering="the empty dance floor",
            fair_play="1970s technology only: landlines, answering machines, Polaroids; no mobile phones. Keep "
            "drugs out of the story; PG-13.",
            settings=(
                "a Manhattan nightclub on the night of its grand reopening, 1977",
                "a Los Angeles recording studio during an all-night session, 1975",
                "a roller-disco rink in Chicago after closing time, 1979",
                "a penthouse party above Miami Beach during a hurricane warning, 1976",
                "a television dance show's studio after the live broadcast, 1978",
            ),
        ),
        Theme(
            id="fantasy",
            label="Fantasy castle",
            blurb="Castles, guilds and courts where magic is real but rule-bound",
            voice="the voice of a classic fantasy novel, grounded and wry",
            genre="a fair-play murder mystery in a fantasy realm, in the grounded, wry voice of a classic fantasy "
            "novel",
            authority="the King's Justiciar",
            gathering="the great hall",
            fair_play="Magic exists but follows stated rules and is never the means of murder or the solution. No "
            "divination, mind-reading, shapeshifting or resurrection. Everything the detective needs is physical "
            "evidence and testimony.",
            settings=(
                "a mountain castle snowed in on the eve of a royal wedding",
                "an alchemists' guildhall during the election of a new guildmaster",
                "a river-barge festival fleet moored outside a walled city",
                "a wizards' academy library locked down after a fire",
                "a dwarven brewery hall on the night of its centenary feast",
            ),
        ),
        Theme(
            id="tbilisi",
            label="Tbilisi old town",
            blurb="Courtyards, sulphur baths and feasts in old Tbilisi, 1900s-1930s",
            voice="the voice of a period detective novel steeped in Georgian life: warm, witty, full of toasts",
            genre="a fair-play murder mystery in old Tbilisi, in the warm, witty voice of a period detective novel",
            authority="the Chief of Police",
            gathering="the courtyard under the vine trellis",
            fair_play="Period technology only. Respect Georgian culture: the tamada, the supra and the toasts are "
            "part of the story, never a joke at its expense.",
            settings=(
                "a supra in a merchant's house with a carved wooden balcony above the Mtkvari, 1912",
                "the Abanotubani sulphur baths on a winter night, 1924",
                "a carpet dealer's courtyard in the old town during the grape harvest, 1908",
                "an opera house dressing room on the night of a premiere, 1931",
                "a winery in Kakheti hosting Tbilisi guests for the rtveli, 1927",
            ),
        ),
    )
}


def theme(theme_id: str | None) -> Theme:
    return THEMES.get(theme_id or DEFAULT_THEME, THEMES[DEFAULT_THEME])
