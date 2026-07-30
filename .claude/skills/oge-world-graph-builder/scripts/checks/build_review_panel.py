#!/usr/bin/env python3
"""
Phase 5b, panel builder. Turns a world graph into a blind edge-review workflow: bundles edges by the
target stock's sector, embeds the human SCENARIO + SIDECAR + the relevant STOCK definitions + the
bundle's EDGES into each prompt, and emits a self-contained Workflow script that fans an Opus reviewer
(prompts/edge_review.md) over the bundles. Clones the embed-and-fan-out pattern of
sim/build_critic_input.py + critic_workflow.js.

Works on the real graph (production review) OR a mutated graph (calibration). The reviewer is blind to
which edges are planted — bundles look identical.

Usage:
  python3 build_review_panel.py GRAPH.json --scenario SCEN.md --sidecar SIDE.md --stocks stocks.json \
      --out-dir OUTDIR [--tag calib] [--model opus] [--bundle-size 9]
Writes OUTDIR/review_panel_<tag>.js (the Workflow script) + OUTDIR/review_map_<tag>.json.
Then:  Workflow(scriptPath="OUTDIR/review_panel_<tag>.js")
Then:  the returned {bundles:[...]} is scored by score_calibration.py / consumed by build_dossier.py.
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT = os.path.join(HERE, "..", "..", "prompts", "edge_review.md")


def bundle_edges(graph, stock_by_id, bundle_size):
    """Group edges by the target stock's sector; split oversized sectors into chunks of bundle_size."""
    by_sector = {}
    for e in graph["edges"]:
        sec = (stock_by_id.get(e["target"], {}) or {}).get("sector", "Other")
        by_sector.setdefault(sec, []).append(e)
    bundles = []
    for sec, es in sorted(by_sector.items()):
        for i in range(0, len(es), bundle_size):
            bundles.append({"sector": sec, "edges": es[i:i + bundle_size]})
    return bundles


def stock_brief(s):
    return {"id": s["id"], "name": s.get("name"), "inverted": bool(s.get("inverted")),
            "measures": s.get("measures"), "increases_when": s.get("increases_when"),
            "decreases_when": s.get("decreases_when")}


