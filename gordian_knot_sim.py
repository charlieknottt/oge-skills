#!/usr/bin/env python3
"""
Gordian Knot Supply Chain Crisis Simulation
Run this file to generate gordian_knot_sim.html.
"""

import json
import os
import webbrowser
from collections import deque

# ─── Constants ────────────────────────────────────────────────────────────────
TOTAL_ROUNDS    = 3
TICKS_PER_ROUND = 12
TOTAL_TICKS     = 36
DAYS_PER_TICK   = 15   # 36 ticks × 15 days ≈ 18 months
ALPHA_UP        = 0.08
ALPHA_DOWN      = 0.05
OUTPUT_FILE     = "gordian_knot_sim.html"

# ─── Node Definitions ─────────────────────────────────────────────────────────
# cls:      Level | Accumulator | Drifter | Lever
# want:     "high" | "low" | None
# init_dev: deviation from 50  →  init_value = 50 + init_dev
# domain:   security | supply | infra | economic | political | diplomatic | adversarial | levers
# x, y:     SVG position in a 1000×600 viewBox

NODES = [
    # ── Security ──
    {"id": "compromise_rate",      "label": "Compromise Rate",          "cls": "Level",       "want": "low",  "init_dev":  15, "domain": "security",    "x": 110, "y":  75},
    {"id": "military_readiness",   "label": "Military Readiness",       "cls": "Level",       "want": "high", "init_dev":   0, "domain": "security",    "x": 195, "y":  75},
    {"id": "counterintel_posture", "label": "Counterintel Posture",     "cls": "Level",       "want": "high", "init_dev":   0, "domain": "security",    "x": 110, "y": 160},
    {"id": "cyber_posture",        "label": "Cyber Monitoring",         "cls": "Level",       "want": "high", "init_dev":   0, "domain": "security",    "x": 195, "y": 160},
    {"id": "intel_source_security","label": "Intel Source Security",    "cls": "Level",       "want": "high", "init_dev":   0, "domain": "security",    "x": 152, "y": 230},
    # ── Supply Chain ──
    {"id": "battery_supply",       "label": "Battery Safe Supply",      "cls": "Level",       "want": "high", "init_dev": -15, "domain": "supply",      "x": 308, "y":  75},
    {"id": "semi_supply",          "label": "Semi Safe Supply",         "cls": "Level",       "want": "high", "init_dev": -15, "domain": "supply",      "x": 383, "y":  75},
    {"id": "power_supply",         "label": "Power Elec Supply",        "cls": "Level",       "want": "high", "init_dev": -15, "domain": "supply",      "x": 458, "y":  75},
    {"id": "optics_supply",        "label": "Optics Supply",            "cls": "Level",       "want": "high", "init_dev": -15, "domain": "supply",      "x": 533, "y":  75},
    {"id": "mineral_access",       "label": "Critical Minerals",        "cls": "Level",       "want": "high", "init_dev": -10, "domain": "supply",      "x": 308, "y": 175},
    {"id": "inspection_capacity",  "label": "Inspection Capacity",      "cls": "Level",       "want": "high", "init_dev": -10, "domain": "supply",      "x": 383, "y": 175},
    {"id": "allied_reallocation",  "label": "Allied Mfg Realloc.",     "cls": "Accumulator", "want": "high", "init_dev": -20, "domain": "supply",      "x": 458, "y": 175},
    {"id": "domestic_buildout",    "label": "Domestic Mfg Buildout",   "cls": "Accumulator", "want": "high", "init_dev": -30, "domain": "supply",      "x": 533, "y": 175},
    # ── Infrastructure ──
    {"id": "grid_stability",       "label": "Grid Stability",           "cls": "Level",       "want": "high", "init_dev":  20, "domain": "infra",       "x": 645, "y":  75},
    {"id": "telecom_integrity",    "label": "Telecom Integrity",        "cls": "Level",       "want": "high", "init_dev":  20, "domain": "infra",       "x": 720, "y":  75},
    {"id": "data_center",          "label": "Data Center",              "cls": "Level",       "want": "high", "init_dev":  20, "domain": "infra",       "x": 795, "y":  75},
    {"id": "ev_transport",         "label": "EV & Transport",           "cls": "Level",       "want": "high", "init_dev":  15, "domain": "infra",       "x": 645, "y": 160},
    {"id": "port_logistics",       "label": "Port & Logistics",         "cls": "Level",       "want": "high", "init_dev":  10, "domain": "infra",       "x": 720, "y": 160},
    {"id": "defense_industrial",   "label": "Defense Industrial Base",  "cls": "Level",       "want": "high", "init_dev":   5, "domain": "infra",       "x": 795, "y": 160},
    # ── Economic ──
    {"id": "market_confidence",    "label": "Market Confidence",        "cls": "Level",       "want": "high", "init_dev":  15, "domain": "economic",    "x": 900, "y":  75},
    {"id": "consumer_price",       "label": "Consumer Price Pressure",  "cls": "Level",       "want": "low",  "init_dev": -10, "domain": "economic",    "x": 900, "y": 165},
    {"id": "consumer_tech",        "label": "Consumer Tech Avail.",     "cls": "Level",       "want": "high", "init_dev":  10, "domain": "economic",    "x": 900, "y": 250},
    # ── Political ──
    {"id": "congressional_support","label": "Congressional Support",    "cls": "Level",       "want": "high", "init_dev":   5, "domain": "political",   "x":  95, "y": 370},
    {"id": "public_trust",         "label": "Public Trust in Govt",     "cls": "Level",       "want": "high", "init_dev":  10, "domain": "political",   "x": 195, "y": 370},
    {"id": "interagency_alignment","label": "Interagency Alignment",    "cls": "Level",       "want": "high", "init_dev":   0, "domain": "political",   "x":  95, "y": 455},
    {"id": "public_awareness",     "label": "Public Awareness (Crisis)","cls": "Level",       "want": "low",  "init_dev": -35, "domain": "political",   "x": 195, "y": 455},
    # ── Diplomatic ──
    {"id": "allied_trust",         "label": "Allied Trust",             "cls": "Level",       "want": "high", "init_dev":  15, "domain": "diplomatic",  "x": 370, "y": 445},
    {"id": "china_stability",      "label": "US-China Stab.",           "cls": "Level",       "want": "high", "init_dev": -10, "domain": "diplomatic",  "x": 480, "y": 445},
    # ── Adversarial / Drifters ──
    {"id": "trade_friction",       "label": "Trade Friction",           "cls": "Drifter",     "want": "low",  "init_dev": -20, "domain": "adversarial", "x": 620, "y": 445},
    {"id": "prc_escalation",       "label": "PRC Escalation",           "cls": "Drifter",     "want": "low",  "init_dev": -20, "domain": "adversarial", "x": 730, "y": 445},
    {"id": "disclosure_clock",     "label": "Disclosure Clock",         "cls": "Drifter",     "want": "low",  "init_dev": -35, "domain": "adversarial", "x": 840, "y": 445},
    # ── Lever ──
    {"id": "tariff_level",         "label": "Tariff / Export Control",  "cls": "Lever",       "want": None,   "init_dev":   0, "domain": "levers",      "x": 730, "y": 530},
]

