"""
Illusion Bowling  (pygame, 5 levels)

Install:  pip install pygame
Run:      python illusion_bowling.py

The ramp and the lane are two separate pieces, placed far apart along ONE line of
sight. The camera is orthographic (no perspective), so from exactly that angle the
two pieces line up and look like one connected track. Rotate the view until they
join, then roll.

Controls
  Mouse drag / arrow keys : rotate the view (let go near the angle and it snaps)
  A / D                   : aim left / right
  Z / X                   : spin left / right
  SPACE                   : roll (only works when the track looks joined)
  H                       : hint (animates to the right angle, limited per level)
  R                       : restart level      N / ENTER : next screen      ESC : quit
"""
import math
import random
import sys

import pygame

W, H = 1000, 650
R = 0.3                                   # ball radius
SLOPE = 3.5 / 5.5
COS = 1 / math.sqrt(1 + SLOPE * SLOPE)
LANE_LEN = 18.0
HOP_TIME = 0.1

BG = (205, 201, 159)
INK = (52, 51, 31)
YEL = (242, 207, 58)
RED = (200, 50, 30)
CREAM = (247, 245, 232)

# az/el = the secret angle (degrees). k = how far behind the ramp the lane hides.
# lw = lane width. tol = alignment tolerance (degrees). amp/freq = sliding pin rack.
LEVELS = [
    dict(name="First Light",   az=45, el=30, k=8,  lw=1.8, rows=3, need=5, rolls=3, tol=4.0, hints=99, amp=0.0,  freq=0.0, meter=True),
    dict(name="Other Side",    az=28, el=24, k=9,  lw=1.8, rows=4, need=7, rolls=3, tol=3.5, hints=3,  amp=0.0,  freq=0.0, meter=True),
    dict(name="Narrow Gauge",  az=62, el=36, k=7,  lw=1.3, rows=4, need=8, rolls=3, tol=3.0, hints=2,  amp=0.0,  freq=0.0, meter=True),
    dict(name="Sliding Rack",  az=38, el=42, k=10, lw=1.5, rows=4, need=8, rolls=3, tol=2.5, hints=1,  amp=0.30, freq=1.6, meter=True),
    dict(name="Needle's Eye",  az=52, el=20, k=11, lw=1.2, rows=4, need=9, rolls=3, tol=1.6, hints=0,  amp=0.40, freq=2.2, meter=False),
]


# ---------------------------------------------------------------- vector helpers
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def norm(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)
def dirv(az, el): return (math.cos(el) * math.sin(az), math.sin(el), math.cos(el) * math.cos(az))
def right_vec(az): return (math.cos(az), 0.0, -math.sin(az))
def up_vec(az, el): return (-math.sin(el) * math.sin(az), math.cos(el), -math.sin(el) * math.cos(az))
def centroid(vs): return mul((sum(v[0] for v in vs), sum(v[1] for v in vs), sum(v[2] for v in vs)), 1 / len(vs))
def lerp(a, b, t): return a + (b - a) * t


PIN_PROFILE = [(0.02, .10), (.05, .13), (.2, .15), (.4, .13), (.55, .08), (.65, .07), (.75, .09), (.82, .10), (.9, .07)]
LIGHT = norm((3, 6, 4))


