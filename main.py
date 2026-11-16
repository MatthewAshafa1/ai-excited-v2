#!/usr/bin/env python3
"""The Match That Lit the Sun -- make.fun ai-excited-01 entry.

A single diagonal matchstick, struck at dawn, whose flame is a whole
rising sun over a dark sea. One focal shape, diagonal momentum, a scale
twist (a tiny match lighting a giant sun), no text.

Pure standard library: renders a 1024x1024 RGB image and writes it as
a PNG (zlib + struct encoder). Fully deterministic: fixed seed, no
clock, no network, no randomness from the environment.

Run:  mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import binascii
import math
import os
import struct
import zlib

W, H = 1024, 1024
HORIZON = 660
SUN_CX, SUN_CY, SUN_R = 700.0, 290.0, 140.0


# ---------------------------------------------------------------- helpers
def clamp(v, lo=0.0, hi=255.0):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def lerp3(c1, c2, t):
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


def smooth(t):
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    return t * t * (3.0 - 2.0 * t)


class LCG:
    """Deterministic pseudo-random source (fixed seed, no time)."""

    def __init__(self, seed=20261116):
        self.s = seed & 0x7FFFFFFF

    def next(self):
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s / 2147483648.0

    def range(self, lo, hi):
        return lo + (hi - lo) * self.next()


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, r, g, b):
        i = (y * self.w + x) * 3
        self.px[i] = int(clamp(r))
        self.px[i + 1] = int(clamp(g))
        self.px[i + 2] = int(clamp(b))

    def get(self, x, y):
        i = (y * self.w + x) * 3
        return self.px[i], self.px[i + 1], self.px[i + 2]

    def blend(self, x, y, r, g, b, a):
        """Alpha-over blend of colour (r,g,b) with opacity a in [0,1]."""
        if a <= 0.0:
            return
        if a >= 1.0:
            self.set(x, y, r, g, b)
            return
        i = (y * self.w + x) * 3
        self.px[i] = int(clamp(lerp(self.px[i], r, a)))
        self.px[i + 1] = int(clamp(lerp(self.px[i + 1], g, a)))
        self.px[i + 2] = int(clamp(lerp(self.px[i + 2], b, a)))

    def disc(self, cx, cy, rad, colour, alpha=1.0, feather=1.5):
        """Soft-edged filled disc."""
        x0 = max(0, int(cx - rad - feather - 1))
        x1 = min(self.w - 1, int(cx + rad + feather + 1))
        y0 = max(0, int(cy - rad - feather - 1))
        y1 = min(self.h - 1, int(cy + rad + feather + 1))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                d = math.hypot(x - cx, y - cy)
                a = alpha * (1.0 - smooth((d - rad + feather) / (2.0 * feather)))
                if a > 0.003:
                    self.blend(x, y, colour[0], colour[1], colour[2], a)

    def ellipse(self, cx, cy, rx, ry, colour, alpha=1.0, feather=2.0):
        x0 = max(0, int(cx - rx - feather - 1))
        x1 = min(self.w - 1, int(cx + rx + feather + 1))
        y0 = max(0, int(cy - ry - feather - 1))
        y1 = min(self.h - 1, int(cy + ry + feather + 1))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                d = math.hypot((x - cx) / rx, (y - cy) / ry)
                a = alpha * (1.0 - smooth((d - 1.0 + feather / rx) / (2.0 * feather / rx)))
                if a > 0.003:
                    self.blend(x, y, colour[0], colour[1], colour[2], a)


# ---------------------------------------------------------------- sky
SKY_STOPS = [
    (0, (9, 13, 46)),
    (260, (34, 26, 84)),
    (470, (88, 40, 108)),
    (600, (178, 76, 88)),
    (660, (224, 108, 62)),
]


def sky_colour(y):
    for i in range(len(SKY_STOPS) - 1):
        y0, c0 = SKY_STOPS[i]
        y1, c1 = SKY_STOPS[i + 1]
        if y <= y1:
            return lerp3(c0, c1, (y - y0) / (y1 - y0))
    return SKY_STOPS[-1][1]


def render():
    cv = Canvas(W, H)
    rng = LCG(20261116)

    # --- sky gradient, row by row
    for y in range(HORIZON):
        r, g, b = sky_colour(y)
        base = y * W * 3
        for x in range(W):
            cv.px[base + x * 3] = int(r)
            cv.px[base + x * 3 + 1] = int(g)
            cv.px[base + x * 3 + 2] = int(b)

    # --- sea gradient
    for y in range(HORIZON, H):
        t = (y - HORIZON) / (H - HORIZON)
        r, g, b = lerp3((56, 40, 78), (7, 11, 32), t)
        base = y * W * 3
        for x in range(W):
            cv.px[base + x * 3] = int(r)
            cv.px[base + x * 3 + 1] = int(g)
            cv.px[base + x * 3 + 2] = int(b)

    # --- stars in the upper sky (fixed seed, so identical every run)
    for _ in range(150):
        sx = rng.range(10, W - 10)
        sy = rng.range(8, 480)
        sr = rng.range(0.7, 1.9)
        bright = rng.range(0.35, 0.95)
        # keep the sky clear right around the sun
        if math.hypot(sx - SUN_CX, sy - SUN_CY) < SUN_R + 90:
            continue
        cv.disc(sx, sy, sr, (235, 238, 255), bright, feather=0.8)

    # --- soft warm clouds, low alpha so the sun stays the hero
    clouds = [
        (210, 210, 150, 9, 0.16),
        (420, 150, 110, 8, 0.13),
        (880, 470, 130, 9, 0.15),
        (140, 470, 120, 8, 0.14),
        (930, 180, 90, 7, 0.12),
    ]
    for cx, cy, rx, ry, a in clouds:
        cv.ellipse(cx, cy, rx, ry, (255, 150, 112), a, feather=6.0)

    # --- sun glow: wide warm halo, strongest near the disc
    gx0, gx1 = int(SUN_CX - 430), int(SUN_CX + 430)
    gy0, gy1 = int(SUN_CY - 430), int(SUN_CY + 430)
    for y in range(max(0, gy0), min(H, gy1 + 1)):
        for x in range(max(0, gx0), min(W, gx1 + 1)):
            d = math.hypot(x - SUN_CX, y - SUN_CY)
            if d >= 430:
                continue
            fall = math.exp(-((d / 210.0) ** 2) * 1.6)
            a = 0.55 * fall
            # glow warms from orange at the edge to gold near the disc
            col = lerp3((255, 122, 48), (255, 196, 92), 1.0 - d / 430.0)
            cv.blend(x, y, col[0], col[1], col[2], a)

    # --- flame tongue licking up from the sun disc (narrow, leaning)
    cv.ellipse(710, 172, 42, 86, (255, 158, 52), 1.0, feather=10.0)
    cv.ellipse(708, 192, 24, 54, (255, 206, 96), 1.0, feather=8.0)
    # --- sun disc: bright core fading to orange at the rim
    cv.disc(SUN_CX, SUN_CY, SUN_R, (255, 176, 66), 1.0, feather=3.0)
    cv.disc(SUN_CX, SUN_CY, SUN_R - 22, (255, 214, 110), 1.0, feather=3.0)
    cv.disc(SUN_CX - 12, SUN_CY - 14, SUN_R - 52, (255, 246, 205), 1.0, feather=3.0)

    # --- sun reflection shimmering down the sea
    for y in range(HORIZON + 2, H):
        depth = (y - HORIZON) / (H - HORIZON)
        half = 150 * (1.0 - 0.45 * depth) * (1.0 + 0.16 * math.sin(y * 0.055))
        for x in range(int(SUN_CX - half), int(SUN_CX + half) + 1):
            if x < 0 or x >= W:
                continue
            wob = 0.5 + 0.5 * math.sin(x * 0.045 + y * 0.11)
            edge = 1.0 - abs(x - SUN_CX) / half
            a = 0.5 * (1.0 - depth) * edge * (0.6 + 0.4 * wob)
            cv.blend(x, y, 255, 158, 64, a)

    # --- the matchstick: diagonal from lower-left up to the sun
    hx, hy = 615.0, 415.0   # head, touching the sun disc's edge
    tx, ty = 268.0, 878.0   # tail
    dx, dy = tx - hx, ty - hy
    seg_len = math.hypot(dx, dy)
    ux, uy = dx / seg_len, dy / seg_len
    px_, py_ = -uy, ux  # perpendicular
    half_w = 13.0
    x0 = int(min(hx, tx) - half_w - 4)
    x1 = int(max(hx, tx) + half_w + 4)
    y0 = int(min(hy, ty) - half_w - 4)
    y1 = int(max(hy, ty) + half_w + 4)
    for y in range(max(0, y0), min(H, y1 + 1)):
        for x in range(max(0, x0), min(W, x1 + 1)):
            # distance from the point to the stick segment
            t = ((x - hx) * dx + (y - hy) * dy) / (seg_len * seg_len)
            t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
            cxp, cyp = hx + t * dx, hy + t * dy
            d = math.hypot(x - cxp, y - cyp)
            if d >= half_w + 1.5:
                continue
            a = 1.0 - smooth((d - half_w + 1.5) / 3.0)
            # wood: warm brown, lighter along the upper edge, darker below
            off = (x - cxp) * px_ + (y - cyp) * py_
            shade = 1.0 - 0.35 * (off / half_w)
            cv.blend(x, y, 168 * shade, 92 * shade, 48 * shade, a)

    # --- match head: dark ember bulb where the stick meets the flame
    cv.disc(hx, hy, 24, (52, 30, 34), 1.0, feather=3.0)
    cv.disc(hx - 4, hy - 6, 15, (255, 122, 36), 0.95, feather=3.0)
    cv.disc(hx - 6, hy - 8, 7, (255, 214, 130), 1.0, feather=2.0)

    # --- sparks bursting off the head and trailing down the stick
    for i in range(46):
        t = rng.range(0.0, 1.0)
        # sparks cluster near the head, thinning toward the tail
        along = (1.0 - t * t) * 0.9
        bx = hx + (tx - hx) * along
        by = hy + (ty - hy) * along
        ox = rng.range(-46, 46) * (0.4 + 0.6 * (1.0 - along))
        oy = rng.range(-52, 30) * (0.4 + 0.6 * (1.0 - along))
        sx, sy = bx + ox, by + oy
        sr = rng.range(1.6, 4.2)
        warm = rng.next()
        col = (255, 214, 120) if warm < 0.5 else (255, 150, 60)
        cv.disc(sx, sy, sr, col, rng.range(0.6, 1.0), feather=1.2)
        # a few sparks streak upward into the flame
        if i % 5 == 0:
            cv.disc(sx + rng.range(-8, 8), sy - rng.range(14, 30),
                    sr * 0.7, col, 0.7, feather=1.2)

    # --- three tiny birds for scale, high in the sky
    for bx, by, s in [(300, 300, 13), (345, 268, 10), (262, 252, 9)]:
        for sign in (-1, 1):
            for k in range(s):
                cv.blend(int(bx + sign * k), int(by + k * 0.45),
                         28, 22, 48, 0.9)
                cv.blend(int(bx + sign * k), int(by + k * 0.45) + 1,
                         28, 22, 48, 0.55)

    return cv


# ---------------------------------------------------------------- PNG out
def png_bytes(cv):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)  # filter: none
        raw += cv.px[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = png_bytes(render())
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path}: {len(data)} bytes, {W}x{H}")


if __name__ == "__main__":
    main()
