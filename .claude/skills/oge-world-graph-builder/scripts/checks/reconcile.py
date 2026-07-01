#!/usr/bin/env python3
"""
Reconcile Monte Carlo invariant failures with the graph — decide, per failure, whether the GRAPH is
wrong or the INVARIANT is naive, and (for trusted, grounded, cross-checked cases) auto-apply the fix.

A failed invariant is a hard signal that something among {the edges on the causal path, the invariant
itself} is inconsistent — it does NOT say which. So a failure opens a reconciliation TICKET, never an
automatic edit, until the adjudicator + deterministic checks agree.

Two modes:
  build  — for each non-pass check, compute the deterministic causal slice (edges on paths between the
           invariant's nodes) and emit reconcile_packets.json + reconcile_workflow.js (an adjudicator
           agent per ticket).
  apply  — read the adjudication output; deterministic tiebreak via mechanism_audit sign-fidelity;
           AUTO-APPLY a proposed edge fix ONLY IF all safety rails hold; else leave as a human ticket.
           Writes change_log.json, updates dispositions[] in the face_validity report, and (if any
           auto-fix) a corrected graph.

Auto-apply rails (ALL required; from the approved plan):
  1) the error class PASSED calibration (calibration.json coverage == trusted),
  2) the fix is grounded (a verify_quotes-verified scenario quote accompanies it),
  3) a deterministic cross-check agrees (mechanism_audit isolated-sign for a sign flip),
  4) re-running mc_face_validity after the fix introduces no NEW invariant failure.
Hard exclusions (always human): magnitude, lag, missing edges, and invariant-naive/underspecified/ambiguous.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_invariants(path):
    try:
        import yaml
        doc = yaml.safe_load(open(path)) or {}
        return doc.get("invariants", [])
    except ImportError:
        from mc_face_validity import _mini_yaml
        return _mini_yaml(open(path).read())[0]


def nodes_in(text, all_ids):
    """Extract node ids referenced in a rule expression (word-boundary match against known ids)."""
    return [nid for nid in all_ids if re.search(r"\b" + re.escape(nid) + r"\b", text or "")]


def invariant_nodes(inv, all_ids):
    if inv.get("kind") == "correlation":
        return [inv.get("a")], [inv.get("b")]
    if inv.get("kind") == "coupling":
        return nodes_in(inv.get("when", ""), all_ids), nodes_in(inv.get("then", ""), all_ids)
    # pointwise: single set
    ns = nodes_in(inv.get("rule", ""), all_ids)
    return ns, ns


def bfs_paths(adj, src, dst, max_depth=3):
    """All edges on any path src->dst up to max_depth (directed)."""
    edges_on = set()
    stack = [(src, [src], [])]
    while stack:
        node, path, eids = stack.pop()
        if len(path) > max_depth + 1:
            continue
        for (nxt, eid) in adj.get(node, []):
            if nxt in path:
                continue
            neids = eids + [eid]
            if nxt == dst:
                edges_on.update(neids)
            else:
                stack.append((nxt, path + [nxt], neids))
    return edges_on


def causal_slice(graph, A, B, max_depth=3):
    adj = {}
    for e in graph["edges"]:
        adj.setdefault(e["source"], []).append((e["target"], e["id"]))
    eids = set()
    for a in A:
        for b in B:
            if not a or not b:
                continue
            eids |= bfs_paths(adj, a, b, max_depth)
            eids |= bfs_paths(adj, b, a, max_depth)
    return sorted(eids)


def build(args):
    graph = json.load(open(args.graph))
    all_ids = [n["id"] for n in graph["nodes"]]
    edge_by_id = {e["id"]: e for e in graph["edges"]}
    fv = json.load(open(args.face_validity))
    fv = fv.get("face_validity", fv)
    invs = {i["id"]: i for i in load_invariants(args.invariants)}

    packets = []
    for c in fv.get("checks", []):
        if c.get("status") == "pass":
            continue
        inv = invs.get(c["id"])
        if inv:
            A, B = invariant_nodes(inv, all_ids)
            slice_ids = causal_slice(graph, A, B)
        else:
            A = B = []
            slice_ids = []
        packets.append({
            "check_id": c["id"], "status": c["status"], "metric": c.get("metric"),
            "value": c.get("value"), "threshold": c.get("threshold"), "evidence": c.get("evidence"),
            "invariant": inv, "node_sets": [A, B],
            "slice": [{k: edge_by_id[eid].get(k) for k in ("id", "source", "target", "sign", "magnitude", "lag", "mechanism")}
                      for eid in slice_ids if eid in edge_by_id],
            "no_path": len(slice_ids) == 0,
        })

    os.makedirs(args.out_dir, exist_ok=True)
    json.dump({"packets": packets}, open(os.path.join(args.out_dir, "reconcile_packets.json"), "w"), indent=2)
    _emit_workflow(packets, os.path.join(args.out_dir, "reconcile_workflow.js"), args.model,
                   open(os.path.join(os.path.dirname(__file__), "..", "prompts", "reconcile_invariant.md")).read())
    print(f"built {len(packets)} reconciliation packet(s) -> {args.out_dir}")
    for p in packets:
        print(f"  {p['check_id']}: {p['status']}  slice={len(p['slice'])} edges"
              f"{'  (NO PATH — likely missing edge)' if p['no_path'] else ''}")


WF = r"""export const meta = { name:'oge-reconcile', description:'Adjudicate MC invariant failures: graph bug vs naive invariant.', phases:[{title:'Reconcile'}] }
const PACKETS = __PACKETS_JSON__;
const PROMPT = __PROMPT_JSON__;
const MODEL = (typeof args==='object'&&args&&args.model)?args.model:__MODEL_JSON__;
const SCHEMA = { type:'object', required:['check_id','disposition','reasoning'], additionalProperties:false, properties:{
  check_id:{type:'string'},
  disposition:{type:'string', enum:['edge-defect','missing-edge','invariant-naive','invariant-underspecified','ambiguous']},
  edge_id:{type:['string','null']},
  proposed_fix:{ type:['object','null'], additionalProperties:false, properties:{ field:{type:'string', enum:['sign','magnitude','lag','mechanism']}, to:{type:'string'} } },
  grounding_quote:{type:['string','null']},
  proposed_invariant_amendment:{type:['string','null']},
  reasoning:{type:'string'} } };
