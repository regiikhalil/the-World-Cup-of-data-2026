from __future__ import annotations

import json
import textwrap
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "output" / "visuals"
OUT.mkdir(parents=True, exist_ok=True)

EVENTS_PATH = DATA / "events.json"
PLAYERS_PATH = DATA / "player_match_stats.json"
ENGLAND_FLAG = ROOT / "flags" / "Flag_of_England.svg.png"
NORWAY_FLAG = ROOT / "flags" / "Flag_of_Norway.svg.png"
HEADSHOTS = {
    "Jude Bellingham": ROOT / "player_headshots" / "england_bellingham_white.png",
    "Elliot Anderson": ROOT / "player_headshots" / "england_anderson_white.png",
    "John Stones": ROOT / "player_headshots" / "england_stones_white.png",
    "Marc Guehi": ROOT / "player_headshots" / "england_guehi_white.png",
    "Bukayo Saka": ROOT / "player_headshots" / "england_saka_white.png",
    "Sander Berge": ROOT / "player_headshots" / "norway_berge_white.png",
    "Martin Ødegaard": ROOT / "player_headshots" / "norway_odegaard_white.png",
    "Kristoffer Ajer": ROOT / "player_headshots" / "norway_ajer_white.png",
    "Erling Håland": ROOT / "player_headshots" / "norway_haaland_white.png",
    "Julian Ryerson": ROOT / "player_headshots" / "norway_ryerson_white.png",
    "Andreas Schjelderup": ROOT / "player_headshots" / "norway_schjelderup_white.png",
}
TITLE_FONT = ROOT / "fonts" / "BarlowCondensed-Bold.ttf"
BODY_FONT = ROOT / "fonts" / "OpenSans-Regular.ttf"


ENGLAND = "#D62728"
NORWAY = "#1F77B4"
ENGLAND_DARK = "#C91F26"
NORWAY_DARK = "#176BA8"
ENGLAND_TINT = "#FFF7F8"
NORWAY_TINT = "#F5FAFF"
ENGLAND_STRIP = "#FBE2E5"
NORWAY_STRIP = "#DDECF8"
ORANGE = "#FF7F0E"
GREEN = "#2CA02C"
INK = "#27313D"
MUTED = "#626B76"
GRID = "#D8DEE8"
PALE = "#F5F8FB"
WHITE = "#FFFFFF"
BLACK = "#111111"
STYLE_BLUE = "#8EB9FF"


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


F_TITLE = font(TITLE_FONT, 70)
F_SUB = font(TITLE_FONT, 34)
F_H2 = font(TITLE_FONT, 38)
F_H3 = font(TITLE_FONT, 29)
F_ROLE = font(TITLE_FONT, 25)
F_VALUE = font(TITLE_FONT, 48)
F_ROW_NAME = font(TITLE_FONT, 42)
F_ROW_ROLE = font(TITLE_FONT, 28)
F_PRIMARY_VALUE = font(TITLE_FONT, 74)
F_PRIMARY_LABEL = font(TITLE_FONT, 26)
F_SUPPORT = font(TITLE_FONT, 26)
F_CARD_NOTE = font(BODY_FONT, 20)
F_LABEL = font(TITLE_FONT, 23)
F_BODY = font(BODY_FONT, 18)
F_SMALL = font(BODY_FONT, 15)
F_TINY = font(TITLE_FONT, 16)
F_FOOT = font(BODY_FONT, 23)
F_LEGEND = font(TITLE_FONT, 34)


def text(draw: ImageDraw.ImageDraw, xy, value: str, fill=INK, font_obj=F_BODY) -> None:
    draw.text(xy, value, fill=fill, font=font_obj)


def tsize(draw: ImageDraw.ImageDraw, value: str, font_obj=F_BODY) -> tuple[int, int]:
    box = draw.textbbox((0, 0), value, font=font_obj)
    return box[2] - box[0], box[3] - box[1]


def wrapped(draw: ImageDraw.ImageDraw, xy, value: str, width: int, fill=MUTED, font_obj=F_SMALL, gap=5) -> int:
    x, y = xy
    for line in textwrap.wrap(value, width):
        text(draw, (x, y), line, fill, font_obj)
        y += tsize(draw, line, font_obj)[1] + gap
    return y


