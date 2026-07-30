#!/usr/bin/env python3
"""
Monte Carlo face-validity check for an OGE world graph.

Face validity is a property of TRAJECTORIES, not of the static node/edge list: you cannot see
"a stock collapses but its consequences never follow" by reading the graph. So this script drives
the graph with thousands of random-but-realistic decision streams through the same deterministic
propagation physics the preview uses, then measures the resulting ensemble against:

  SCANNERS (descriptive)         - per-node rail-hit rate, dead nodes, outcome skew, stability,
                                   node co-movement — surface the obvious pathologies.
  INVARIANTS (prescriptive)      - author-declared domain plausibility rules the ensemble must
                                   mostly satisfy: pointwise ("this should hold each round"),
                                   coupling ("if A collapses, B must follow within N rounds"), and
                                   correlation ("A and B should move together over a run").

The coupling invariant is what catches the class of bug where e.g. war-sustainability grinds to ~0
while the frontline and combat tempo are unaffected — found statistically over random play, with no
LLM and no live game.

Output: a `face_validity` JSON block (checks[] with pass/warn/fail + evidence) written to
<out> and printed. It is consumed by the build gate (gate_face_validity.py); this script only
PRODUCES results, it does not decide whether the build ships.

Usage:
  python3 mc_face_validity.py GRAPH.json [--invariants INV.yaml] [--runs 2000] [--rounds 24]
                              [--rail-zone 0] [--rail-power 1] [--out face_validity.json] [--seed 7]

Self-contained: embeds the propagation engine (same physics as render_preview.py); no imports beyond
the stdlib. YAML invariants are read with a tiny built-in parser if PyYAML is absent.
"""
import argparse
import json
import math
import random
import statistics
import sys

# ---------------- engine (compact port of the preview physics) ----------------
SPEED = 0.7
SAT_A = 0.38
MINV, MAXV = 0.0, 1.0
RATES = {"Lever": (0.0, 0.0), "Level": (0.12, 0.22),
         "Accumulator": (0.06, 0.13), "Drifter": (0.10, 0.18)}
def edge_gain(s):
    # strength is a number in [0, 1]
    return float(s) if isinstance(s, (int, float)) and not isinstance(s, bool) else 0.6


class Engine:
    """Deterministic propagation over a world graph. State is tracked as deviation from baseline;
    absolute value = base + dev, held in [0,1]. Optional rail resistance attenuates movement
    toward a 0/1 rail (rail_zone=0 => plain hard clamp, matching the preview)."""

    def __init__(self, graph, rail_zone=0.0, rail_power=1.0):
        self.rail_zone = float(rail_zone)
        self.rail_power = float(rail_power)
        nodes = graph["nodes"]
        self.ids = [n["id"] for n in nodes]
        by_id = {n["id"]: n for n in nodes}
        self.base, self.aup, self.adn, self.want, self.type = {}, {}, {}, {}, {}
        for n in nodes:
            au, ad = RATES.get(n["type"], RATES["Level"])
            self.base[n["id"]] = float(n["baseline"])
            self.aup[n["id"]] = au * SPEED
            self.adn[n["id"]] = ad * SPEED
            self.want[n["id"]] = not bool(n.get("inverted"))
            self.type[n["id"]] = n["type"]
        self.incoming = {i: [] for i in self.ids}
        for e in graph["edges"]:
            if e["source"] in by_id and e["target"] in by_id:
                w = edge_gain(e.get("strength", 0.6)) * (1 if e.get("sign", "+") == "+" else -1)
                self.incoming[e["target"]].append((e["source"], w, int(e.get("lag", 1))))

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
        cn, cl = w * SAT_A * math.tanh(now / SAT_A), w * SAT_A * math.tanh(lag / SAT_A)
        return (cn if cn <= cl else cl) if want_high else (cn if cn >= cl else cl)

    def run(self, shocks, total_ticks):
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
            nx = {}
            for i in self.ids:
                v = cur[i]
                if ac[i]:
                    a = self.aup[i] if tg[i] >= v else self.adn[i]
                    v = self._move(v, a * (tg[i] - v), i)
                else:
                    v = self._clamp_dev(v, i)
                nx[i] = v
            if (t + 1) in shocks:
                for i, amt in shocks[t + 1].items():
                    if i in nx:
                        nx[i] = self._move(nx[i], amt, i)
            dev.append(nx)
        return [{i: self.base[i] + d[i] for i in self.ids} for d in dev]


