from __future__ import annotations

"""Build a transparent StatsBomb-only match momentum chart.

This script is inspired by the public concept of a "match momentum" visual:
show a rolling sense of which team is creating the more dangerous attacking
activity. It does not attempt to recreate the Bundesliga Match Fact formula,
which is proprietary. Instead, it builds a documented index from event fields
available in this project:

- shots, StatsBomb xG and shot execution xG
- goals
- completed passes/carries into the box or final third
- box receipts
- corners and crosses
- attacking-third fouls won
- high regains
- positive OBV

The result is a net momentum value:

    England rolling threat - Norway rolling threat

Positive bars therefore favor England. Negative bars favor Norway. The chart is
kept deliberately simple: a single histogram layer plus match-event markers.
"""

import json
import math
import textwrap
from collections import deque
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "output" / "visuals"
OUT.mkdir(parents=True, exist_ok=True)

# Project inputs. The script only reads from the StatsBomb event file plus
# local design assets supplied in the project folder.
EVENTS_PATH = DATA / "events.json"
ENGLAND_FLAG = ROOT / "flags" / "Flag_of_England.svg.png"
NORWAY_FLAG = ROOT / "flags" / "Flag_of_Norway.svg.png"
BALL_MARKER = ROOT / "flags" / "trionda_ball_marker.png"
TITLE_FONT = ROOT / "fonts" / "BarlowCondensed-Bold.ttf"
BODY_FONT = ROOT / "fonts" / "OpenSans-Regular.ttf"

# Colour tokens follow the Sports Data Campus palette/style guide direction.
ENGLAND = "#D62728"
NORWAY = "#1F77B4"
ORANGE = "#FF7F0E"
GREEN = "#2CA02C"
PURPLE = "#9467BD"
BREAK = "#F59E0B"
INK = "#27313D"
MUTED = "#626B76"
GRID = "#D8DEE8"
PALE = "#F5F8FB"
WHITE = "#FFFFFF"
BLACK = "#111111"
STYLE_BLUE = "#8EB9FF"

TEAMS = ["England", "Norway"]
HYDRATION_MINUTES = [23, 70]

# Editorial period boundaries used for the chart timeline. These keep the
# plotted x-axis monotonic when StatsBomb period clocks overlap in stoppage
# time, for example period 2 ending at 90+9 while period 3 starts from 90.
PERIOD_CLOCK_START = {1: 0.0, 2: 45.0, 3: 90.0, 4: 105.0}
PERIOD_TIMELINE_START = {1: 0.0, 2: 48.0, 3: 102.0, 4: 121.0}
MATCH_END_TIMELINE = 139


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    """Load a project font at a fixed pixel size."""
    return ImageFont.truetype(str(path), size=size)


F_TITLE = font(TITLE_FONT, 62)
F_SUB = font(TITLE_FONT, 32)
F_H2 = font(TITLE_FONT, 34)
F_H3 = font(TITLE_FONT, 26)
F_LABEL = font(TITLE_FONT, 22)
F_LEGEND = font(TITLE_FONT, 28)
F_VALUE = font(TITLE_FONT, 30)
F_BODY = font(BODY_FONT, 17)
F_SMALL = font(TITLE_FONT, 23)
F_TAG = font(TITLE_FONT, 28)
F_TINY = font(BODY_FONT, 12)


def text(draw: ImageDraw.ImageDraw, xy, value: str, fill=INK, font_obj=F_BODY) -> None:
    """Small wrapper so text calls read consistently across the script."""
    draw.text(xy, value, fill=fill, font=font_obj)


def tsize(draw: ImageDraw.ImageDraw, value: str, font_obj=F_BODY) -> tuple[int, int]:
    """Return rendered text width and height for manual layout."""
    box = draw.textbbox((0, 0), value, font=font_obj)
    return box[2] - box[0], box[3] - box[1]


def centered(draw: ImageDraw.ImageDraw, box, value: str, fill=INK, font_obj=F_BODY) -> None:
    """Draw text centered inside a rectangle-like tuple."""
    w, h = tsize(draw, value, font_obj)
    text(draw, (box[0] + (box[2] - box[0] - w) / 2, box[1] + (box[3] - box[1] - h) / 2), value, fill, font_obj)