def paste_flag(base: Image.Image, path: Path, x: int, y: int, w: int, h: int, trim: bool = True) -> None:
    flag = Image.open(path).convert("RGBA")
    if trim:
        bg = Image.new("RGBA", flag.size, (255, 255, 255, 255))
        diff = Image.eval(ImageChops.difference(flag, bg), lambda px: 255 if px > 12 else 0)
        bbox = diff.getbbox()
        if bbox:
            flag = flag.crop(bbox)
    flag.thumbnail((w, h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    canvas.alpha_composite(flag, ((w - flag.width) // 2, (h - flag.height) // 2))
    base.paste(canvas, (x, y), canvas)


def paste_flag_cover(base: Image.Image, path: Path, x: int, y: int, w: int, h: int) -> None:
    flag = Image.open(path).convert("RGBA")
    ratio = max(w / flag.width, h / flag.height)
    resized = flag.resize((int(flag.width * ratio), int(flag.height * ratio)), Image.Resampling.LANCZOS)
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    cropped = resized.crop((left, top, left + w, top + h))
    base.paste(cropped, (x, y), cropped)


def paste_headshot(base: Image.Image, draw: ImageDraw.ImageDraw, path: Path, x: int, y: int, size: int, color: str) -> None:
    portrait = Image.open(path).convert("RGBA")
    side = min(portrait.size)
    left = (portrait.width - side) // 2
    top = (portrait.height - side) // 2
    portrait = portrait.crop((left, top, left + side, top + side)).resize((size, size), Image.Resampling.LANCZOS)

    mask_scale = 4
    mask = Image.new("L", (size * mask_scale, size * mask_scale), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, size * mask_scale - 1, size * mask_scale - 1), fill=255)
    mask = mask.resize((size, size), Image.Resampling.LANCZOS)

    ring_pad = 4
    draw.ellipse((x - ring_pad, y - ring_pad, x + size + ring_pad, y + size + ring_pad), fill=WHITE, outline="#98A6B6", width=4)
    base.paste(portrait, (x, y), mask)


def get_player(players: list[dict], name: str) -> dict:
    for player in players:
        if player.get("player_name") == name:
            return player
    raise ValueError(f"Missing player: {name}")


def event_shot_summary(events: list[dict], player_name: str) -> tuple[int, float]:
    shots = [
        event
        for event in events
        if event.get("player", {}).get("name") == player_name
        and event.get("type", {}).get("name") == "Shot"
    ]
    xg = sum(float((event.get("shot") or {}).get("statsbomb_xg") or 0) for event in shots)
    return len(shots), xg


def fmt_int(row: dict, key: str) -> str:
    return str(int(row[key]))


def fmt_float(row: dict, key: str, places: int = 2) -> str:
    return f"{float(row[key]):.{places}f}"


def fmt_pass_comp(row: dict) -> str:
    return f"{fmt_int(row, 'player_match_successful_passes')}/{fmt_int(row, 'player_match_passes')}"


def draw_legend(img: Image.Image, draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """Draw a bold two-column legend in the top-right title area."""
    draw.rounded_rectangle((x, y, x + 315, y + 112), radius=8, fill=PALE, outline=GRID, width=1)

    row_y = y + 17
    draw.ellipse((x + 20, row_y + 8, x + 46, row_y + 34), fill=NORWAY)
    draw.rounded_rectangle((x + 64, row_y + 1, x + 126, row_y + 39), radius=3, fill=WHITE, outline=GRID, width=1)
    paste_flag_cover(img, NORWAY_FLAG, x + 68, row_y + 5, 54, 30)
    text(draw, (x + 145, row_y + 0), "Norway", INK, F_LEGEND)

    row_y += 50
    draw.ellipse((x + 20, row_y + 8, x + 46, row_y + 34), fill=ENGLAND)
    draw.rounded_rectangle((x + 64, row_y + 1, x + 126, row_y + 39), radius=3, fill=WHITE, outline=GRID, width=1)
    paste_flag(img, ENGLAND_FLAG, x + 68, row_y + 5, 54, 30, trim=False)
    text(draw, (x + 145, row_y + 0), "England", INK, F_LEGEND)

# def draw_column_header(img: Image.Image, draw: ImageDraw.ImageDraw, x: int, y: int, w: int, team: str, color: str, flag: Path) -> None:
#     draw.rounded_rectangle((x, y, x + w, y + 58), radius=8, fill=PALE, outline=GRID, width=1)
#     draw.ellipse((x + 22, y + 18, x + 44, y + 40), fill=color)
#     draw.rounded_rectangle((x + 62, y + 13, x + 118, y + 45), radius=3, fill=WHITE, outline=GRID, width=1)
#     paste_flag(img, flag, x + 66, y + 17, 48, 24, trim=False)
#     text(draw, (x + 136, y + 10), team, INK, F_H2)
#     text(draw, (x + w - 218, y + 20), "standout player profiles", MUTED, F_SMALL)


def draw_profile_row(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    name: str,
    role: str,
    primary: tuple[str, str],
    support: str,
    note: str,
    color: str,
    flag: Path,
    headshot: Path | None = None,
) -> None:
    card_fill = ENGLAND_TINT if color == ENGLAND else NORWAY_TINT
    strip_fill = ENGLAND_STRIP if color == ENGLAND else NORWAY_STRIP
    strong_color = ENGLAND_DARK if color == ENGLAND else NORWAY_DARK

    draw.rounded_rectangle((x + 3, y + 5, x + w + 3, y + h + 5), radius=5, fill="#F1F4F8")
    draw.rounded_rectangle((x, y, x + w, y + h), radius=5, fill=card_fill, outline="#CBD5E1", width=1)
    draw.line((x + 1, y + 3, x + w - 1, y + 3), fill=strong_color, width=8)
    if headshot and headshot.exists():
        paste_headshot(img, draw, headshot, x + 14, y + 35, 150, color)
    else:
        draw.rounded_rectangle((x + 40, y + 58, x + 134, y + 116), radius=3, fill=WHITE, outline=GRID, width=1)
        paste_flag(img, flag, x + 48, y + 68, 78, 38, trim=False)
    text(draw, (x + 178, y + 28), name, INK, F_ROW_NAME)
    text(draw, (x + 180, y + 77), role.upper(), strong_color, F_ROW_ROLE)
    text(draw, (x + 180, y + 114), note, INK, F_CARD_NOTE)

    primary_value, primary_label = primary
    primary_right = x + w - 44
    value_w, _ = tsize(draw, primary_value, F_PRIMARY_VALUE)
    label = primary_label.upper()
    label_w, _ = tsize(draw, label, F_PRIMARY_LABEL)
    value_x = primary_right - value_w
    label_x = primary_right - label_w
    text(draw, (value_x, y + 23), primary_value, strong_color, F_PRIMARY_VALUE)
    text(draw, (label_x, y + 94), label, MUTED, F_PRIMARY_LABEL)

    draw.rounded_rectangle((x + 178, y + h - 56, x + w - 72, y + h - 17), radius=5, fill=strip_fill, outline=GRID, width=1)
    text(draw, (x + 196, y + h - 54), support, MUTED, F_SUPPORT)


def main() -> None:
    players = json.loads(PLAYERS_PATH.read_text())

    bellingham = get_player(players, "Jude Bellingham")
    anderson = get_player(players, "Elliot Anderson")
    stones = get_player(players, "John Stones")
    berge = get_player(players, "Sander Berge")
    odegaard = get_player(players, "Martin Ødegaard")
    haaland = get_player(players, "Erling Håland")

    img = Image.new("RGB", (1600, 1100), WHITE)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 1599, 1099), outline=STYLE_BLUE, width=18)

    text(draw, (95, 44), "Influence Profiles", INK, F_TITLE)
    text(draw, (95, 114), "Six story drivers behind the decisive windows and chance profile", MUTED, F_SUB)
    draw_legend(img, draw, 1190, 44)

    col_y, col_w = 178, 690
    left_x, right_x = 95, 815
    # draw_column_header(img, draw, left_x, col_y, col_w, "England", ENGLAND, ENGLAND_FLAG)
    # draw_column_header(img, draw, right_x, col_y, col_w, "Norway", NORWAY, NORWAY_FLAG)

    row_y, row_h, row_gap = col_y + 34, 220, 24
    england_rows = [
        (
            "Jude Bellingham",
            "Decisive finisher",
            (fmt_int(bellingham, "player_match_goals"), "goals"),
            f"{fmt_int(bellingham, 'player_match_np_shots')} shots | {fmt_float(bellingham, 'player_match_np_xg')} np xG | {fmt_int(bellingham, 'player_match_touches_inside_box')} box touches",
            "Finished England's two decisive windows.",
        ),
        (
            "Elliot Anderson",
            "Main connector",
            (fmt_int(anderson, "player_match_deep_progressions"), "deep prog."),
            f"{fmt_pass_comp(anderson)} passing | {fmt_int(anderson, 'player_match_ball_recoveries')} recoveries | {fmt_int(anderson, 'player_match_pressure_regains')} regains",
            "Linked possession, territory and regains.",
        ),
        (
            "John Stones",
            "Defensive stabiliser",
            (fmt_float(stones, "player_match_obv"), "OBV"),
            f"{fmt_int(stones, 'player_match_clearances')} clearances | {fmt_int(stones, 'player_match_ball_recoveries')} recoveries | {fmt_int(stones, 'player_match_successful_aerials')}/{fmt_int(stones, 'player_match_aerials')} aerials",
            "Kept Norway's striker volume contained.",
        ),
    ]
    norway_rows = [
        (
            "Sander Berge",
            "Balance point",
            (fmt_pass_comp(berge), "passing"),
            f"{fmt_int(berge, 'player_match_deep_progressions')} deep prog. | {fmt_int(berge, 'player_match_ball_recoveries')} recoveries | {fmt_float(berge, 'player_match_xgchain')} xGChain",
            "Connected the block to higher spells.",
        ),
        (
            "Martin Ødegaard",
            "Creative hub",
            (fmt_int(odegaard, "player_match_deep_progressions"), "deep prog."),
            f"{fmt_pass_comp(odegaard)} passing | {fmt_int(odegaard, 'player_match_key_passes')} key passes | {fmt_int(odegaard, 'player_match_pressures')} pressures",
            "Directed progression and pressure.",
        ),
        (
            "Erling Håland",
            "Contained volume",
            (fmt_int(haaland, "player_match_np_shots"), "shots"),
            f"{fmt_int(haaland, 'player_match_goals')} goals | {fmt_float(haaland, 'player_match_np_xg')} np xG | {fmt_int(haaland, 'player_match_successful_aerials')}/{fmt_int(haaland, 'player_match_aerials')} aerials",
            "Present, but denied decisive chances.",
        ),
    ]

    for idx, (name, role, primary, support, note) in enumerate(england_rows):
        draw_profile_row(
            img,
            draw,
            left_x,
            row_y + idx * (row_h + row_gap),
            col_w,
            row_h,
            name,
            role,
            primary,
            support,
            note,
            ENGLAND,
            ENGLAND_FLAG,
            HEADSHOTS.get(name),
        )
    for idx, (name, role, primary, support, note) in enumerate(norway_rows):
        draw_profile_row(
            img,
            draw,
            right_x,
            row_y + idx * (row_h + row_gap),
            col_w,
            row_h,
            name,
            role,
            primary,
            support,
            note,
            NORWAY,
            NORWAY_FLAG,
            HEADSHOTS.get(name),
        )

    footer_y = row_y + 3 * row_h + 2 * row_gap + 62
    draw.line((95, footer_y, 1505, footer_y), fill="#D8DEE8", width=1)
    text(draw, (95, footer_y + 10), "Pass pairs show completed/attempted.", BLACK, F_FOOT)
    text(
        draw,
        (95, footer_y + 37),
        "np xG = non-penalty expected goals | xGChain = possessions a player was involved in that ended in a shot.",
        BLACK,
        F_FOOT,
    )

    out = OUT / "influence_profiles.png"
    img.save(out, "PNG", optimize=True)
    print(f"Saved {out}")
    print("Validation")
    for row in england_rows:
        print("England:", row[0], row[2], row[3], row[4])
    for row in norway_rows:
        print("Norway:", row[0], row[2], row[3], row[4])


if __name__ == "__main__":
    main()