# ---------------- random decision-stream generator ----------------
TIERS = {"T1": 0.03, "T2": 0.06, "T3": 0.11, "T4": 0.18}
TIER_KEYS, TIER_W = ["T1", "T2", "T3", "T4"], [4, 3, 2, 1]
EFF = [0.6, 1.0, 1.3]


def sample_game(eng, rounds, tpr, cap, teams, rng):
    """One random episode: each round, `teams`*`cap` landings of tier*eff*sign on random nodes.
    Returns per-round absolute-value states (list length `rounds`)."""
    shocks = {}
    for r in range(rounds):
        b = shocks.setdefault(r * tpr, {})
        for _ in range(teams * cap):
            i = rng.choice(eng.ids)
            d = TIERS[rng.choices(TIER_KEYS, weights=TIER_W)[0]] * rng.choice(EFF) * rng.choice([-1, 1])
            b[i] = b.get(i, 0.0) + d
    traj = eng.run(shocks, rounds * tpr)
    return [traj[k * tpr] for k in range(1, rounds + 1)]


# ---------------- safe expression evaluation for invariant rules ----------------
def make_eval(expr):
    code = compile(expr, "<invariant>", "eval")
    for name in code.co_names:
        if name in ("__import__", "eval", "exec", "open", "globals", "locals"):
            raise ValueError(f"disallowed name in rule: {name}")

    def f(state):
        return bool(eval(code, {"__builtins__": {}}, state))
    return f


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


# ---------------- invariant evaluation over the ensemble ----------------
def eval_invariants(games, invs):
    """games: list of runs; each run = list of round-state dicts. Returns list of check dicts."""
    checks = []
    for inv in invs:
        kind = inv.get("kind")
        iid = inv["id"]
        thr = float(inv.get("max_violation_rate", 0.05))
        if kind == "pointwise":
            test = make_eval(inv["rule"])
            tot = viol = 0
            for run in games:
                for st in run:
                    tot += 1
                    if not test(st):
                        viol += 1
            rate = viol / tot if tot else 0.0
            checks.append(_mk(iid, "violation_rate", round(rate, 3), f"<= {thr}", rate <= thr,
                              f"{viol}/{tot} rounds violate `{inv['rule']}`"))
        elif kind == "coupling":
            when, then = make_eval(inv["when"]), make_eval(inv["then"])
            within = int(inv.get("within_rounds", 3))
            qual = viol = 0
            for run in games:
                n = len(run)
                for r in range(n):
                    if when(run[r]):
                        qual += 1
                        if not any(then(run[j]) for j in range(r, min(n, r + within + 1))):
                            viol += 1
            rate = viol / qual if qual else 0.0
            ev = (f"in {qual} rounds where `{inv['when']}`, `{inv['then']}` failed to follow within "
                  f"{within} rounds {viol} times ({round((1-rate)*100)}% coupled)")
            status_ok = (qual == 0) or (rate <= thr)
            checks.append(_mk(iid, "violation_rate", round(rate, 3) if qual else None,
                              f"<= {thr}", status_ok, ev if qual else "no qualifying rounds sampled"))
        elif kind == "correlation":
            a, b = inv["a"], inv["b"]
            op, want = _parse_expect(inv.get("expect", ">= 0.25"))
            corrs = []
            for run in games:
                xs = [st[a] for st in run if a in st]
                ys = [st[b] for st in run if b in st]
                if len(xs) == len(ys) and len(xs) >= 3:
                    corrs.append(pearson(xs, ys))
            mean_c = round(statistics.mean(corrs), 3) if corrs else 0.0
            ok = op(mean_c, want)
            checks.append(_mk(iid, "mean_run_correlation", mean_c, f"{inv.get('expect')}", ok,
                              f"mean within-run corr({a},{b}) = {mean_c} over {len(corrs)} runs"))
        else:
            checks.append(_mk(iid, "kind", kind, "known kind", False, f"unknown invariant kind '{kind}'"))
    return checks