def stacked_label(draw: ImageDraw.ImageDraw, x: float, y: float, top_line: str, bottom_line: str, fill: str) -> None:
    """Draw a two-line centered label with the minute over the event name."""
    top_w, top_h = tsize(draw, top_line, F_TAG)
    bottom_w, bottom_h = tsize(draw, bottom_line, F_TAG)
    text(draw, (x - top_w / 2, y), top_line, fill, F_TAG)
    text(draw, (x - bottom_w / 2, y + top_h + 2), bottom_line, fill, F_TAG)


def final_score_label(img: Image.Image, draw: ImageDraw.ImageDraw, x: float, y: float, left: int, right: int) -> None:
    """Draw the end-of-match label with the final score and team flags."""
    top_line = "120+3'"
    score = "2-1"
    top_w, top_h = tsize(draw, top_line, F_TAG)
    score_w, _score_h = tsize(draw, score, F_TAG)
    flag_w, flag_h = 34, 24
    gap = 7
    total_w = flag_w + gap + score_w + gap + flag_w
    canvas_right = img.width - 34
    start_x = max(left + 8, min(x - total_w / 2, canvas_right - total_w))

    text(draw, (x - top_w / 2, y), top_line, BREAK, F_TAG)
    row_center = y + top_h + 18
    flag_y = row_center - flag_h / 2

    draw.rounded_rectangle((start_x, flag_y, start_x + flag_w, flag_y + flag_h), radius=2, fill=WHITE, outline=GRID, width=1)
    paste_flag(img, ENGLAND_FLAG, round(start_x + 2), round(flag_y + 2), flag_w - 4, flag_h - 4, trim=False)
    draw.text((start_x + flag_w + gap + score_w / 2, row_center), score, fill=BREAK, font=F_TAG, anchor="mm")
    norway_x = start_x + flag_w + gap + score_w + gap
    draw.rounded_rectangle((norway_x, flag_y, norway_x + flag_w, flag_y + flag_h), radius=2, fill=WHITE, outline=GRID, width=1)
    paste_flag(img, NORWAY_FLAG, round(norway_x + 2), round(flag_y + 2), flag_w - 4, flag_h - 4, trim=False)


def wrapped(draw: ImageDraw.ImageDraw, xy, value: str, width: int, fill=MUTED, font_obj=F_SMALL, gap=4) -> int:
    """Draw wrapped text and return the final y-coordinate."""
    x, y = xy
    for line in textwrap.wrap(value, width):
        text(draw, (x, y), line, fill, font_obj)
        y += tsize(draw, line, font_obj)[1] + gap
    return y


def paste_flag(base: Image.Image, path: Path, x: int, y: int, w: int, h: int, trim: bool = True) -> None:
    """Paste a flag into a transparent box after trimming white margins."""
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


def loc(event: dict) -> tuple[float, float] | None:
    """Return an event's start location, if present."""
    value = event.get("location") or []
    if len(value) < 2:
        return None
    return float(value[0]), float(value[1])


def norm_xy(event: dict, x: float, y: float) -> tuple[float, float]:
    """Return event coordinates as supplied by this dataset.

    The project data is already normalized for attacking direction, so the
    momentum logic must not flip x/y values. The helper is kept so the tactical
    checks read clearly and can be changed in one place if a future dataset is
    not pre-normalized.
    """
    return x, y


def pass_end(event: dict) -> tuple[float, float] | None:
    """Return the end location of a pass, if present."""
    value = (event.get("pass") or {}).get("end_location") or []
    if len(value) < 2:
        return None
    return float(value[0]), float(value[1])


def carry_end(event: dict) -> tuple[float, float] | None:
    """Return the end location of a carry, if present."""
    value = (event.get("carry") or {}).get("end_location") or []
    if len(value) < 2:
        return None
    return float(value[0]), float(value[1])


def complete_pass(event: dict) -> bool:
    """StatsBomb records completed passes as passes with no outcome value."""
    return event.get("type", {}).get("name") == "Pass" and not (event.get("pass") or {}).get("outcome")


def raw_event_time(event: dict) -> float:
    """Convert StatsBomb minute/second into the event's football-clock minute."""
    return float(event.get("minute") or 0) + float(event.get("second") or 0) / 60