# ─── Drifter Schedules ────────────────────────────────────────────────────────
DRIFTER_SCHEDULES = {
    "prc_escalation":  [min(100.0, 30 + i * 1.2) for i in range(TOTAL_TICKS + 1)],
    "trade_friction":  [min(100.0, 30 + i * 0.8) for i in range(TOTAL_TICKS + 1)],
    "disclosure_clock":[min(100.0, 15 + i * 2.0) for i in range(TOTAL_TICKS + 1)],
}

# ─── Edge Definitions ─────────────────────────────────────────────────────────
EDGES_RAW = [
    # Security cascade
    ("prc_escalation",      "compromise_rate",        0.7,  30),
    ("cyber_posture",       "compromise_rate",       -0.6,  60),
    ("counterintel_posture","intel_source_security",  0.5,  90),
    ("inspection_capacity", "compromise_rate",       -0.5,  90),
    ("disclosure_clock",    "public_awareness",       0.8,  30),
    # Supply chain
    ("compromise_rate",     "battery_supply",        -0.7,  60),
    ("compromise_rate",     "semi_supply",           -0.7,  60),
    ("compromise_rate",     "power_supply",          -0.6,  60),
    ("compromise_rate",     "optics_supply",         -0.6,  60),
    ("allied_reallocation", "battery_supply",         0.5, 180),
    ("allied_reallocation", "semi_supply",            0.5, 180),
    ("allied_reallocation", "power_supply",           0.4, 180),
    ("allied_reallocation", "optics_supply",          0.4, 180),
    ("domestic_buildout",   "battery_supply",         0.6, 720),
    ("domestic_buildout",   "semi_supply",            0.6, 720),
    ("domestic_buildout",   "power_supply",           0.5, 720),
    ("domestic_buildout",   "optics_supply",          0.5, 720),
    ("mineral_access",      "battery_supply",         0.5, 180),
    # Infrastructure
    ("battery_supply",      "ev_transport",           0.4, 360),
    ("semi_supply",         "data_center",            0.5, 360),
    ("power_supply",        "grid_stability",         0.5, 360),
    ("optics_supply",       "telecom_integrity",      0.5, 360),
    ("compromise_rate",     "grid_stability",        -0.4, 120),
    ("compromise_rate",     "telecom_integrity",     -0.4, 120),
    ("compromise_rate",     "data_center",           -0.5, 120),
    ("semi_supply",         "defense_industrial",     0.4, 360),
    ("battery_supply",      "port_logistics",         0.3, 360),
    # Economic
    ("grid_stability",      "market_confidence",      0.4, 120),
    ("data_center",         "market_confidence",      0.4, 120),
    ("consumer_price",      "market_confidence",     -0.5,  60),
    ("trade_friction",      "market_confidence",     -0.4,  90),
    ("public_awareness",    "consumer_price",         0.5,  60),
    ("battery_supply",      "consumer_tech",          0.4, 180),
    ("semi_supply",         "consumer_tech",          0.4, 180),
    # Political
    ("public_awareness",    "congressional_support",  0.4,  90),
    ("market_confidence",   "congressional_support",  0.4, 180),
    ("public_trust",        "congressional_support",  0.5, 120),
    ("congressional_support","interagency_alignment", 0.5,  90),
    ("interagency_alignment","inspection_capacity",   0.4,  60),
    ("congressional_support","domestic_buildout",     0.6, 120),
    ("compromise_rate",     "public_trust",          -0.4, 180),
    # Diplomatic
    ("trade_friction",      "allied_trust",          -0.4, 180),
    ("allied_trust",        "allied_reallocation",    0.6,  90),
    ("china_stability",     "trade_friction",        -0.5,  90),
    ("tariff_level",        "trade_friction",         0.7,  30),
]