def _parse_expect(s):
    s = s.strip()
    for sym, fn in ((">=", lambda a, b: a >= b), ("<=", lambda a, b: a <= b),
                    (">", lambda a, b: a > b), ("<", lambda a, b: a < b)):
        if s.startswith(sym):
            return fn, float(s[len(sym):])
    return (lambda a, b: a >= b), float(s)


def _mk(cid, metric, value, threshold, ok, evidence, warn=False):
    status = "pass" if ok else ("warn" if warn else "fail")
    return {"id": cid, "metric": metric, "value": value, "threshold": threshold,
            "status": status, "evidence": evidence}


# ---------------- scanners (always on; no authoring needed) ----------------
def scanners(eng, games, cfg):
    checks = []
    ids = eng.ids
    N = len(games)
    # rail-hit rate per node (value within 0.01 of a 0/1 rail in any round of a run)
    hit = {i: 0 for i in ids}
    for run in games:
        seen = set()
        for st in run:
            for i in ids:
                if i not in seen and (st[i] <= 0.01 or st[i] >= 0.99):
                    seen.add(i)
        for i in seen:
            hit[i] += 1
    worst = max(ids, key=lambda i: hit[i])
    worst_rate = round(hit[worst] / N, 3) if N else 0.0
    thr = cfg["rail_hit_max"]
    offenders = sorted([(i, round(hit[i] / N, 3)) for i in ids if N and hit[i] / N > thr],
                       key=lambda x: -x[1])
    checks.append(_mk("node_rail_hits", "worst_node_rate", f"{worst} {worst_rate}",
                      f"<= {thr}", worst_rate <= thr,
                      f"{len(offenders)} nodes exceed {thr}: " + ", ".join(f"{i}={r}" for i, r in offenders[:8]),
                      warn=True))
    # dead nodes: never move > 0.05 from baseline in ANY run
    moved = {i: False for i in ids}
    for run in games:
        for st in run:
            for i in ids:
                if abs(st[i] - eng.base[i]) > 0.05:
                    moved[i] = True
    dead = [i for i in ids if not moved[i]]
    checks.append(_mk("dead_nodes", "count", len(dead), "0", len(dead) == 0,
                      "frozen: " + (", ".join(dead) if dead else "none")))
    # outcome skew (if outcome win_rule provided)
    if cfg.get("win_rule") and cfg.get("outcome_nodes"):
        tally = {}
        for run in games:
            o = _classify(run[-1], cfg["win_rule"])
            tally[o] = tally.get(o, 0) + 1
        share = max(tally.values()) / N if N else 0.0
        thr2 = cfg["skew_max"]
        checks.append(_mk("neutral_play_skew", "max_outcome_share", round(share, 3),
                          f"<= {thr2} or waived", share <= thr2, f"distribution {tally}", warn=True))
    # stability: any NaN / out-of-bounds anywhere
    oob = 0
    for run in games:
        for st in run:
            for v in st.values():
                if v != v or v < -1e-6 or v > 1 + 1e-6:
                    oob += 1
    checks.append(_mk("boundedness", "violations", oob, "0", oob == 0,
                      "no out-of-bounds" if oob == 0 else f"{oob} out-of-bounds values"))
    return checks


def _classify(final, win_rule):
    env = dict(final)
    for label, expr in win_rule.items():
        if label == "else":
            continue
        try:
            if eval(compile(expr, "<win>", "eval"), {"__builtins__": {}}, env):
                return label
        except Exception:
            return "eval_error"
    return win_rule.get("else", "undecided")