class Pin:
    def __init__(self, x, z):
        self.x0, self.z0 = x, z
        self.reset()

    def reset(self):
        self.x, self.z = self.x0, self.z0
        self.state = "up"      # up / fall
        self.vis = True
        self.tilt = 0.0
        self.dx = self.dz = self.sp = 0.0

    def knock(self, fx, fz, sp):
        if self.state != "up":
            return
        l = math.hypot(fx, fz) or 1.0
        self.state, self.dx, self.dz, self.sp = "fall", fx / l, fz / l, sp


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Illusion Bowling")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.f_big = pygame.font.Font(None, 54)
        self.f_mid = pygame.font.Font(None, 32)
        self.f_small = pygame.font.Font(None, 24)
        self.level_i = 0
        self.total = 0
        self.mode = "intro"      # intro / play / rolling / win / lose / done
        self.load(0)

    # ------------------------------------------------------------ world building
    def load(self, i):
        self.level_i = i
        L = self.L = LEVELS[i]
        self.hz = L["lw"] / 2
        self.V0 = dirv(math.radians(L["az"]), math.radians(L["el"]))
        self.S2 = mul(self.V0, -L["k"])
        self.build_faces()
        self.build_pins()
        self.fit_view()
        sgn = 1 if i % 2 == 0 else -1
        self.az = math.radians(L["az"]) - 0.7 * sgn
        self.el = max(0.12, math.radians(L["el"]) - 0.3 * sgn)
        self.tween = None
        self.aim = 0.0
        self.spin = 0.0
        self.hints = L["hints"]
        self.rolls_left = L["rolls"]
        self.down = 0
        self.t = 0.0
        self.note = ""
        self.note_t = 0.0
        self.reset_ball()
        self.mode = "intro"

    def add_face(self, faces, verts, n, endcap=False):
        sh = 0.5 + 0.5 * max(0.0, dot(n, LIGHT))
        faces.append(dict(v=verts, n=n, c=centroid(verts), endcap=endcap,
                          col=tuple(int(ch * sh) for ch in YEL),
                          edge=tuple(int(ch * sh * 0.72) for ch in YEL)))

    def box(self, faces, x0, x1, y0, y1, z0, z1):
        P = lambda x, y, z: (x, y, z)
        self.add_face(faces, [P(x0, y1, z1), P(x1, y1, z1), P(x1, y0, z1), P(x0, y0, z1)], (0, 0, 1))
        self.add_face(faces, [P(x0, y1, z0), P(x0, y0, z0), P(x1, y0, z0), P(x1, y1, z0)], (0, 0, -1))
        self.add_face(faces, [P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z1), P(x0, y1, z1)], (0, 1, 0))
        self.add_face(faces, [P(x0, y0, z0), P(x0, y0, z1), P(x1, y0, z1), P(x1, y0, z0)], (0, -1, 0))
        self.add_face(faces, [P(x1, y1, z0), P(x1, y0, z0), P(x1, y0, z1), P(x1, y1, z1)], (1, 0, 0))
        self.add_face(faces, [P(x0, y1, z0), P(x0, y1, z1), P(x0, y0, z1), P(x0, y0, z0)], (-1, 0, 0))

    def build_faces(self):
        faces = []
        hz, S2 = self.hz, self.S2
        prof = [(-7, 3.5), (-1.5, 0), (0, 0), (0, -0.4), (-1.5, -0.4), (-7, 3.1)]
        area = sum(prof[i][0] * prof[(i + 1) % 6][1] - prof[(i + 1) % 6][0] * prof[i][1] for i in range(6))
        cw = area < 0
        self.add_face(faces, [(x, y, hz) for x, y in prof], (0, 0, 1))
        self.add_face(faces, [(x, y, -hz) for x, y in reversed(prof)], (0, 0, -1))
        for i in range(6):
            (x1, y1), (x2, y2) = prof[i], prof[(i + 1) % 6]
            dx, dy = x2 - x1, y2 - y1
            n = (-dy, dx, 0) if cw else (dy, -dx, 0)
            n = norm(n)
            # the flat end of the ramp is the piece that vanishes at the sweet spot
            self.add_face(faces, [(x1, y1, hz), (x2, y2, hz), (x2, y2, -hz), (x1, y1, -hz)], n, endcap=(i == 2))
        self.box(faces, -6.8, -5.8, -3.5, 2.7, -hz, hz)                                  # ramp pier
        self.box(faces, S2[0], S2[0] + LANE_LEN, S2[1] - 0.4, S2[1], S2[2] - hz, S2[2] + hz)   # lane
        self.box(faces, S2[0] + 1.0, S2[0] + 2.0, S2[1] - 3.4, S2[1] - 0.4, S2[2] - hz, S2[2] + hz)
        self.faces = faces

    def build_pins(self):
        L, S2 = self.L, self.S2
        self.hx = S2[0] + 14
        gap = min(0.5, (L["lw"] - 0.3) / (L["rows"] - 1 + 0.0001) / 1.0)
        gap = min(0.5, (L["lw"] - 0.3) / max(1, L["rows"] - 1))
        self.pins = []
        for r in range(L["rows"]):
            for i in range(r + 1):
                self.pins.append(Pin(self.hx + r * 0.45, S2[2] + (i - r / 2) * gap))

    def fit_view(self):
        a, e = math.radians(self.L["az"]), math.radians(self.L["el"])
        r, u = right_vec(a), up_vec(a, e)
        xs, ys = [], []
        for f in self.faces:
            for v in f["v"]:
                xs.append(dot(v, r))
                ys.append(dot(v, u))
        bw, bh = max(xs) - min(xs), max(ys) - min(ys) + 1.2
        self.scale = min(W * 0.9 / bw, H * 0.6 / bh)
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        self.T = add(mul(r, cx), mul(u, cy))

    def reset_ball(self):
        self.ph = 0
        self.bx = -6.6
        self.vs = 0.0
        self.bt = 0.0
        self.gutter = False
        self.wait = 0.0
        self.rot = 0.0
        self.ball = [self.bx, self.slope_y(self.bx), 0.0]
        self.ball_vis = True

    @staticmethod
    def slope_y(x):
        return (-1.5 - x) * SLOPE + R / COS if x < -1.5 else R

    # ------------------------------------------------------------------- helpers
    def world_aim(self):
        return -self.aim * (self.hz - 0.2)

    def world_spin(self):
        return -self.spin * self.L["lw"] * 0.45

    def err(self):
        v = dirv(self.az, self.el)
        return math.acos(max(-1.0, min(1.0, dot(v, self.V0))))

    def aligned(self):
        return self.err() < math.radians(self.L["tol"])

    def proj(self, p):
        q = sub(p, self.T)
        r, u = right_vec(self.az), up_vec(self.az, self.el)
        return (W / 2 + dot(q, r) * self.scale, H * 0.47 - dot(q, u) * self.scale)

    def start_tween(self):
        self.tween = dict(t=0.0, a=self.az, e=self.el)

    def say(self, s):
        self.note, self.note_t = s, 2.4

    # --------------------------------------------------------------------- input
    def roll(self):
        if self.mode != "play" or not self.aligned():
            return
        self.ph, self.mode = 1, "rolling"
        self.b_aim, self.b_spin = self.world_aim(), self.world_spin()

    def hint(self):
        if self.mode in ("play", "rolling") and self.hints > 0:
            self.hints -= 1
            self.start_tween()

    def advance(self):
        if self.mode == "intro":
            self.mode = "play"
        elif self.mode == "win":
            if self.level_i + 1 < len(LEVELS):
                self.load(self.level_i + 1)
            else:
                self.mode = "done"
        elif self.mode == "lose":
            self.load(self.level_i)
        elif self.mode == "done":
            self.total = 0
            self.load(0)

    def handle_event(self, e):
        if e.type == pygame.QUIT:
            pygame.quit(); sys.exit()
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                pygame.quit(); sys.exit()
            elif e.key == pygame.K_SPACE:
                self.advance() if self.mode != "play" and self.mode != "rolling" else self.roll()
            elif e.key in (pygame.K_RETURN, pygame.K_n):
                self.advance()
            elif e.key == pygame.K_h:
                self.hint()
            elif e.key == pygame.K_r and self.mode in ("play", "rolling", "lose"):
                self.load(self.level_i); self.mode = "play"
        if e.type == pygame.KEYUP and e.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
            if self.err() < 0.12:
                self.start_tween()
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.drag = True
            self.tween = None
            pygame.mouse.get_rel()
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if getattr(self, "drag", False) and self.err() < 0.12:
                self.start_tween()
            self.drag = False
        if e.type == pygame.MOUSEMOTION and getattr(self, "drag", False):
            self.az -= e.rel[0] * 0.006
            self.el = min(1.3, max(0.05, self.el + e.rel[1] * 0.006))

    # -------------------------------------------------------------------- update
    def update(self, dt):
        self.t += dt
        keys = pygame.key.get_pressed()
        if self.mode in ("play", "rolling"):
            if keys[pygame.K_LEFT] or keys[pygame.K_RIGHT] or keys[pygame.K_UP] or keys[pygame.K_DOWN]:
                self.tween = None
            self.az += (keys[pygame.K_LEFT] - keys[pygame.K_RIGHT]) * 1.2 * dt
            self.el = min(1.3, max(0.05, self.el + (keys[pygame.K_DOWN] - keys[pygame.K_UP]) * 1.2 * dt))
            if self.mode == "play":
                self.aim = max(-1, min(1, self.aim + (keys[pygame.K_d] - keys[pygame.K_a]) * 1.3 * dt))
                self.spin = max(-1, min(1, self.spin + (keys[pygame.K_x] - keys[pygame.K_z]) * 1.3 * dt))
        if self.tween:
            tw = self.tween
            tw["t"] += dt / 0.35
            k = min(1.0, tw["t"])
            s = k * k * (3 - 2 * k)
            self.az = lerp(tw["a"], math.radians(self.L["az"]), s)
            self.el = lerp(tw["e"], math.radians(self.L["el"]), s)
            if k >= 1:
                self.tween = None
        if self.note_t > 0:
            self.note_t -= dt

        S2 = self.S2
        if self.ph == 0:
            self.ball = [self.bx, self.slope_y(self.bx), self.world_aim()]
        elif self.ph == 1:
            self.vs += 7 * dt
            self.bx += self.vs * COS * dt
            self.rot -= self.vs * dt / R
            if self.bx >= 0:
                self.bx, self.ph, self.bt = 0.0, 2, 0.0
            self.ball = [self.bx, self.slope_y(self.bx), self.b_aim]
        elif self.ph == 2:
            self.bt += dt
            u = min(1.0, self.bt / HOP_TIME)
            self.ball = [S2[0] * u, R + S2[1] * u, self.b_aim + S2[2] * u]
            if u >= 1:
                self.ph, self.bx = 3, S2[0]
        elif self.ph == 3:
            self.bx += self.vs * dt
            self.rot -= self.vs * dt / R
            d = (self.bx - S2[0]) / 14
            zo = self.b_aim + self.b_spin * d * d
            if abs(zo) > self.hz + 0.05:
                self.gutter = True
            y = S2[1] + R - (0.3 if self.gutter else 0)
            self.ball = [self.bx, y, S2[2] + zo]
            if not self.gutter:
                for p in self.pins:
                    if p.state != "up":
                        continue
                    ex, ez = p.x - self.ball[0], p.z - self.ball[2]
                    if ex * ex + ez * ez < 0.2:
                        p.knock(ex + 0.5, ez * 1.5, 3 + self.vs * 0.3 + random.random())
                        self.vs *= 0.985
            if self.bx > S2[0] + LANE_LEN - 0.4:
                self.ph, self.wait, self.ball_vis = 4, 1.3, False
        elif self.ph == 4:
            self.wait -= dt
            if self.wait <= 0:
                self.ph = 5
                self.finish_roll()

        L = self.L
        shift = L["amp"] * math.sin(L["freq"] * self.t) if L["amp"] else 0.0
        for p in self.pins:
            if p.state == "up":
                p.z = p.z0 + shift
                continue
            p.tilt = min(math.pi / 2, p.tilt + dt * 3.6)
            p.x += p.dx * p.sp * dt
            p.z += p.dz * p.sp * dt
            p.sp *= math.exp(-1.6 * dt)
            if p.sp > 1.2:
                for q in self.pins:
                    if q.state == "up":
                        ex, ez = q.x - p.x, q.z - p.z
                        if ex * ex + ez * ez < 0.11:
                            q.knock(ex, ez, p.sp * 0.7)

    def finish_roll(self):
        fell = [p for p in self.pins if p.vis and p.state != "up"]
        for p in fell:
            p.vis = False
        n = len(fell)
        self.down += n
        self.rolls_left -= 1
        total = len(self.pins)
        if self.down >= self.L["need"] or self.down >= total:
            self.stars = 3 if self.rolls_left >= self.L["rolls"] - 1 else (2 if self.rolls_left >= 1 else 1)
            self.gain = self.down * 10 + self.rolls_left * 25 + self.stars * 20
            self.total += self.gain
            self.mode = "win"
        elif self.rolls_left <= 0:
            self.mode = "lose"
        else:
            self.say("%d down" % n if n else "Missed!")
            self.reset_ball()
            self.mode = "play"
            return
        self.reset_ball()

    # ---------------------------------------------------------------------- draw
    def draw_world(self):
        v = dirv(self.az, self.el)
        near_join = self.err() < 0.03
        vis = []
        for f in self.faces:
            if dot(f["n"], v) <= 0.0:
                continue
            if f["endcap"] and near_join:
                continue
            vis.append(f)
        vis.sort(key=lambda f: dot(f["c"], v))
        for f in vis:
            pts = [self.proj(p) for p in f["v"]]
            pygame.draw.polygon(self.screen, f["col"], pts)
            pygame.draw.polygon(self.screen, f["edge"], pts, 1)

        items = []
        for p in self.pins:
            if p.vis:
                items.append((dot((p.x, self.S2[1], p.z), v), "pin", p))
        if self.ball_vis:
            items.append((dot(self.ball, v), "ball", None))
        items.sort(key=lambda it: it[0])
        for _, kind, p in items:
            self.draw_pin(p, v) if kind == "pin" else self.draw_ball(v)

    def draw_pin(self, p, v):
        s = math.sin(p.tilt)
        axis = (p.dx * s, math.cos(p.tilt), p.dz * s)
        base = (p.x, self.S2[1] + s * 0.15, p.z)
        order = PIN_PROFILE if dot(axis, v) > 0 else list(reversed(PIN_PROFILE))
        sh = 0.55 + 0.45 * max(0.0, dot(axis, LIGHT) * 0.5 + 0.5)
        for h, r in order:
            c = add(base, mul(axis, h))
            x, y = self.proj(c)
            col = (200, 50, 30) if 0.5 < h < 0.7 else CREAM
            col = tuple(int(ch * sh) for ch in col)
            pygame.draw.circle(self.screen, col, (int(x), int(y)), max(2, int(r * self.scale)))
            pygame.draw.circle(self.screen, (120, 116, 90), (int(x), int(y)), max(2, int(r * self.scale)), 1)

    def draw_ball(self, v):
        x, y = self.proj(self.ball)
        rad = max(3, int(R * self.scale))
        pygame.draw.circle(self.screen, RED, (int(x), int(y)), rad)
        pygame.draw.circle(self.screen, (240, 120, 100), (int(x - rad * 0.3), int(y - rad * 0.3)), max(2, rad // 4))
        off = norm((0.5, 0.6, 0.62))
        c, s = math.cos(self.rot), math.sin(self.rot)
        off = (off[0] * c - off[1] * s, off[0] * s + off[1] * c, off[2])
        if dot(off, v) > 0:
            dp = self.proj(add(self.ball, mul(off, R * 0.98)))
            pygame.draw.circle(self.screen, (255, 243, 208), (int(dp[0]), int(dp[1])), max(2, rad // 4))
        pygame.draw.circle(self.screen, (110, 25, 15), (int(x), int(y)), rad, 1)

    def text(self, s, font, x, y, col=INK, center=False):
        img = font.render(s, True, col)
        rect = img.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(img, rect)

    def draw_hud(self):
        L = self.L
        self.text("Level %d: %s" % (self.level_i + 1, L["name"]), self.f_mid, 16, 12)
        self.text("Knock down %d of %d pins in %d rolls" % (L["need"], len(self.pins), L["rolls"]), self.f_small, 16, 42)
        self.text("Pins down %d   Rolls left %d   Hints %s   Score %d" %
                  (self.down, self.rolls_left, "-" if L["hints"] == 99 else self.hints, self.total), self.f_small, 16, 64)
        if self.mode in ("play", "rolling"):
            if L["meter"]:
                e = math.degrees(self.err())
                fill = max(0.0, 1 - e / 40)
                pygame.draw.rect(self.screen, INK, (W - 216, 16, 200, 14), 2)
                col = (60, 150, 60) if self.aligned() else (200, 130, 40)
                pygame.draw.rect(self.screen, col, (W - 214, 18, int(196 * fill), 10))
                self.text("closeness", self.f_small, W - 216, 34)
            if self.mode == "play":
                msg = "Track joined. A/D aim, Z/X spin, SPACE to roll." if self.aligned() \
                    else "Rotate until the ramp and the lane join into one track."
            else:
                msg = "Rolling. Rotate to see how the ball hops between pieces."
            if self.note_t > 0:
                msg = self.note + "   " + msg
            self.text(msg, self.f_mid, W // 2, H - 62, center=True)
            self.text("Drag / arrows rotate     H hint     R restart", self.f_small, W // 2, H - 30, center=True)
            self.text("aim %+.2f   spin %+.2f" % (self.aim, self.spin), self.f_small, W // 2, H - 92, INK, True)

    def overlay(self, title, lines):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((205, 201, 159, 215))
        self.screen.blit(s, (0, 0))
        self.text(title, self.f_big, W // 2, H // 2 - 80, INK, True)
        for i, ln in enumerate(lines):
            self.text(ln, self.f_mid, W // 2, H // 2 - 20 + i * 36, INK, True)

    def draw(self):
        self.screen.fill(BG)
        self.draw_world()
        self.draw_hud()
        L = self.L
        if self.mode == "intro":
            self.overlay("Level %d: %s" % (self.level_i + 1, L["name"]),
                         ["Knock down %d of %d pins using %d rolls." % (L["need"], len(self.pins), L["rolls"]),
                          "Find the one angle where the ramp and lane look like a single track.",
                          "Press SPACE to start"])
        elif self.mode == "win":
            self.overlay("Level complete", ["Stars: " + "*" * self.stars + "-" * (3 - self.stars) + "     +%d points" % self.gain,
                                            "Press SPACE for " + ("the next level" if self.level_i + 1 < len(LEVELS) else "the finish")])
        elif self.mode == "lose":
            self.overlay("Out of rolls", ["You knocked down %d of the %d you needed." % (self.down, L["need"]),
                                          "Press SPACE to try the level again"])
        elif self.mode == "done":
            self.overlay("You beat all 5 levels", ["Final score: %d" % self.total, "Press SPACE to play again"])
        pygame.display.flip()

    def run(self):
        while True:
            dt = min(0.033, self.clock.tick(60) / 1000)
            for e in pygame.event.get():
                self.handle_event(e)
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    Game().run()