def _process_edges():
    out = []
    for src, tgt, w, delay_days in EDGES_RAW:
        out.append({"src": src, "tgt": tgt, "w": w, "delay": max(1, round(delay_days / DAYS_PER_TICK))})
    return out

EDGES = _process_edges()

# ─── Round Decisions ──────────────────────────────────────────────────────────
ROUND_DECISIONS = {
    1: [
        {"team": "Team A", "action": "Fund Inspection Capacity",      "effect": {"inspection_capacity":  10}},
        {"team": "Team B", "action": "Diplomatic Outreach to Allies", "effect": {"allied_trust":          8}},
        {"team": "Team C", "action": "Cyber Task Force",              "effect": {"cyber_posture":         12}},
        {"team": "Team D", "action": "Emergency Reshoring Fund",      "effect": {"domestic_buildout":     8}},
    ],
    2: [
        {"team": "Team A", "action": "Congressional Briefing",        "effect": {"congressional_support": 10}},
        {"team": "Team B", "action": "Allied Mfg Agreement",          "effect": {"allied_reallocation":   15}},
        {"team": "Team C", "action": "Counterintel Surge",            "effect": {"counterintel_posture":  12}},
        {"team": "Team D", "action": "Controlled Disclosure",         "effect": {"public_awareness": 20, "public_trust": 5}},
    ],
    3: [
        {"team": "Team A", "action": "Emergency Supply Legislation",  "effect": {"domestic_buildout":     12}},
        {"team": "Team B", "action": "Critical Minerals Deal",        "effect": {"mineral_access":        15}},
        {"team": "Team C", "action": "Activate DIB Protocols",        "effect": {"defense_industrial":    10}},
        {"team": "Team D", "action": "Trade Freeze Talks",            "effect": {"china_stability":       10}},
    ],
}

# ─── Injectable Events ────────────────────────────────────────────────────────
INJECTABLE_EVENTS = [
    {
        "id":          "allied_constraint",
        "name":        "Allied Capacity Constraint",
        "desc":        "Key allied manufacturing partners signal they cannot increase output due to their own supply shortfalls.",
        "inject_tick": 6,
        "effect":      {"allied_trust": -20},
    },
    {
        "id":          "source_dark",
        "name":        "Source Goes Dark",
        "desc":        "A primary intelligence source within the PRC supply chain has gone silent. IC assesses probable compromise.",
        "inject_tick": 10,
        "effect":      {"intel_source_security": -25},
    },
    {
        "id":          "public_leak",
        "name":        "Public Leak",
        "desc":        "A defense publication has obtained and published a classified summary of the hardware compromise assessment.",
        "inject_tick": 15,
        "effect":      {"public_awareness": 30},
    },
]