# ---------------- tiny YAML reader (fallback if PyYAML absent) ----------------
def load_invariants(path):
    if not path:
        return {}, {}
    try:
        import yaml
        doc = yaml.safe_load(open(path)) or {}
        return doc.get("invariants", []), doc.get("config", {})
    except ImportError:
        return _mini_yaml(open(path).read())


def _mini_yaml(text):
    """Minimal parser for the subset used here: a top-level `config:` map and an `invariants:` list
    of flat maps. Values are str/float/int; quotes optional. Not general YAML."""
    invariants, config = [], {}
    section, cur = None, None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if indent == 0 and line.rstrip(":") in ("invariants", "config"):
            section = line.rstrip(":")
            continue
        if section == "config" and indent >= 2 and ":" in line:
            k, v = line.split(":", 1)
            config[k.strip()] = _coerce(v.strip())
        elif section == "invariants":
            if line.startswith("- "):
                cur = {}
                invariants.append(cur)
                line = line[2:].strip()
                if ":" in line:
                    k, v = line.split(":", 1)
                    cur[k.strip()] = _coerce(v.strip())
            elif cur is not None and ":" in line:
                k, v = line.split(":", 1)
                cur[k.strip()] = _coerce(v.strip())
    return invariants, config


def _coerce(v):
    v = v.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("graph")
    ap.add_argument("--invariants")
    ap.add_argument("--runs", type=int, default=2000)
    ap.add_argument("--rounds", type=int, default=24)
    ap.add_argument("--tpr", type=int, default=6)
    ap.add_argument("--teams", type=int, default=4)
    ap.add_argument("--cap", type=int, default=3)
    ap.add_argument("--rail-zone", type=float, default=0.0)
    ap.add_argument("--rail-power", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    graph = json.load(open(args.graph))
    eng = Engine(graph, rail_zone=args.rail_zone, rail_power=args.rail_power)
    invs, inv_cfg = load_invariants(args.invariants)

    cfg = {"rail_hit_max": 0.30, "skew_max": 0.70}
    cfg.update({k: inv_cfg[k] for k in ("rail_hit_max", "skew_max", "win_rule", "outcome_nodes") if k in inv_cfg})

    rng = random.Random(args.seed)
    games = [sample_game(eng, args.rounds, args.tpr, args.cap, args.teams, rng) for _ in range(args.runs)]

    checks = scanners(eng, games, cfg) + eval_invariants(games, invs)
    n_fail = sum(1 for c in checks if c["status"] == "fail")
    n_warn = sum(1 for c in checks if c["status"] == "warn")
    block = {"face_validity": {
        "generated": True,
        "method": f"monte_carlo random-play n={args.runs} rounds={args.rounds} "
                  f"rails=({args.rail_zone},{args.rail_power}) seed={args.seed}",
        "n_fail": n_fail, "n_warn": n_warn, "n_pass": len(checks) - n_fail - n_warn,
        "checks": checks, "dispositions": []}}

    out = args.out or (args.graph.rsplit(".", 1)[0] + ".face_validity.json")
    json.dump(block, open(out, "w"), indent=2)

    print(f"Monte Carlo face validity — {args.runs} runs x {args.rounds} rounds "
          f"(rails {args.rail_zone}/{args.rail_power})")
    print(f"{'STATUS':6} {'CHECK':26} {'VALUE':>16}  THRESHOLD")
    for c in checks:
        mark = {"pass": "PASS", "warn": "warn", "fail": "FAIL"}[c["status"]]
        print(f"{mark:6} {c['id']:26} {str(c['value']):>16}  {c['threshold']}")
        if c["status"] != "pass":
            print(f"       └ {c['evidence']}")
    print(f"\n{block['face_validity']['n_pass']} pass / {n_warn} warn / {n_fail} fail  ->  {out}")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