def event_time(event: dict) -> float:
    """Map an event onto a continuous chart timeline that includes stoppage.

    StatsBomb stores period 3 as minute 90 onward, while period 2 can also
    continue through 90+ stoppage. Plotting raw minutes would therefore place
    extra-time actions on top of second-half stoppage. This helper shifts each
    period by the accepted stoppage boundaries so the timeline is monotonic.
    """
    period = int(event.get("period") or 1)
    raw_time = raw_event_time(event)
    period_clock_start = PERIOD_CLOCK_START.get(period, 0.0)
    period_timeline_start = PERIOD_TIMELINE_START.get(period, period_clock_start)
    return period_timeline_start + (raw_time - period_clock_start)


def display_clock_to_timeline(minute: float) -> float:
    """Map a displayed match-clock minute to the continuous chart timeline."""
    if minute <= 45:
        return minute
    if minute <= 90:
        return minute + 3
    if minute <= 105:
        return minute + 12
    return minute + 16


def in_box(x: float, y: float) -> bool:
    """Return whether a normalized coordinate is inside the penalty area."""
    return x >= 102 and 18 <= y <= 62


def in_final_third(x: float) -> bool:
    """Return whether a normalized x-coordinate is in the attacking third."""
    return x >= 80


def is_high_regain(event: dict) -> bool:
    """Identify possession-winning defensive actions high up the pitch.

    This is intentionally conservative:
    - Ball Recovery counts if it happens beyond x=80.
    - Interception counts unless StatsBomb says it was lost.
    - Duel counts only for successful tackle duels.

    The high-regain score is included because a regain near goal often creates
    immediate attacking pressure even when it does not become a shot.
    """
    point = loc(event)
    if not point:
        return False
    x, y = norm_xy(event, *point)
    if x < 80:
        return False
    event_type = event.get("type", {}).get("name")
    if event_type == "Ball Recovery":
        return True
    if event_type == "Interception":
        outcome = (event.get("interception") or {}).get("outcome", {}).get("name")
        return outcome not in {"Lost Out", "Lost In Play"}
    if event_type == "Duel":
        duel = event.get("duel") or {}
        outcome = duel.get("outcome", {}).get("name", "")
        return duel.get("type", {}).get("name") == "Tackle" and outcome.startswith("Success")
    return False


def event_threat(event: dict) -> tuple[float, list[str]]:
    """Convert one StatsBomb event into an attacking-threat score.

    The weights are transparent, hand-tuned values designed for a readable
    single-match story rather than a predictive model. They deliberately give
    the largest weight to shots and xG, then smaller values to actions that
    move the ball into dangerous zones.

    Current weighting:
    - positive OBV: `min(obv_total_net * 8, 1.5)`
    - shot: `1.5 + xG * 14 + min(shot_execution_xg * 3, 2)`
    - goal bonus: `+12`
    - corner pass: `+0.8`
    - cross: `+0.6`
    - completed pass/carry into box: `+1.2`
    - progressive completed pass/carry into final third: `+0.5`
    - box receipt: `+0.4`
    - attacking-third foul won: `+0.5`
    - high regain: `+0.7`

    The returned reasons are not used in the chart itself, but they are useful
    for debugging or auditing why an event contributed to momentum.
    """
    event_type = event.get("type", {}).get("name")
    score = 0.0
    reasons: list[str] = []

    # OBV provides StatsBomb's own possession-value signal. We cap its impact
    # so one very high OBV action does not flatten the rest of the chart.
    positive_obv = max(float(event.get("obv_total_net") or 0), 0)
    if positive_obv:
        score += min(positive_obv * 8.0, 1.5)
        reasons.append("positive OBV")

    if event_type == "Shot":
        shot = event.get("shot") or {}
        xg = float(shot.get("statsbomb_xg") or 0)
        psxg = float(shot.get("shot_execution_xg") or 0)
        # The base shot value makes even low-xG shots visible. xG and
        # shot_execution_xg then scale genuinely dangerous efforts upward.
        score += 1.5 + xg * 14.0 + min(psxg * 3.0, 2.0)
        reasons.append("shot/xG")
        if shot.get("outcome", {}).get("name") == "Goal":
            score += 12.0
            reasons.append("goal")

    if event_type == "Pass":
        p = event.get("pass") or {}
        start = loc(event)
        end = pass_end(event)
        if p.get("type", {}).get("name") == "Corner":
            score += 0.8
            reasons.append("corner")
        if p.get("cross"):
            score += 0.6
            reasons.append("cross")
        if start and end and complete_pass(event):
            sx, sy = norm_xy(event, *start)
            ex, ey = norm_xy(event, *end)
            # Box entries are more valuable than general final-third progress.
            if in_box(ex, ey):
                score += 1.2
                reasons.append("pass into box")
            elif in_final_third(ex) and ex - sx >= 10:
                score += 0.5
                reasons.append("progressive pass")

    if event_type == "Carry":
        start = loc(event)
        end = carry_end(event)
        if start and end:
            sx, sy = norm_xy(event, *start)
            ex, ey = norm_xy(event, *end)
            # Carries are treated in parallel with passes so direct dribbling
            # spells can register even without a completed pass.
            if in_box(ex, ey):
                score += 1.2
                reasons.append("carry into box")
            elif in_final_third(ex) and ex - sx >= 10:
                score += 0.5
                reasons.append("progressive carry")

    if event_type == "Ball Receipt*":
        point = loc(event)
        if point:
            x, y = norm_xy(event, *point)
            if in_box(x, y):
                score += 0.4
                reasons.append("box receipt")

    if event_type == "Foul Won":
        point = loc(event)
        if point:
            x, y = norm_xy(event, *point)
            if x >= 80:
                score += 0.5
                reasons.append("attacking-third foul won")

    if is_high_regain(event):
        score += 0.7
        reasons.append("high regain")

    return score, reasons