# ─── Round Narratives ─────────────────────────────────────────────────────────
ROUND_NARRATIVES = {
    1: {
        "title": "ROUND 1 — INITIAL ASSESSMENT",
        "text":  ("A confidential source reports China has inserted modified components into critical hardware "
                  "supply chains. Penetration is estimated at 8-12% across battery and semiconductor shipments. "
                  "Your team has 6 months before the next scheduled audit. "
                  "Initial intelligence suggests the compromise began 18-24 months ago. "
                  "Teams must prioritize: where do you focus first?"),
    },
    2: {
        "title": "ROUND 2 — POLITICAL CONSEQUENCES",
        "text":  ("Your sector prioritization decisions are now under Congressional scrutiny. "
                  "Three committee chairs are requesting classified briefings. "
                  "Allied partners are asking pointed questions about supply chain verification protocols. "
                  "Market analysts have begun noting unusual supply anomalies. "
                  "The window for quiet remediation is narrowing."),
    },
    3: {
        "title": "ROUND 3 — FLASH TRAFFIC",
        "text":  ("FLASH TRAFFIC: Penetration rate now confirmed at 20-25%. Timeline has accelerated. "
                  "An anonymous source has leaked preliminary findings to a defense publication. "
                  "Public disclosure is imminent. "
                  "The PRC has signaled awareness that the compromise has been detected. "
                  "Escalation risk is elevated. Teams must choose: contain, disclose, or escalate?"),
    },
}

# ─── Simulation Engine ────────────────────────────────────────────────────────

def init_state():
    return {n["id"]: float(50 + n["init_dev"]) for n in NODES}


def run_simulation(state_in, extra_shocks=None):
    """
    Simulate TOTAL_TICKS ticks from state_in.
    extra_shocks: {tick_number: {node_id: delta}, ...}
    Returns list of state dicts, index 0 = initial state (before any ticks).
    """
    if extra_shocks is None:
        extra_shocks = {}

    # One ring-buffer per edge to implement transport delay
    buffers = {i: deque([0.0] * e["delay"], maxlen=e["delay"]) for i, e in enumerate(EDGES)}

    state = {k: v for k, v in state_in.items()}
    snapshots = [dict(state)]

    for tick in range(1, TOTAL_TICKS + 1):
        # Apply round decisions at the first tick of each round
        rnd = ((tick - 1) // TICKS_PER_ROUND) + 1
        if (tick - 1) % TICKS_PER_ROUND == 0:
            for dec in ROUND_DECISIONS.get(rnd, []):
                for nid, delta in dec["effect"].items():
                    state[nid] = min(100.0, max(0.0, state[nid] + delta))

        # Apply event shocks
        if tick in extra_shocks:
            for nid, delta in extra_shocks[tick].items():
                state[nid] = min(100.0, max(0.0, state[nid] + delta))

        # Update Drifters from schedule
        for nid, sched in DRIFTER_SCHEDULES.items():
            state[nid] = sched[min(tick, len(sched) - 1)]

        # Push source values into buffers; read delayed values → pressure on targets
        incoming = {n["id"]: 0.0 for n in NODES}
        for i, e in enumerate(EDGES):
            src_val    = state[e["src"]]
            buf        = buffers[i]
            delayed    = buf[0]           # oldest (delay-ticks-ago) value exits
            buf.append(src_val)           # current value enters

            # Normalize: 50 = neutral; pressure is proportional to deviation
            pressure = e["w"] * (delayed - 50.0) / 50.0
            incoming[e["tgt"]] += pressure

        # Update Levels and Accumulators
        new_state = dict(state)
        for n in NODES:
            nid = n["id"]
            cls = n["cls"]
            if cls in ("Drifter", "Lever"):
                continue

            current  = state[nid]
            pressure = incoming[nid]

            if cls == "Level":
                target = min(100.0, max(0.0, current + pressure * 20.0))
                alpha  = ALPHA_UP if target > current else ALPHA_DOWN
                new_state[nid] = current + alpha * (target - current)

            elif cls == "Accumulator":
                DECAY = 0.02
                new_state[nid] = min(100.0, max(0.0, current * (1 - DECAY) + pressure * 5.0))

        state = new_state
        snapshots.append(dict(state))

    return snapshots


def compute_timelines():
    s0 = init_state()
    base = run_simulation(s0)

    event_branches = {}
    for evt in INJECTABLE_EVENTS:
        shock = {evt["inject_tick"]: {k: v for k, v in evt["effect"].items()}}
        event_branches[evt["id"]] = run_simulation(s0, shock)

    return base, event_branches

# ─── HTML Generation ─────────────────────────────────────────────────────────

def node_color(value, want):
    if want == "low":
        # For "want low" nodes: high value = bad (red), low value = good (green)
        if value <= 35:
            return "#4caf50"
        elif value <= 65:
            return "#ffeb3b"
        else:
            return "#f44336"
    else:
        # For "want high" nodes
        if value >= 65:
            return "#4caf50"
        elif value >= 35:
            return "#ffeb3b"
        else:
            return "#f44336"


def generate_html(base_ticks, event_branches):
    # Build node id → node map
    node_map = {n["id"]: n for n in NODES}

    # Serialize data
    data = {
        "nodes":    NODES,
        "edges":    EDGES,
        "base":     base_ticks,
        "events":   event_branches,
        "drifters": DRIFTER_SCHEDULES,
        "roundDecisions": {str(k): v for k, v in ROUND_DECISIONS.items()},
        "injectableEvents": INJECTABLE_EVENTS,
        "roundNarratives": {str(k): v for k, v in ROUND_NARRATIVES.items()},
        "constants": {
            "TOTAL_ROUNDS":    TOTAL_ROUNDS,
            "TICKS_PER_ROUND": TICKS_PER_ROUND,
            "TOTAL_TICKS":     TOTAL_TICKS,
            "DAYS_PER_TICK":   DAYS_PER_TICK,
        },
    }
    data_json = json.dumps(data, separators=(',', ':'))

    # Pre-render initial tick colors for SVG static fallback
    init_state_snap = base_ticks[0]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gordian Knot — World Simulation</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ height: 100%; background: #fff; color: #000; font-family: ui-monospace, monospace; font-size: 12px; }}
body {{ display: flex; flex-direction: column; height: 100vh; }}

#main {{ display: flex; flex: 1; overflow: hidden; border-bottom: 1px solid #000; }}

#graph-panel {{
  flex: 0 0 65%;
  border-right: 1px solid #000;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}}
#graph-title {{
  padding: 4px 8px;
  border-bottom: 1px solid #000;
  font-size: 11px;
  letter-spacing: 0.05em;
}}
#svg-wrap {{ flex: 1; overflow: hidden; }}
svg#world {{ width: 100%; height: 100%; }}