phase('Reconcile');
const res = await parallel(PACKETS.map(p => () => {
  const sliceTxt = p.slice.map(e=>`- ${e.id}: ${e.source} --(${e.sign},${e.magnitude},lag ${e.lag})--> ${e.target} :: ${e.mechanism}`).join('\n') || '(no edges on any causal path between the invariant nodes — a missing edge is likely)';
  const prompt = `${PROMPT}\n\n===== FAILED CHECK =====\nid: ${p.check_id}\nstatus: ${p.status}\nmetric ${p.metric} = ${p.value} (threshold ${p.threshold})\nevidence: ${p.evidence}\ninvariant: ${JSON.stringify(p.invariant)}\n\n===== CANDIDATE EDGES ON THE CAUSAL PATH =====\n${sliceTxt}`;
  return agent(prompt, { label:`reconcile:${p.check_id}`, phase:'Reconcile', schema:SCHEMA, model:MODEL, effort:'high' }).then(r=>({check_id:p.check_id, adjudication:r}));
}));
return { n:PACKETS.length, tickets: res.filter(Boolean) };
"""


def _emit_workflow(packets, path, model, prompt):
    js = (WF.replace("__PACKETS_JSON__", json.dumps(packets))
            .replace("__PROMPT_JSON__", json.dumps(prompt))
            .replace("__MODEL_JSON__", json.dumps(model)))
    open(path, "w").write(js)


def _unwrap(doc, key="tickets"):
    if isinstance(doc, dict):
        if key in doc:
            return doc
        if isinstance(doc.get("result"), dict) and key in doc["result"]:
            return doc["result"]
    return None


def _isolated_sign_ok(graph_obj, edge, expected_sign):
    """Rail 3 for a sign fix: in the isolated 2-node subgraph, shocking the source must move the target
    in `expected_sign`'s direction (and reverse under the opposite shock). Pure physics, no LLM."""
    import mc_face_validity as M
    nb = {n["id"]: n for n in graph_obj["nodes"]}
    if edge["source"] not in nb or edge["target"] not in nb:
        return False
    mini = {"nodes": [dict(nb[edge["source"]]), dict(nb[edge["target"]])], "edges": [dict(edge)]}
    eng = M.Engine(mini, rail_zone=0.0, rail_power=1.0)
    t, b = edge["target"], None
    b = eng.base[t]
    up = eng.run({0: {edge["source"]: 25}}, 40)[-1][t] - b
    dn = eng.run({0: {edge["source"]: -25}}, 40)[-1][t] - b
    exp = 1 if expected_sign == "+" else -1
    return (abs(up) > 1e-6 and (1 if up > 0 else -1) == exp and
            abs(dn) > 1e-6 and (1 if dn > 0 else -1) == -exp)