def build_event_points(events: list[dict]) -> list[dict]:
    """Create the compact list of scoring events used by the rolling index."""
    points = []
    for event in events:
        team = event.get("team", {}).get("name")
        if team not in TEAMS:
            continue
        score, reasons = event_threat(event)
        if score <= 0:
            continue
        points.append(
            {
                "time": event_time(event),
                "team": team,
                "score": score,
                "minute": int(event.get("minute") or 0) + 1,
                "type": event.get("type", {}).get("name"),
                "player": event.get("player", {}).get("name", ""),
                "reasons": reasons,
            }
        )
    return points


def rolling_threat(points: list[dict], max_minute: int, step: float = 0.5) -> tuple[list[float], dict[str, list[float]]]:
    """Build each team's rolling attacking-threat curve.

    Parameters:
    - `points`: threat-scored events from `build_event_points`.
    - `max_minute`: last minute to include on the chart.
    - `step`: chart resolution in minutes. `0.5` means one value every
      30 seconds.

    For each time slice, the script sums threat points from the previous
    five minutes. Recent actions count more than older actions using
    exponential decay:

        contribution = event_score * exp(-age / tau)

    `tau = 2.2` means the value of an action fades materially over a few
    minutes, but a strong attack can still shape the rest of the five-minute
    window. The resulting curves are lightly smoothed before charting.
    """
    times = [round(i * step, 2) for i in range(int(max_minute / step) + 1)]
    threats = {team: [] for team in TEAMS}
    tau = 2.2
    window = 5.0
    for t in times:
        for team in TEAMS:
            value = 0.0
            for point in points:
                age = t - point["time"]
                if point["team"] != team or age < 0 or age > window:
                    continue
                value += point["score"] * math.exp(-age / tau)
            threats[team].append(value)
    return times, {team: smooth(values) for team, values in threats.items()}


def smooth(values: list[float]) -> list[float]:
    """Apply a small weighted moving average to reduce visual jitter."""
    smoothed = []
    weights = [1, 2, 3, 2, 1]
    offset = len(weights) // 2
    for i, _ in enumerate(values):
        total = 0.0
        denom = 0.0
        for j, weight in enumerate(weights):
            idx = i + j - offset
            if 0 <= idx < len(values):
                total += values[idx] * weight
                denom += weight
        smoothed.append(total / denom if denom else values[i])
    return smoothed