#side-panel {{
  flex: 0 0 35%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}}
.side-section {{
  border-bottom: 1px solid #000;
  padding: 6px 8px;
  overflow-y: auto;
}}
.side-section:last-child {{ border-bottom: none; flex: 1; }}
.side-label {{
  font-size: 9px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 4px;
  color: #555;
}}
#briefing-title {{ font-size: 11px; font-weight: bold; margin-bottom: 4px; }}
#briefing-text  {{ font-size: 11px; line-height: 1.5; }}
#events-list    {{ font-size: 11px; }}
.event-card {{
  border: 1px solid #000;
  padding: 4px 6px;
  margin-bottom: 4px;
}}
.event-card-name {{ font-weight: bold; font-size: 10px; }}
.event-card-desc {{ font-size: 10px; margin-top: 2px; color: #333; }}
#decisions-list {{ font-size: 11px; }}
.decision-row {{ margin-bottom: 2px; }}
.decision-team {{ font-weight: bold; }}

#resources-section {{ flex: none; }}
.resource-row {{ margin-bottom: 6px; }}
.resource-label {{ font-size: 10px; margin-bottom: 2px; }}
.bar-track {{ height: 8px; background: #e0e0e0; border: 1px solid #000; }}
.bar-fill  {{ height: 100%; background: #000; }}

#controls {{
  flex: none;
  display: flex;
  align-items: center;
  padding: 6px 10px;
  gap: 8px;
  border-top: 1px solid #000;
  font-size: 12px;
}}
#controls button {{
  font-family: ui-monospace, monospace;
  font-size: 11px;
  background: #fff;
  border: 1px solid #000;
  padding: 3px 8px;
  cursor: pointer;
}}
#controls button:hover {{ background: #000; color: #fff; }}
#tick-display {{ flex: 1; text-align: center; font-size: 11px; }}
#inject-select {{
  font-family: ui-monospace, monospace;
  font-size: 11px;
  border: 1px solid #000;
  background: #fff;
  padding: 3px 6px;
  cursor: pointer;
}}

/* SVG node tooltip */
.node-tooltip {{
  position: fixed;
  background: #fff;
  border: 1px solid #000;
  padding: 4px 6px;
  font-size: 10px;
  pointer-events: none;
  z-index: 100;
  display: none;
}}