JS_TEMPLATE = r"""export const meta = {
  name: 'oge-edge-realism-review',
  description: 'Blind, scenario-grounded per-edge realism review (Phase 5b) fanned over edge bundles.',
  phases: [{ title: 'Review', detail: 'one Opus analyst per edge bundle, grounded in the scenario doc' }],
}

const BUNDLES = __BUNDLES_JSON__;
const PROMPT = __PROMPT_JSON__;
const MODEL = (typeof args === 'object' && args && args.model) ? args.model : __MODEL_JSON__;

const PROV = { type:'object', required:['existence','sign','strength','lag'], additionalProperties:false, properties:{
  existence:{ type:'object', required:['grounding'], additionalProperties:false, properties:{ grounding:{type:'string', enum:['stated','implied','model-inferred','unsupported']}, quote:{type:['string','null']} } },
  sign:{ type:'object', required:['grounding'], additionalProperties:false, properties:{ grounding:{type:'string', enum:['stated','implied','model-inferred','unsupported']}, quote:{type:['string','null']} } },
  strength:{ type:'object', required:['grounding'], additionalProperties:false, properties:{ grounding:{type:'string', enum:['stated','implied','model-inferred','unsupported']}, quote:{type:['string','null']} } },
  lag:{ type:'object', required:['grounding'], additionalProperties:false, properties:{ grounding:{type:'string', enum:['stated','implied','model-inferred','unsupported']}, quote:{type:['string','null']} } } } };
const EDGE = { type:'object', required:['edge_id','verdict','provenance'], additionalProperties:false, properties:{
  edge_id:{type:'string'}, provenance:PROV,
  verdict:{type:'string', enum:['defensible','flag']},
  error_class:{type:['string','null'], enum:['flipped_sign','fabricated_mechanism','wrong_strength','wrong_lag','other',null]},
  proposed_fix:{ type:['object','null'], additionalProperties:false, properties:{ field:{type:'string', enum:['sign','strength','lag','mechanism']}, to:{type:'string'} } },
  confidence:{type:'string', enum:['low','medium','high']},
  reasoning:{type:'string'} } };
const SCHEMA = { type:'object', required:['edges'], additionalProperties:false, properties:{
  edges:{ type:'array', items:EDGE },
  missing_edges:{ type:'array', items:{ type:'object', required:['source','target'], additionalProperties:false, properties:{ source:{type:'string'}, target:{type:'string'}, quote:{type:['string','null']}, why:{type:'string'} } } } } };

phase('Review');
log(`edge realism review: ${BUNDLES.length} bundles on ${MODEL}`);
const results = await parallel(BUNDLES.map((b, i) => () => {
  const stocksTxt = b.stocks.map(s => `- ${s.id} "${s.name}"${s.inverted?' [inverted: higher=worse]':''}: ${s.measures}. up when: ${s.increases_when}. down when: ${s.decreases_when}`).join('\n');
  const edgesTxt = b.edges.map(e => `- ${e.id}: ${e.source} --(${e.sign}, ${e.strength}, lag ${e.lag})--> ${e.target}\n    mechanism: ${e.mechanism}`).join('\n');
  const prompt = `${PROMPT}\n\n===== SCENARIO =====\n${b.scenario}\n\n===== SIDECAR =====\n${b.sidecar}\n\n===== STOCKS (this bundle) =====\n${stocksTxt}\n\n===== EDGES to review (target sector: ${b.sector}) =====\n${edgesTxt}`;
  return agent(prompt, { label:`review:${b.bundle_id}`, phase:'Review', schema:SCHEMA, model:MODEL, effort:'high' })
    .then(r => ({ bundle_id: b.bundle_id, sector: b.sector, review: r }));
}));

return { n: BUNDLES.length, bundles: results.filter(Boolean) };
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("graph")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--sidecar", required=True)
    ap.add_argument("--stocks", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tag", default="review")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--bundle-size", type=int, default=9)
    args = ap.parse_args()

    graph = json.load(open(args.graph))
    scenario = open(args.scenario, encoding="utf-8", errors="replace").read()
    sidecar = open(args.sidecar, encoding="utf-8", errors="replace").read()
    stocks_doc = json.load(open(args.stocks))
    stocks = stocks_doc["stocks"] if isinstance(stocks_doc, dict) and "stocks" in stocks_doc else stocks_doc
    stock_by_id = {s["id"]: s for s in stocks}
    prompt = open(PROMPT, encoding="utf-8").read()

    raw_bundles = bundle_edges(graph, stock_by_id, args.bundle_size)
    bundles, review_map = [], {}
    for i, b in enumerate(raw_bundles):
        bid = f"B{i+1:02d}"
        node_ids = set()
        for e in b["edges"]:
            node_ids.add(e["source"])
            node_ids.add(e["target"])
        bundles.append({
            "bundle_id": bid, "sector": b["sector"], "scenario": scenario, "sidecar": sidecar,
            "stocks": [stock_brief(stock_by_id[n]) for n in sorted(node_ids) if n in stock_by_id],
            "edges": [{k: e.get(k) for k in ("id", "source", "target", "sign", "strength", "lag", "mechanism")}
                      for e in b["edges"]],
        })
        review_map[bid] = [e["id"] for e in b["edges"]]

    os.makedirs(args.out_dir, exist_ok=True)
    js = (JS_TEMPLATE
          .replace("__BUNDLES_JSON__", json.dumps(bundles))
          .replace("__PROMPT_JSON__", json.dumps(prompt))
          .replace("__MODEL_JSON__", json.dumps(args.model)))
    js_path = os.path.join(args.out_dir, f"review_panel_{args.tag}.js")
    open(js_path, "w").write(js)
    json.dump({"map": review_map, "n_bundles": len(bundles), "n_edges": len(graph["edges"])},
              open(os.path.join(args.out_dir, f"review_map_{args.tag}.json"), "w"), indent=2)
    print(f"wrote {js_path} ({len(js)} bytes) — {len(bundles)} bundles, {len(graph['edges'])} edges, model={args.model}")
    print(f"launch: Workflow(scriptPath='{js_path}')")


if __name__ == "__main__":
    main()