def goals(events: list[dict]) -> list[dict]:
    """Extract goal events for annotations on the momentum chart."""
    rows = []
    for event in events:
        if event.get("type", {}).get("name") != "Shot":
            continue
        if (event.get("shot") or {}).get("outcome", {}).get("name") != "Goal":
            continue
        rows.append(
            {
                "time": event_time(event),
                "minute": int(event.get("minute") or 0) + 1,
                "label_minute": display_minute(event),
                "team": event.get("team", {}).get("name"),
                "player": event.get("player", {}).get("name", "").split()[-1],
            }
        )
    return rows


def display_minute(event: dict) -> str:
    """Return a football-style minute label for event annotations."""
    minute = int(event.get("minute") or 0)
    second = int(event.get("second") or 0)
    period = int(event.get("period") or 0)
    if period == 1 and (minute > 45 or (minute == 45 and second > 0)):
        return f"45+{math.ceil((raw_event_time(event) - 45) or 1)}"
    if period == 2 and (minute > 90 or (minute == 90 and second > 0)):
        return f"90+{math.ceil((raw_event_time(event) - 90) or 1)}"
    if period == 3 and (minute > 105 or (minute == 105 and second > 0)):
        return f"105+{math.ceil((raw_event_time(event) - 105) or 1)}"
    if period == 4 and (minute > 120 or (minute == 120 and second > 0)):
        return f"120+{math.ceil((raw_event_time(event) - 120) or 1)}"
    return str(minute + 1)


def hydration_breaks(events: list[dict]) -> list[dict]:
    """Return the match hydration breaks to annotate on the chart."""
    del events
    return [{"time": display_clock_to_timeline(float(minute)), "minute": minute} for minute in HYDRATION_MINUTES]


def x_at(time_value: float, left: int, right: int, max_minute: int) -> float:
    """Map a match minute to an x-coordinate inside a chart area."""
    return left + time_value / max_minute * (right - left)


def draw_dotted_vertical(draw: ImageDraw.ImageDraw, x: float, top: int, bottom: int, fill: str, width: int = 2, dash: int = 7, gap: int = 6) -> None:
    """Draw a vertical dotted/dashed marker line."""
    y = top
    while y < bottom:
        draw.line((x, y, x, min(y + dash, bottom)), fill=fill, width=width)
        y += dash + gap


def draw_dotted_horizontal(draw: ImageDraw.ImageDraw, left: float, right: float, y: float, fill: str, width: int = 2, dash: int = 7, gap: int = 6) -> None:
    """Draw a horizontal dotted/dashed marker line."""
    x = left
    while x < right:
        draw.line((x, y, min(x + dash, right), y), fill=fill, width=width)
        x += dash + gap


def draw_axis(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    left: int,
    right: int,
    top: int,
    bottom: int,
    baseline: int,
    max_minute: int,
    events: list[dict],
) -> None:
    """Draw the shared time axis, half-time/extra-time markers and labels."""
    draw.rectangle((left, top, right, bottom), fill=WHITE, outline=GRID, width=1)
    # Bottom ticks show the football clock within each period. The repeated
    # labels at 45, 90 and 105 mark the clock reset after HT, FT and ET HT.
    clock_ticks = [
        (0, "0"),
        (15, "15"),
        (30, "30"),
        (PERIOD_TIMELINE_START[2], "45"),
        (PERIOD_TIMELINE_START[2] + 15, "60"),
        (PERIOD_TIMELINE_START[2] + 30, "75"),
        (PERIOD_TIMELINE_START[3], "90"),
        (PERIOD_TIMELINE_START[4], "105"),
        (PERIOD_TIMELINE_START[4] + 15, "120"),
    ]
    for timeline_minute, label in clock_ticks:
        if timeline_minute > max_minute:
            continue
        x = x_at(timeline_minute, left, right, max_minute)
        draw.line((x, top, x, bottom), fill=GRID, width=1)
        text(draw, (x - 10, bottom + 14), label, MUTED, F_SMALL)
    draw.line((left, baseline, right, baseline), fill=INK, width=2)
    period_markers = [
        (48, "45+3'", "HT"),
        (102, "90+9'", "FT"),
        (121, "105+4'", "ET HT"),
        (139, "120+3'", "FINAL_SCORE"),
    ]
    for minute, top_label, bottom_label in period_markers:
        if minute <= max_minute:
            x = x_at(minute, left, right, max_minute)
            draw.line((x, top, x, bottom), fill=BREAK, width=4)
            if bottom_label == "FINAL_SCORE":
                final_score_label(img, draw, x, top - 62, left, right)
            elif bottom_label:
                stacked_label(draw, x, top - 62, top_label, bottom_label, BREAK)
            else:
                centered(draw, (x - 70, top - 46, x + 70, top - 8), top_label, BREAK, F_TAG)
    for item in hydration_breaks(events):
        x = x_at(item["time"], left, right, max_minute)
        draw_dotted_vertical(draw, x, top, bottom, PURPLE, width=4, dash=11, gap=7)
        stacked_label(draw, x, top - 62, f"{item['minute']}'", "Hydration Break", PURPLE)