def _mc_status(graph_obj, invariants_path, runs=600):
    """Run a reduced Monte Carlo in-process; return {check_id: status}. Used for rail 4."""
    import random
    import mc_face_validity as M
    eng = M.Engine(graph_obj, rail_zone=0.0, rail_power=1.0)
    invs, inv_cfg = M.load_invariants(invariants_path) if invariants_path else ([], {})
    cfg = {"rail_hit_max": 0.30, "skew_max": 0.70}
    cfg.update({k: inv_cfg[k] for k in ("rail_hit_max", "skew_max", "win_rule", "outcome_nodes") if k in inv_cfg})
    rng = random.Random(7)
    games = [M.sample_game(eng, 24, 6, 3, 4, rng) for _ in range(runs)]
    checks = M.scanners(eng, games, cfg) + M.eval_invariants(games, invs)
    return {c["id"]: c["status"] for c in checks}


def apply(args):
    from mc_face_validity import Engine  # noqa
    graph = json.load(open(args.graph))
    edge_by_id = {e["id"]: e for e in graph["edges"]}
    adj = _unwrap(json.load(open(args.adjudication)))
    if not adj:
        raise SystemExit("no 'tickets' in adjudication output")
    calib = json.load(open(args.calibration)) if args.calibration and os.path.exists(args.calibration) else {}
    coverage = calib.get("coverage_map", {})
    scen_norm = None
    if args.scenario:
        from verify_quotes import load_scenario, verify_quote
        scen_norm = load_scenario(args.scenario)

    # Baseline MC status (rail 4 compares against this so a fix can't create a NEW failure).
    base_status = _mc_status(graph, args.invariants) if args.invariants else {}
    change_log, dispositions = [], []
    for t in adj["tickets"]:
        a = t.get("adjudication") or {}
        cid = t.get("check_id")
        disp = a.get("disposition")
        rec = {"id": cid, "source": "reconcile", "disposition": disp, "reasoning": a.get("reasoning")}
        auto = False
        reason = ""
        if disp == "edge-defect" and a.get("edge_id") in edge_by_id and a.get("proposed_fix"):
            fix = a["proposed_fix"]
            field = fix.get("field")
            # AUTO-APPLY is confined to SIGN fixes: it is the only class that is BOTH calibration-trusted
            # AND has a deterministic verifier (isolated-sign fidelity). Mechanism rewrites are trusted by
            # calibration but have no deterministic check, so they go to the human; magnitude/lag are
            # calibration-uncovered and excluded outright.
            trusted = coverage.get("flipped_sign") == "trusted"
            grounded = bool(scen_norm and a.get("grounding_quote") and verify_quote(a["grounding_quote"], scen_norm))
            rails = {"rail1_class_trusted": bool(trusted and field == "sign"),
                     "rail2_grounded": grounded}
            if rails["rail1_class_trusted"] and rails["rail2_grounded"]:
                # tentatively apply, then run rails 3 & 4; revert if either fails.
                before = edge_by_id[a["edge_id"]].get(field)
                edge_by_id[a["edge_id"]][field] = fix["to"]
                rails["rail3_sign_fidelity"] = _isolated_sign_ok(graph, edge_by_id[a["edge_id"]], fix["to"])
                new_status = _mc_status(graph, args.invariants) if args.invariants else {}
                new_fail = [k for k, s in new_status.items()
                            if s == "fail" and base_status.get(k) == "pass"]
                rails["rail4_no_new_mc_failure"] = (len(new_fail) == 0)
                if rails["rail3_sign_fidelity"] and rails["rail4_no_new_mc_failure"]:
                    auto = True
                    reason = "AUTO-APPLIED: trusted sign class, grounded, sign-fidelity OK, no new MC failure"
                    change_log.append({"check_id": cid, "edge_id": a["edge_id"], "field": field,
                                       "from": before, "to": fix["to"], "rails": rails,
                                       "grounding_quote": a.get("grounding_quote")})
                else:
                    edge_by_id[a["edge_id"]][field] = before  # REVERT
                    reason = (f"NOT auto-applied (reverted): rail3_sign_fidelity="
                              f"{rails['rail3_sign_fidelity']} rail4_no_new_fail="
                              f"{rails['rail4_no_new_mc_failure']}{' new:'+str(new_fail) if new_fail else ''} — human")
            else:
                reason = (f"NOT auto-applied: rail1(sign&trusted)={rails['rail1_class_trusted']} "
                          f"rail2(grounded)={rails['rail2_grounded']} — human")
            rec["rails"] = rails
        elif disp == "invariant-naive":
            reason = "invariant is naive; fix the rule, not the graph — human ratifies"
        else:
            reason = f"{disp} — human decision"
        rec["auto_applied"] = auto
        rec["note"] = reason
        rec["decision"] = "fixed" if auto else None  # feeds gate_face_validity dispositions
        rec["proposed_fix"] = a.get("proposed_fix")
        rec["proposed_invariant_amendment"] = a.get("proposed_invariant_amendment")
        dispositions.append(rec)

    os.makedirs(args.out_dir, exist_ok=True)
    json.dump({"change_log": change_log}, open(os.path.join(args.out_dir, "change_log.json"), "w"), indent=2)
    json.dump({"dispositions": dispositions}, open(os.path.join(args.out_dir, "reconcile_dispositions.json"), "w"), indent=2)
    if change_log:
        json.dump(graph, open(os.path.join(args.out_dir, "graph_autofixed.json"), "w"), indent=1)
    print(f"reconcile apply: {len(change_log)} auto-fix(es) (rails 1-4 all passed), {len(dispositions)} disposition(s)")
    for d in dispositions:
        print(f"  {d['id']}: {d['disposition']} -> {'AUTO-FIXED' if d['auto_applied'] else 'human'}  ({d['note']})")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    b = sub.add_parser("build")
    b.add_argument("graph"); b.add_argument("--face-validity", required=True)
    b.add_argument("--invariants", required=True); b.add_argument("--out-dir", required=True)
    b.add_argument("--model", default="opus")
    ap2 = sub.add_parser("apply")
    ap2.add_argument("graph"); ap2.add_argument("--adjudication", required=True)
    ap2.add_argument("--calibration"); ap2.add_argument("--scenario"); ap2.add_argument("--invariants")
    ap2.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    (build if args.mode == "build" else apply)(args)


if __name__ == "__main__":
    main()
