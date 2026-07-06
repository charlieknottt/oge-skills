#!/usr/bin/env python3
"""
engine.py - the OGE world-graph propagation physics, in one place.

This is the SINGLE Python source of truth for how a world graph propagates:
split-alpha goal-seek (slow up, fast down), tanh saturation, and the asymmetric
"worse-of {now, lag-steps-ago}" rule that makes harm land fast while benefit waits
out the full lag. It is imported by the deterministic dynamic checks
(behavior_gate.py, and later the behavior-rule Monte Carlo). No LLM, stdlib only.

render_preview.py embeds the SAME physics in JavaScript for the playable demo. That
copy cannot import this module (it ships inside standalone HTML), so it is a mirror:
the constants and the contrib/goal-seek logic here are the reference. If you change
the physics, change both. (A test asserts the shared constants match.)

State is tracked as deviation from each node's baseline; the absolute value is
base + dev, held in [0, 100].
"""
import math

SPEED = 0.7
SAT_A = 38.0
MINV, MAXV = 0.0, 100.0

# node behavior -> (alpha_up slow, alpha_down fast). Levers hold at (0,0): they move
# only on a direct shock, never goal-seek. "Bad happens faster than good" lives here.
RATES = {
    "Lever": (0.0, 0.0),
    "Level": (0.12, 0.22),
    "Accumulator": (0.06, 0.13),
    "Drifter": (0.10, 0.18),
}


def mag_weight(m):
    """Edge magnitude as a float in [0,1]. Tolerates the legacy weak/moderate/strong strings."""
    if isinstance(m, bool):
        return 0.6
    if isinstance(m, (int, float)):
        return float(m)
    return {"weak": 0.35, "moderate": 0.6, "strong": 0.9}.get(m, 0.6)


class Engine:
    """Deterministic propagation over a lean world_graph.json.

    graph: {"nodes": [...], "edges": [...]}.
    rail_zone/rail_power: optional soft-rail resistance near 0/100; the default
    (rail_zone=0) is a plain hard clamp, matching render_preview.py exactly.
    """

    def __init__(self, graph, rail_zone=0.0, rail_power=1.0):
        self.rail_zone = float(rail_zone)
        self.rail_power = float(rail_power)
        nodes = graph["nodes"]
        by_id = {n["id"]: n for n in nodes}
        # de-dupe ids: a duplicate id would double-count in downstream per-node tallies. The graph
        # schema forbids duplicates, but the engine should not misbehave if handed an unvalidated one.
        self.ids = list(dict.fromkeys(n["id"] for n in nodes))
        self.base, self.aup, self.adn, self.want, self.type = {}, {}, {}, {}, {}
        for n in nodes:
            au, ad = RATES.get(n["type"], RATES["Level"])
            self.base[n["id"]] = float(n["starting_value"])
            self.aup[n["id"]] = au * SPEED
            self.adn[n["id"]] = ad * SPEED
            self.want[n["id"]] = not bool(n.get("inverted"))
            self.type[n["id"]] = n["type"]
        self.incoming = {i: [] for i in self.ids}
        for e in graph["edges"]:
            if e["source"] in by_id and e["target"] in by_id:
                w = mag_weight(e.get("magnitude", 0.6)) * (1 if e.get("sign", "+") == "+" else -1)
                self.incoming[e["target"]].append((e["source"], w, max(0, int(e.get("lag", 1)))))

    def _move(self, dev_val, delta, i):
        val = self.base[i] + dev_val
        if self.rail_zone > 0 and delta != 0:
            head = (MAXV - val) if delta > 0 else val
            f = min(1.0, head / self.rail_zone) ** self.rail_power
            val = val + delta * f
        else:
            val = val + delta
        val = max(MINV, min(MAXV, val))
        return val - self.base[i]

    def _clamp_dev(self, d, i):
        return max(MINV - self.base[i], min(MAXV - self.base[i], d))

    def _contrib(self, now, lag, w, want_high):
        cn = w * SAT_A * math.tanh(now / SAT_A)
        cl = w * SAT_A * math.tanh(lag / SAT_A)
        # asymmetric lag: take the WORSE of {now, lag-steps-ago} for this target.
        return (cn if cn <= cl else cl) if want_high else (cn if cn >= cl else cl)

    def run(self, shocks, total_ticks):
        """shocks: {tick: {node_id: amount}}. Returns per-tick ABSOLUTE-value states,
        a list of length total_ticks + 1 (index 0 = start)."""
        dev = [{i: 0.0 for i in self.ids}]
        if 0 in shocks:
            for i, amt in shocks[0].items():
                if i in dev[0]:
                    dev[0][i] = self._move(dev[0][i], amt, i)
        for t in range(total_ticks):
            cur = dev[t]
            tg = {i: 0.0 for i in self.ids}
            ac = {i: False for i in self.ids}
            for i in self.ids:
                for (s, w, lag) in self.incoming[i]:
                    lg = dev[t - lag][s] if (t - lag) >= 0 else 0.0
                    c = self._contrib(cur[s], lg, w, self.want[i])
                    tg[i] += c
                    if abs(c) > 1e-6:
                        ac[i] = True
            nxt = {}
            for i in self.ids:
                v = cur[i]
                if ac[i]:
                    a = self.aup[i] if tg[i] >= v else self.adn[i]
                    v = self._move(v, a * (tg[i] - v), i)
                else:
                    v = self._clamp_dev(v, i)
                nxt[i] = v
            if (t + 1) in shocks:
                for i, amt in shocks[t + 1].items():
                    if i in nxt:
                        nxt[i] = self._move(nxt[i], amt, i)
            dev.append(nxt)
        return [{i: self.base[i] + d[i] for i in self.ids} for d in dev]


# ---------- random decision-stream driver (shared by the behavior gate and the rule check) ----------
# Each round drops `teams`*`cap` random "landings" of tier*effort*sign on random nodes -- a rough
# stand-in for the many different ways a game could be played. Deterministic given `rng`.
TIERS = {"T1": 3, "T2": 6, "T3": 11, "T4": 18}
TIER_KEYS, TIER_W = ["T1", "T2", "T3", "T4"], [4, 3, 2, 1]
EFF = [0.6, 1.0, 1.3]


def sample_game(eng, rounds, tpr, cap, teams, rng):
    """One random episode; returns per-round absolute-value states (a list of length `rounds`)."""
    shocks = {}
    for r in range(rounds):
        b = shocks.setdefault(r * tpr, {})
        for _ in range(teams * cap):
            i = rng.choice(eng.ids)
            d = TIERS[rng.choices(TIER_KEYS, weights=TIER_W)[0]] * rng.choice(EFF) * rng.choice([-1, 1])
            b[i] = b.get(i, 0.0) + d
    traj = eng.run(shocks, rounds * tpr)
    return [traj[k * tpr] for k in range(1, rounds + 1)]