def nice_axis_max(value: float) -> int:
    """Return the chart's fixed mirrored momentum scale."""
    del value
    return 24


def draw_y_axis_labels(draw: ImageDraw.ImageDraw, left: int, baseline: int, half_h: int, axis_max: int) -> None:
    """Draw momentum-index labels that match the plotted bar scale."""
    half_tick = int(round(axis_max / 2))
    tick_values = [axis_max, half_tick, 0, -half_tick, -axis_max]
    for value in tick_values:
        y = baseline - (value / axis_max) * half_h if axis_max else baseline
        label = str(abs(value))
        label_width, label_height = tsize(draw, label, F_SMALL)
        text(draw, (left - label_width - 10, y - label_height / 2), label, MUTED, F_SMALL)
        draw.line((left - 6, y, left, y), fill=GRID, width=1)


def rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    """Convert a #RRGGBB colour token to an RGBA tuple."""
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha


def draw_momentum_wave(
    img: Image.Image,
    times: list[float],
    values: list[float],
    left: int,
    right: int,
    baseline: int,
    half_h: int,
    axis_max: int,
    max_minute: int,
) -> None:
    """Draw the net momentum values as a smooth filled wave."""
    curve = [
        (
            x_at(time_value, left, right, max_minute),
            baseline - value / axis_max * half_h,
            value,
        )
        for time_value, value in zip(times, values)
    ]
    red_curve = [(x, min(y, baseline)) for x, y, _value in curve]
    blue_curve = [(x, max(y, baseline)) for x, y, _value in curve]
    red_area = [(left, baseline), *red_curve, (right, baseline)]
    blue_area = [(left, baseline), *blue_curve, (right, baseline)]

    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.polygon(red_area, fill=rgba(ENGLAND, 235))
    overlay_draw.polygon(blue_area, fill=rgba(NORWAY, 235))

    for side, fill in ((1, ENGLAND), (-1, NORWAY)):
        segment = []
        for x, y, value in curve:
            if value * side > 0:
                segment.append((x, y))
            else:
                if len(segment) > 1:
                    overlay_draw.line(segment, fill=rgba(fill), width=3)
                segment = []
        if len(segment) > 1:
            overlay_draw.line(segment, fill=rgba(fill), width=3)

    composited = img.convert("RGBA")
    composited.alpha_composite(overlay)
    img.paste(composited.convert("RGB"))


def draw_label_box(draw: ImageDraw.ImageDraw, x: float, y: float, label: str, fill: str, font_obj: ImageFont.FreeTypeFont) -> None:
    """Draw a label with a white backing so chart lines do not run through it."""
    label_width, label_height = tsize(draw, label, font_obj)
    pad_x, pad_y = 5, 2
    draw.rounded_rectangle(
        (x - pad_x, y - pad_y, x + label_width + pad_x, y + label_height + pad_y),
        radius=3,
        fill=WHITE,
    )
    text(draw, (x, y), label, fill, font_obj)

@lru_cache(maxsize=1)
def ball_marker_image() -> Image.Image:
    """Load the supplied ball marker and remove the black outer background.

    Only dark pixels connected to the image edge are made transparent. That
    keeps the black printed details on the ball itself intact.
    """
    marker = Image.open(BALL_MARKER).convert("RGBA")
    width, height = marker.size
    pixels = marker.load()
    visited = set()
    queue: deque[tuple[int, int]] = deque()

    def is_background(px: int, py: int) -> bool:
        red, green, blue, alpha = pixels[px, py]
        return alpha > 0 and red < 22 and green < 22 and blue < 22

    for px in range(width):
        for py in (0, height - 1):
            if is_background(px, py):
                queue.append((px, py))
                visited.add((px, py))
    for py in range(height):
        for px in (0, width - 1):
            if (px, py) not in visited and is_background(px, py):
                queue.append((px, py))
                visited.add((px, py))

    while queue:
        px, py = queue.popleft()
        red, green, blue, _alpha = pixels[px, py]
        pixels[px, py] = (red, green, blue, 0)
        for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited and is_background(nx, ny):
                visited.add((nx, ny))
                queue.append((nx, ny))

    alpha_box = marker.getchannel("A").getbbox()
    return marker.crop(alpha_box) if alpha_box else marker