/* domain cluster labels */
.cluster-label {{ font-size: 9px; fill: #aaa; font-family: ui-monospace, monospace; }}
</style>
</head>
<body>

<div id="main">
  <!-- ── Left: world graph ── -->
  <div id="graph-panel">
    <div id="graph-title">GORDIAN KNOT — WORLD STATE</div>
    <div id="svg-wrap">
      <svg id="world" viewBox="0 0 1000 580" preserveAspectRatio="xMidYMid meet">
        <defs>
          <marker id="arrow-pos" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="#000" />
          </marker>
          <marker id="arrow-neg" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="#d32f2f" />
          </marker>
        </defs>
        <!-- cluster background labels -->
        <text class="cluster-label" x="80"  y="45">SECURITY</text>
        <text class="cluster-label" x="290" y="45">SUPPLY CHAIN</text>
        <text class="cluster-label" x="630" y="45">INFRASTRUCTURE</text>
        <text class="cluster-label" x="870" y="45">ECONOMIC</text>
        <text class="cluster-label" x="55"  y="345">POLITICAL</text>
        <text class="cluster-label" x="340" y="415">DIPLOMATIC</text>
        <text class="cluster-label" x="600" y="415">ADVERSARIAL</text>

        <!-- edges rendered by JS -->
        <g id="edges-layer"></g>
        <!-- nodes rendered by JS -->
        <g id="nodes-layer"></g>
      </svg>
    </div>
  </div>

  <!-- ── Right: sidecar ── -->
  <div id="side-panel">
    <div class="side-section" style="flex:none;">
      <div class="side-label">Intel Briefing</div>
      <div id="briefing-title"></div>
      <div id="briefing-text"></div>
    </div>
    <div class="side-section" style="flex:none; min-height:60px;">
      <div class="side-label">Active Events</div>
      <div id="events-list">(none)</div>
    </div>
    <div class="side-section" style="flex:none; min-height:80px;">
      <div class="side-label">Decisions This Round</div>
      <div id="decisions-list"></div>
    </div>
    <div class="side-section" id="resources-section">
      <div class="side-label">Resources</div>
      <div class="resource-row">
        <div class="resource-label">BUDGET</div>
        <div class="bar-track"><div class="bar-fill" id="res-budget" style="width:70%"></div></div>
      </div>
      <div class="resource-row">
        <div class="resource-label">POLITICAL CAPITAL</div>
        <div class="bar-track"><div class="bar-fill" id="res-polcap" style="width:55%"></div></div>
      </div>
      <div class="resource-row">
        <div class="resource-label">ALLIED CAPACITY</div>
        <div class="bar-track"><div class="bar-fill" id="res-allied" style="width:40%"></div></div>
      </div>
    </div>
  </div>
</div>

<!-- ── Controls ── -->
<div id="controls">
  <button id="btn-prev">&#8592; Prev Round</button>
  <div id="tick-display">Round 1 / Tick 0 / Day 0</div>
  <button id="btn-next">Next Round &#8594;</button>
  <button id="btn-play">&#9654; Play</button>
  <select id="inject-select">
    <option value="">Inject Event&#9660;</option>
  </select>
</div>

<div class="node-tooltip" id="tooltip"></div>

<script>
const DATA = {data_json};

// ─── State ───────────────────────────────────────────────────────────────────
let currentTick      = 0;
let playInterval     = null;
let activeEventId    = null;
let activeEventName  = null;
let activeEventTick  = null;

function currentTimeline() {{
  if (activeEventId && DATA.events[activeEventId]) return DATA.events[activeEventId];
  return DATA.base;
}}

function roundForTick(tick) {{
  return Math.min(DATA.constants.TOTAL_ROUNDS, Math.floor(tick / DATA.constants.TICKS_PER_ROUND) + 1);
}}

// ─── SVG Rendering ───────────────────────────────────────────────────────────
const SVG_NS = "http://www.w3.org/2000/svg";

function nodeColor(value, want) {{
  if (want === "low") {{
    if (value <= 35) return "#4caf50";
    if (value <= 65) return "#ffeb3b";
    return "#f44336";
  }} else {{
    if (value >= 65) return "#4caf50";
    if (value >= 35) return "#ffeb3b";
    return "#f44336";
  }}
}}

function buildEdges() {{
  const layer = document.getElementById("edges-layer");
  layer.innerHTML = "";
  const nodePos = {{}};
  DATA.nodes.forEach(n => nodePos[n.id] = {{x: n.x, y: n.y}});

  DATA.edges.forEach((e, i) => {{
    const s = nodePos[e.src];
    const t = nodePos[e.tgt];
    if (!s || !t) return;

    const dx = t.x - s.x, dy = t.y - s.y;
    const len = Math.sqrt(dx*dx + dy*dy) || 1;
    const r = 16;
    const ux = dx/len, uy = dy/len;

    const x1 = s.x + ux*r, y1 = s.y + uy*r;
    const x2 = t.x - ux*(r+6), y2 = t.y - uy*(r+6);

    const isNeg = e.w < 0;
    const line  = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", x1); line.setAttribute("y1", y1);
    line.setAttribute("x2", x2); line.setAttribute("y2", y2);
    line.setAttribute("stroke",         isNeg ? "#d32f2f" : "#000");
    line.setAttribute("stroke-width",   "0.8");
    line.setAttribute("stroke-opacity", "0.4");
    line.setAttribute("marker-end",     isNeg ? "url(#arrow-neg)" : "url(#arrow-pos)");
    layer.appendChild(line);
  }});
}}

function buildNodes() {{
  const layer = document.getElementById("nodes-layer");
  layer.innerHTML = "";

  DATA.nodes.forEach(n => {{
    const g = document.createElementNS(SVG_NS, "g");
    g.setAttribute("data-id", n.id);
    g.style.cursor = "default";

    const snap  = currentTimeline()[currentTick];
    const val   = snap ? (snap[n.id] !== undefined ? snap[n.id] : 50) : 50;
    const fill  = nodeColor(val, n.want);

    if (n.cls === "Drifter") {{
      // Diamond
      const sz = 13;
      const poly = document.createElementNS(SVG_NS, "polygon");
      poly.setAttribute("points", `${{n.x}},${{n.y-sz}} ${{n.x+sz}},${{n.y}} ${{n.x}},${{n.y+sz}} ${{n.x-sz}},${{n.y}}`);
      poly.setAttribute("fill", fill); poly.setAttribute("stroke", "#000"); poly.setAttribute("stroke-width", "1.5");
      g.appendChild(poly);
    }} else if (n.cls === "Accumulator") {{
      // Square
      const sz = 13;
      const rect = document.createElementNS(SVG_NS, "rect");
      rect.setAttribute("x", n.x-sz); rect.setAttribute("y", n.y-sz);
      rect.setAttribute("width", sz*2); rect.setAttribute("height", sz*2);
      rect.setAttribute("fill", fill); rect.setAttribute("stroke", "#000"); rect.setAttribute("stroke-width", "1.5");
      g.appendChild(rect);
    }} else {{
      // Circle (Level + Lever)
      const c = document.createElementNS(SVG_NS, "circle");
      c.setAttribute("cx", n.x); c.setAttribute("cy", n.y); c.setAttribute("r", "16");
      c.setAttribute("fill", fill); c.setAttribute("stroke", "#000"); c.setAttribute("stroke-width", "1.5");
      if (n.cls === "Lever") {{ c.setAttribute("stroke-dasharray", "3 2"); }}
      g.appendChild(c);
    }}

    // Value label inside node
    const vt = document.createElementNS(SVG_NS, "text");
    vt.setAttribute("x", n.x); vt.setAttribute("y", n.y + 3);
    vt.setAttribute("text-anchor", "middle"); vt.setAttribute("font-size", "8");
    vt.setAttribute("font-family", "ui-monospace, monospace"); vt.setAttribute("fill", "#000");
    vt.textContent = Math.round(val);
    g.appendChild(vt);

    // Name label below node
    const lt = document.createElementNS(SVG_NS, "text");
    lt.setAttribute("x", n.x); lt.setAttribute("y", n.y + 26);
    lt.setAttribute("text-anchor", "middle"); lt.setAttribute("font-size", "7.5");
    lt.setAttribute("font-family", "ui-monospace, monospace"); lt.setAttribute("fill", "#000");
    lt.textContent = n.label;
    g.appendChild(lt);

    // Tooltip — reads live value at currentTick, not the build-time val
    g.addEventListener("mouseenter", (ev) => {{
      const tt  = document.getElementById("tooltip");
      const snap = currentTimeline()[currentTick];
      const liveVal = snap && snap[n.id] !== undefined ? snap[n.id] : 50;
      tt.style.display = "block";
      tt.innerHTML = `<b>${{n.label}}</b><br>Value: ${{Math.round(liveVal)}}<br>Class: ${{n.cls}}<br>Want: ${{n.want || "N/A"}}`;
    }});
    g.addEventListener("mousemove", (ev) => {{
      const tt = document.getElementById("tooltip");
      tt.style.left = (ev.clientX + 12) + "px";
      tt.style.top  = (ev.clientY + 12) + "px";
    }});
    g.addEventListener("mouseleave", () => {{
      document.getElementById("tooltip").style.display = "none";
    }});

    layer.appendChild(g);
  }});
}}

function updateNodes() {{
  const snap = currentTimeline()[currentTick];
  if (!snap) return;
  document.querySelectorAll("#nodes-layer g[data-id]").forEach(g => {{
    const nid  = g.getAttribute("data-id");
    const node = DATA.nodes.find(n => n.id === nid);
    if (!node) return;
    const val  = snap[nid] !== undefined ? snap[nid] : 50;
    const fill = nodeColor(val, node.want);

    const shape = g.querySelector("circle, rect, polygon");
    if (shape) shape.setAttribute("fill", fill);
    const texts = g.querySelectorAll("text");
    if (texts[0]) texts[0].textContent = Math.round(val);
  }});
}}

// ─── Sidecar ─────────────────────────────────────────────────────────────────
function updateSidecar() {{
  const rnd = roundForTick(currentTick);
  const narr = DATA.roundNarratives[String(rnd)];
  if (narr) {{
    document.getElementById("briefing-title").textContent = narr.title;
    document.getElementById("briefing-text").textContent  = narr.text;
  }}

  // Active event
  const evList = document.getElementById("events-list");
  if (activeEventId) {{
    const evt = DATA.injectableEvents.find(e => e.id === activeEventId);
    if (evt) {{
      evList.innerHTML = `<div class="event-card">
        <div class="event-card-name">${{evt.name}}</div>
        <div class="event-card-desc">${{evt.desc}}</div>
      </div>`;
    }}
  }} else {{
    evList.textContent = "(none)";
  }}

  // Decisions
  const decList = document.getElementById("decisions-list");
  const decs = DATA.roundDecisions[String(rnd)] || [];
  if (decs.length) {{
    decList.innerHTML = decs.map(d =>
      `<div class="decision-row"><span class="decision-team">${{d.team}}:</span> ${{d.action}}</div>`
    ).join("");
  }} else {{
    decList.textContent = "(none)";
  }}

  // Resources — decorative; drain slightly each round
  const budget = Math.max(10, 70 - (rnd - 1) * 15);
  const polcap = Math.max(10, 55 - (rnd - 1) * 12);
  const allied = Math.max(10, 40 + (rnd - 1) * 5);
  document.getElementById("res-budget").style.width = budget + "%";
  document.getElementById("res-polcap").style.width = polcap + "%";
  document.getElementById("res-allied").style.width = allied + "%";
}}

function updateTickDisplay() {{
  const rnd  = roundForTick(currentTick);
  const tick = currentTick;
  const day  = currentTick * DATA.constants.DAYS_PER_TICK;
  document.getElementById("tick-display").textContent =
    `Round ${{rnd}} / Tick ${{tick}} / Day ${{day}}`;
}}

function render() {{
  updateNodes();
  updateSidecar();
  updateTickDisplay();
}}

// ─── Controls ────────────────────────────────────────────────────────────────
function prevRound() {{
  stopPlay();
  const rnd = roundForTick(currentTick);
  if (rnd <= 1) {{ currentTick = 0; }}
  else {{ currentTick = (rnd - 2) * DATA.constants.TICKS_PER_ROUND; }}
  render();
}}

function nextRound() {{
  stopPlay();
  const rnd = roundForTick(currentTick);
  if (rnd >= DATA.constants.TOTAL_ROUNDS) {{
    currentTick = DATA.constants.TOTAL_TICKS;
  }} else {{
    currentTick = rnd * DATA.constants.TICKS_PER_ROUND;
  }}
  render();
}}

function stopPlay() {{
  if (playInterval) {{ clearInterval(playInterval); playInterval = null; }}
  document.getElementById("btn-play").textContent = "▶ Play";
}}

function togglePlay() {{
  if (playInterval) {{
    stopPlay();
  }} else {{
    document.getElementById("btn-play").textContent = "⏸ Pause";
    playInterval = setInterval(() => {{
      if (currentTick >= DATA.constants.TOTAL_TICKS) {{
        stopPlay();
        return;
      }}
      currentTick++;
      render();
    }}, 600);
  }}
}}

// ─── Event Injection ─────────────────────────────────────────────────────────
function injectEvent(evtId) {{
  if (!evtId) return;
  const evt = DATA.injectableEvents.find(e => e.id === evtId);
  if (!evt) return;
  activeEventId   = evtId;
  activeEventName = evt.name;
  activeEventTick = evt.inject_tick;
  // Jump to injection tick
  currentTick = evt.inject_tick;
  render();
}}

// ─── Init ────────────────────────────────────────────────────────────────────
function init() {{
  buildEdges();
  buildNodes();
  updateSidecar();
  updateTickDisplay();

  // Populate event dropdown
  const sel = document.getElementById("inject-select");
  DATA.injectableEvents.forEach(e => {{
    const opt  = document.createElement("option");
    opt.value  = e.id;
    opt.textContent = e.name;
    sel.appendChild(opt);
  }});

  document.getElementById("btn-prev").addEventListener("click",  prevRound);
  document.getElementById("btn-next").addEventListener("click",  nextRound);
  document.getElementById("btn-play").addEventListener("click",  togglePlay);
  sel.addEventListener("change", () => {{ injectEvent(sel.value); sel.value = ""; }});
}}

document.addEventListener("DOMContentLoaded", init);
</script>
</body>
</html>"""

    return html


# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Running simulation...")
    base_ticks, event_branches = compute_timelines()
    print(f"  Base timeline: {len(base_ticks)} snapshots ({TOTAL_TICKS} ticks)")
    for eid, branch in event_branches.items():
        print(f"  Event branch '{eid}': {len(branch)} snapshots")

    print("Generating HTML...")
    html = generate_html(base_ticks, event_branches)

    out_path = os.path.join(os.path.dirname(__file__), OUTPUT_FILE)
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Written: {out_path}")

    try:
        webbrowser.open(f"file://{out_path}")
        print("Opened in browser.")
    except Exception:
        print("Could not auto-open browser. Open the file manually.")
