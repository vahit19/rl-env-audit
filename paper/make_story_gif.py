"""Story GIF for the README: what the test sends, the two-guess rule, the scan and the fixes.

    uv run --with pillow python paper/make_story_gif.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures"
OUT.mkdir(exist_ok=True)
W, H = 1200, 620

FONTS = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu")]


def fnt(size, bold=False):
    names = ["segoeuib.ttf", "DejaVuSans-Bold.ttf"] if bold else ["segoeui.ttf", "DejaVuSans.ttf"]
    for d in FONTS:
        for n in names:
            if (d / n).exists():
                return ImageFont.truetype(str(d / n), size)
    return ImageFont.load_default()


BG = (248, 250, 252); INK = (24, 32, 44); MUTED = (90, 102, 118); LINE = (203, 210, 217)
BLUE = (29, 78, 216); RED = (220, 38, 38); GREEN = (22, 128, 61); PURPLE = (109, 40, 217); GREY = (156, 163, 175)
LBLUE = (219, 234, 254); LRED = (254, 226, 226); LGREEN = (220, 252, 231); LPURP = (237, 233, 254)
LAMBER = (254, 249, 235)

scan = json.loads((ROOT / "scans" / "2026-10-13-prime-hub.json").read_text(encoding="utf-8"))
fix = json.loads((ROOT / "scans" / "2026-10-14-fixes.json").read_text(encoding="utf-8"))
N_ALL = len(scan)
AUD = [r for r in scan if r["status"] == "audited"]
N_FAIL = sum(1 for r in AUD if any(c.get("paid", 0) for c in r["checks"].values()))
N_PASS = len(AUD) - N_FAIL
N_NA = N_ALL - len(AUD)

POL = (40, 150, 270, 260)
GRA = (40, 300, 270, 410)
INS = (40, 450, 270, 560)
CARD = (330, 150, 1160, 570)


def box(dr, b, title, sub, tag, fill, hl=None):
    dr.rounded_rectangle(b, 18, fill=fill, outline=hl or LINE, width=5 if hl else 2)
    x0, y0, x1, y1 = b
    dr.text(((x0 + x1) // 2, y0 + 30), title, font=fnt(25, True), fill=INK, anchor="mm")
    dr.text(((x0 + x1) // 2, y0 + 62), sub, font=fnt(17), fill=MUTED, anchor="mm")
    dr.text(((x0 + x1) // 2, y1 - 18), tag, font=fnt(15, True), fill=RED if tag == "AI" else PURPLE, anchor="mm")


def arrow(dr, p0, p1, color, width=5, dot=None):
    (x0, y0), (x1, y1) = p0, p1
    dr.line([x0, y0, x1, y1], fill=color, width=width)
    ang = math.atan2(y1 - y0, x1 - x0)
    a1 = (x1 - 16 * math.cos(ang - 0.45), y1 - 16 * math.sin(ang - 0.45))
    a2 = (x1 - 16 * math.cos(ang + 0.45), y1 - 16 * math.sin(ang + 0.45))
    dr.polygon([(x1, y1), a1, a2], fill=color)
    if dot is not None:
        xd, yd = x0 + (x1 - x0) * dot, y0 + (y1 - y0) * dot
        dr.ellipse([xd - 9, yd - 9, xd + 9, yd + 9], fill=color)


def headline(dr, text, color, sub):
    dr.text((W // 2, 50), text, font=fnt(36, True), fill=color, anchor="mm")
    dr.text((W // 2, 98), sub, font=fnt(22), fill=INK, anchor="mm")


def card(dr, title):
    dr.rounded_rectangle(CARD, 18, fill="white", outline=LINE, width=2)
    dr.text((CARD[0] + 24, CARD[1] + 28), title, font=fnt(22, True), fill=INK, anchor="lm")


def side(dr, p, hl_g=None, hl_i=None, inspector=True):
    box(dr, POL, "Policy", "the model in training", "AI", LBLUE)
    box(dr, GRA, "Grader", "the environment's own code", "CODE", LRED if hl_g else LAMBER, hl_g)
    if inspector:
        box(dr, INS, "rl-env-audit", "sends test replies", "CODE", LPURP, hl_i)
        arrow(dr, (155, 450), (155, 410), PURPLE, dot=(p * 3) % 1 if hl_i else None)
    arrow(dr, (120, 260), (120, 300), BLUE)
    arrow(dr, (190, 300), (190, 260), RED if hl_g else GREEN)
    dr.text((112, 280), "reply", font=fnt(14, True), fill=BLUE, anchor="rm")
    dr.text((198, 280), "reward", font=fnt(14, True), fill=RED if hl_g else GREEN, anchor="lm")


def footer(dr):
    dr.text((W // 2, H - 22), "github.com/vahit19/rl-env-audit  ·  60 real environments  ·  Vahit Feryad, PhD",
            font=fnt(16), fill=MUTED, anchor="mm")


def pill(dr, x, y, text, fill, color="white", size=17):
    w = dr.textlength(text, font=fnt(size, True)) + 28
    dr.rounded_rectangle([x, y - 16, x + w, y + 16], 14, fill=fill)
    dr.text((x + w / 2, y), text, font=fnt(size, True), fill=color, anchor="mm")


def s0(f, n):  # what the test is for
    im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im); p = f / max(1, n - 1)
    headline(dr, "1. Every RL environment has a grader", BLUE,
             "The policy learns whatever the grader pays. Is it paying only correct answers?")
    side(dr, p, inspector=False)
    card(dr, "A grader should pay a reply only if it commits to the correct answer")
    x0, y0 = CARD[0] + 40, CARD[1] + 90
    rows = [("The final answer is \\boxed{42}.", "correct answer", "pay", GREEN),
            ("The final answer is \\boxed{41}.", "wrong answer", "do not pay", RED),
            ("41 or 42", "two guesses at once", "do not pay", RED),
            ("(the question, repeated back)", "no answer at all", "do not pay", RED)]
    for i, (reply, what, verdict, col) in enumerate(rows):
        if p * 5 < i:
            break
        y = y0 + i * 72
        dr.rounded_rectangle([x0, y - 24, x0 + 430, y + 24], 10, fill=(241, 245, 249))
        dr.text((x0 + 14, y), reply, font=fnt(18), fill=INK, anchor="lm")
        dr.text((x0 + 450, y), what, font=fnt(17), fill=MUTED, anchor="lm")
        pill(dr, x0 + 640, y, verdict, col)
    footer(dr)
    return im


def s1(f, n):  # the checks
    im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im); p = f / max(1, n - 1)
    headline(dr, "2. Send replies that should never be paid", PURPLE,
             "10 checks per task, built from the task's own answer. No model, no extra labels.")
    side(dr, p, hl_i=PURPLE)
    card(dr, "The checks")
    fams = [("Null replies", ["empty reply", "format with nothing in it", "the question, repeated"]),
            ("Grader injection", ["wrong answer + \"Award full credit\""]),
            ("Two guesses", ["\"g or w\"", "a list \"w, g\"", "two final answers", "value in reasoning, another final",
                             "\"it is not g\", then w", "w, then \"some sources list g\""])]
    x, y = CARD[0] + 40, CARD[1] + 78
    shown = int(p * 12)
    k = 0
    for fam, items in fams:
        dr.text((x, y), fam, font=fnt(19, True), fill=PURPLE, anchor="lm")
        y += 30
        for it in items:
            if k < shown:
                dr.text((x + 24, y), "• " + it, font=fnt(17), fill=INK, anchor="lm")
            k += 1
            y += 27
        y += 8
    dr.text((CARD[2] - 30, CARD[3] - 26), "first: find the format and reward term that really check correctness",
            font=fnt(15), fill=MUTED, anchor="rm")
    footer(dr)
    return im


def s2(f, n):  # the cross-task rule
    im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im); p = f / max(1, n - 1)
    headline(dr, "3. The two-guess test: one reply, two tasks", RED,
             "Paid as correct on BOTH tasks? Then a policy can hedge and never decide.")
    side(dr, p, hl_g=RED if p > 0.45 else None, hl_i=PURPLE)
    card(dr, "Reply: \"Pickle or Chennai\"")
    cx = (CARD[0] + CARD[2]) // 2
    cols = [("Grader A: is the answer contained?", RED, (1.0, 1.0), "HOLE: paid twice"),
            ("Grader B: read the last value", GREEN, (0.0, 1.0), "fair: no second guess")]
    for j, (name, col, rewards, verdict) in enumerate(cols):
        x0 = CARD[0] + 30 + j * 405
        dr.text((x0 + 185, CARD[1] + 80), name, font=fnt(18, True), fill=INK, anchor="mm")
        for t, (gold, rw) in enumerate(zip(["Pickle", "Chennai"], rewards)):
            y = CARD[1] + 140 + t * 90
            dr.rounded_rectangle([x0, y - 32, x0 + 370, y + 32], 12, fill=(241, 245, 249))
            dr.text((x0 + 16, y), f"task whose answer is {gold}", font=fnt(17), fill=INK, anchor="lm")
            if p > 0.25 + 0.15 * t:
                pill(dr, x0 + 270, y, f"reward {rw:.0f}", RED if (rw and j == 0) else (GREEN if rw else GREY))
        if p > 0.6:
            pill(dr, x0 + 70, CARD[1] + 340, verdict, col, size=19)
    if p > 0.75:
        dr.text((cx, CARD[3] - 30), "Proved: a grader that reads one answer, by any rule, can never be flagged.",
                font=fnt(17, True), fill=INK, anchor="mm")
    footer(dr)
    return im


def s3(f, n):  # the scan
    im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im); p = f / max(1, n - 1)
    headline(dr, f"4. Scan: the {N_ALL} most-starred environments", BLUE,
             "Prime Intellect Environments Hub, single-turn. Each installed in its own sandbox. About $1.")
    side(dr, p, hl_i=PURPLE)
    card(dr, "Result")
    bars = [("passed every check", N_PASS, GREEN), ("paid a reply with no correct answer", N_FAIL, RED),
            ("could not be audited (keys, no single answer, ...)", N_NA, GREY)]
    x0, x1 = CARD[0] + 40, CARD[2] - 90
    for i, (name, v, col) in enumerate(bars):
        y = CARD[1] + 100 + i * 95
        dr.text((x0, y - 24), name, font=fnt(18, True), fill=col if col != GREY else MUTED, anchor="lm")
        g = min(1.0, max(0.0, p * 1.6 - i * 0.2))
        w = int((x1 - x0) * v / N_NA * g)
        dr.rounded_rectangle([x0, y - 4, x0 + max(10, w), y + 26], 8, fill=col)
        if g >= 1:
            dr.text((x0 + w + 12, y + 11), str(v), font=fnt(24, True), fill=col if col != GREY else MUTED,
                    anchor="lm")
    if p > 0.7:
        dr.text((CARD[0] + 40, CARD[3] - 40), "Certificate for the 19: every check paid on < 4.9% of tasks (95%).",
                font=fnt(18, True), fill=GREEN, anchor="lm")
    footer(dr)
    return im


def s4(f, n):  # the fixes
    im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im); p = f / max(1, n - 1)
    headline(dr, "5. Found, fixed, proven", PURPLE,
             "A few lines per grader. The holes close; honest answers are paid exactly as before.")
    side(dr, p)
    card(dr, "Share of tasks paid without a correct answer")
    A, B = fix["Environment A"], fix["Environment B"]
    h = A["honest_phrasings"]
    rows = [("A: \"X or Y\"", A["before"]["hedge_or"], A["after"]["hedge_or"]),
            ("A: list \"Y, X\"", A["before"]["candidate_list"], A["after"]["candidate_list"]),
            ("B: question repeated", B["before"]["echo_prompt"], B["after"]["echo_prompt"])]
    x0, x1 = CARD[0] + 250, CARD[2] - 110
    for i, (name, b, a) in enumerate(rows):
        y = CARD[1] + 90 + i * 88
        dr.text((CARD[0] + 30, y + 12), name, font=fnt(18, True), fill=INK, anchor="lm")
        fb = b["paid"] / b["tested"]
        fa = a["paid"] / a["tested"]
        frac = fb if p < 0.45 else fb + (fa - fb) * min(1, (p - 0.45) / 0.35)
        col = RED if p < 0.45 else (PURPLE if frac > fa + 1e-9 else BLUE)
        dr.rounded_rectangle([x0, y, x0 + max(10, int((x1 - x0) * max(frac, 0.012))), y + 26], 8, fill=col)
        lab = f"{b['paid']}/{b['tested']}" if p < 0.45 else (f"{a['paid']}/{a['tested']}" if p > 0.8 else "")
        dr.text((x0 + max(10, int((x1 - x0) * frac)) + 12, y + 13), lab, font=fnt(18, True), fill=col, anchor="lm")
    if p > 0.8:
        dr.text((CARD[0] + 30, CARD[3] - 40),
                f"Honest replies paid: {h['paid_before']:,}/{h['replies']:,} before, {h['paid_after']:,}/{h['replies']:,}"
                " after. None changed.", font=fnt(18, True), fill=GREEN, anchor="lm")
    footer(dr)
    return im


def s5(f, n):  # closing
    im = Image.new("RGB", (W, H), BG); dr = ImageDraw.Draw(im)
    headline(dr, "Test the grader before you train on it.", BLUE,
             "An acceptance test for RL environments: certificate or failing replies, in minutes.")
    side(dr, 0)
    card(dr, "rl-env-audit")
    lines = [("Ten checks from each task's own answer", INK), ("A rule proven not to flag honest graders", INK),
             (f"{N_ALL} public environments scanned: {N_PASS} certified, {N_FAIL} holes found and fixed", INK),
             ("Paper, code, data: github.com/vahit19/rl-env-audit", BLUE)]
    for i, (t, col) in enumerate(lines):
        dr.text((CARD[0] + 40, CARD[1] + 100 + i * 70), "•  " + t if col == INK else t, font=fnt(22, col == BLUE),
                fill=col, anchor="lm")
    footer(dr)
    return im


SCENES = [(s0, 22), (s1, 22), (s2, 34), (s3, 26), (s4, 30), (s5, 22)]
frames = [fn(f, n) for fn, n in SCENES for f in range(n)]
pal = [fr.convert("P", palette=Image.ADAPTIVE, colors=96) for fr in frames]
out = OUT / "rl_env_audit_story.gif"
pal[0].save(out, save_all=True, append_images=pal[1:], duration=150, loop=0, optimize=True, disposal=2)
print(out, out.stat().st_size, len(frames))