def paste_soccer_ball(base: Image.Image, x: float, y: float, r: int = 12) -> None:
    """Paste the supplied World Cup ball image centered on the given point."""
    ball = ball_marker_image().copy()
    size = r * 2
    ball.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    canvas.alpha_composite(ball, ((size - ball.width) // 2, (size - ball.height) // 2))
    base.paste(canvas, (round(x - r), round(y - r)), canvas)


def goal_tag_size(draw: ImageDraw.ImageDraw, minute: str, player: str, ball_r: int = 13) -> tuple[int, int]:
    """Return the size of a one-line goal tag with ball, minute and scorer."""
    label = f"{minute} {player}"
    label_width, label_height = tsize(draw, label, F_TAG)
    pad_x, pad_y = 8, 5
    width = ball_r * 2 + 8 + label_width + pad_x * 2
    height = max(ball_r * 2, label_height) + pad_y * 2
    return width, height


def draw_goal_tag(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    ball_x: float,
    y: float,
    minute: str,
    player: str,
    fill: str,
    ball_r: int = 13,
) -> None:
    """Draw a compact one-line goal label with the ball on the goal line."""
    tag_width, tag_height = goal_tag_size(draw, minute, player, ball_r)
    pad_x, pad_y = 8, 5
    x = ball_x - ball_r - pad_x
    draw.rounded_rectangle((x, y, x + tag_width, y + tag_height), radius=5, fill=fill)

    row_h = tag_height - pad_y * 2
    row_center = y + pad_y + row_h / 2
    paste_soccer_ball(img, ball_x, row_center, ball_r)

    label = f"{minute} {player}"
    label_x = ball_x + ball_r + 8
    draw.text((label_x, row_center), label, fill=WHITE, font=F_TAG, anchor="lm")


def draw_legend(img: Image.Image, draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """Draw a bold two-column legend in the top-right title area."""
    draw.rounded_rectangle((x, y, x + 390, y + 116), radius=8, fill=PALE, outline=GRID, width=1)

    row_y = y + 20
    draw.ellipse((x + 22, row_y + 8, x + 44, row_y + 30), fill=NORWAY)
    draw.rounded_rectangle((x + 60, row_y + 1, x + 114, row_y + 35), radius=3, fill=WHITE, outline=GRID, width=1)
    paste_flag(img, NORWAY_FLAG, x + 63, row_y + 4, 48, 28, trim=False)
    text(draw, (x + 130, row_y + 3), "Norway", INK, F_LEGEND)

    row_y += 48
    draw.ellipse((x + 22, row_y + 8, x + 44, row_y + 30), fill=ENGLAND)
    draw.rounded_rectangle((x + 60, row_y + 1, x + 114, row_y + 35), radius=3, fill=WHITE, outline=GRID, width=1)
    paste_flag(img, ENGLAND_FLAG, x + 63, row_y + 4, 48, 28, trim=False)
    text(draw, (x + 130, row_y + 3), "England", INK, F_LEGEND)

    event_x = x + 240
    event_label_x = event_x + 58
    row_y = y + 20
    row_center = row_y + 19
    paste_soccer_ball(img, event_x + 23, row_center, 13)
    text(draw, (event_label_x, row_y + 3), "Goal", INK, F_LEGEND)

    row_y += 48
    row_center = row_y + 19
    draw_dotted_horizontal(draw, event_x + 2, event_x + 44, row_center - 7, PURPLE, width=4, dash=7, gap=5)
    draw.line((event_x + 2, row_center + 7, event_x + 44, row_center + 7), fill=BREAK, width=4)
    text(draw, (event_label_x, row_y + 3), "Breaks", INK, F_LEGEND)


def draw_chart(img: Image.Image, draw: ImageDraw.ImageDraw, times: list[float], threats: dict[str, list[float]], events: list[dict]) -> dict[str, float]:
    """Draw the main momentum chart and return scaling values.

    The chart now uses one primary layer only: a net momentum wave. Positive
    values favor England; negative values favor Norway.
    """
    left, right = 95, 1505
    top, bottom = 300, 960
    baseline = (top + bottom) // 2
    max_minute = max(int(math.ceil(max(times))), MATCH_END_TIMELINE)
    draw_axis(img, draw, left, right, top, bottom, baseline, max_minute, events)

    # Net drives the red/blue wave. The extra pass of smoothing is a visual
    # treatment only, so the chart reads as momentum rather than event noise.
    net = [threats["England"][i] - threats["Norway"][i] for i in range(len(times))]
    visual_net = smooth(smooth(net))
    max_abs = max(max(abs(value) for value in visual_net), 0.01)
    half_h = 300
    axis_max = nice_axis_max(max_abs)
    draw_y_axis_labels(draw, left, baseline, half_h, axis_max)
    draw_momentum_wave(img, times, visual_net, left, right, baseline, half_h, axis_max, max_minute)
    draw.line((left, baseline, right, baseline), fill=INK, width=2)

    for goal in goals(events):
        # Goal markers are intentionally vertical because they should connect
        # the moment of the goal with the surrounding momentum context.
        x = x_at(goal["time"], left, right, max_minute)
        color = ENGLAND if goal["team"] == "England" else NORWAY
        line_top, line_bottom = (top, baseline) if goal["team"] == "England" else (baseline, bottom)
        
        draw_dotted_vertical(draw, x, line_top, line_bottom, color, width=4)
        minute = f"{goal['label_minute']}'"
        player = goal["player"]
        _label_width, label_height = goal_tag_size(draw, minute, player)
        if goal["team"] == "England":
            label_y = top + 18
        else:
            label_y = bottom - label_height - 14
        draw_goal_tag(img, draw, x, label_y, minute, player, color)

    return {"max_abs": max_abs, "axis_max": axis_max, "max_minute": max_minute}


def strongest_windows(times: list[float], threats: dict[str, list[float]], top_n: int = 4) -> list[tuple[str, float, float]]:
    """Return the strongest non-overlapping net momentum windows.

    This is printed as a validation aid. The four-minute spacing rule avoids
    reporting the same sustained spell multiple times.
    """
    rows = []
    for i, t in enumerate(times):
        net = threats["England"][i] - threats["Norway"][i]
        team = "England" if net >= 0 else "Norway"
        rows.append((team, t, abs(net)))
    rows.sort(key=lambda row: row[2], reverse=True)
    picked = []
    for team, t, value in rows:
        if all(abs(t - other_t) > 4 for _, other_t, _ in picked):
            picked.append((team, t, value))
        if len(picked) == top_n:
            break
    return picked


def main() -> None:
    """Load data, build the index, render the chart and print checks."""
    events = json.loads(EVENTS_PATH.read_text())
    points = build_event_points(events)
    max_minute = max(int(math.ceil(max(event_time(event) for event in events))), MATCH_END_TIMELINE)
    times, threats = rolling_threat(points, max_minute)

    img = Image.new("RGB", (1600, 1100), WHITE)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 1599, 1099), outline=STYLE_BLUE, width=18)
    text(draw, (95, 44), "Match Momentum", INK, F_TITLE)
    text(draw, (95, 108), "A rolling five-minute net attacking-threat view: England above, Norway below", MUTED, F_SUB)
    draw_legend(img, draw, 1135, 44)

    stats = draw_chart(img, draw, times, threats, events)

    out = OUT / "statsbomb_match_momentum_index.png"
    img.save(out, "PNG", optimize=True)
    print(f"Saved {out}")
    print("Index details")
    print(f"Threat events: {len(points)}")
    print(f"Max plotted net value: {stats['max_abs']:.2f}")
    print("Strongest momentum windows:")
    for team, t, value in strongest_windows(times, threats):
        print(f"{team}: around {t:.1f}' raw net {value:.2f}")


if __name__ == "__main__":
    main()
