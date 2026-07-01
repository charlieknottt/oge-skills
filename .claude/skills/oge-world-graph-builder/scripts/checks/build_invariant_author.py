#!/usr/bin/env python3
"""
Phase 3b — emit a workflow that authors plausibility invariants from the SCENARIO, BLIND to the graph's
edges. Gives the author only the scenario text + the node vocabulary (id/name/measures/inverted) so its
expectations are independent of the graph's causal claims (not a paraphrase of them). Runs two authors
with slightly different emphases for a little diversity; `validate_invariants.py` unions + validates.

Usage:
  python3 build_invariant_author.py --scenario SCEN.md --stocks stocks.json --out-dir OUTDIR [--model opus]
Writes OUTDIR/invariant_author_workflow.js. Then Workflow(scriptPath=...) → validate_invariants.py.
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT = os.path.join(HERE, "..", "..", "prompts", "invariant_author.md")

WF = r"""export const meta = { name:'oge-invariant-author', description:'Author plausibility invariants from the scenario, blind to the graph edges.', phases:[{title:'Author'}] }
const SCENARIO = __SCEN_JSON__;
const NODES = __NODES_JSON__;
const PROMPT = __PROMPT_JSON__;
const MODEL = (typeof args==='object'&&args&&args.model)?args.model:__MODEL_JSON__;
const INV = { type:'object', required:['id','kind','quote','rationale'], additionalProperties:false, properties:{
  id:{type:'string'}, kind:{type:'string', enum:['coupling','pointwise','correlation']},
  when:{type:['string','null']}, then:{type:['string','null']}, within_rounds:{type:['integer','null']},
  rule:{type:['string','null']}, a:{type:['string','null']}, b:{type:['string','null']}, expect:{type:['string','null']},
  max_violation_rate:{type:['number','null']}, quote:{type:'string'}, rationale:{type:'string'} } };
const SCHEMA = { type:'object', required:['invariants'], additionalProperties:false, properties:{ invariants:{ type:'array', items:INV } } };
const nodesTxt = NODES.map(n=>`- ${n.id} "${n.name}"${n.inverted?' [inverted: higher=worse]':''}: ${n.measures}`).join('\n');
const emphases = [
  'Emphasize decisive OUTCOME couplings: what, per the scenario, should break or hold the key results.',
  'Emphasize failure states that should (almost) never occur, and any co-movements the scenario explicitly asserts.'
];
phase('Author');
const res = await parallel(emphases.map((emph,i)=>()=>{
  const prompt = `${PROMPT}\n\nEMPHASIS FOR THIS PASS: ${emph}\n\n===== SCENARIO =====\n${SCENARIO}\n\n===== NODES (reference by exact id) =====\n${nodesTxt}`;
  return agent(prompt, { label:`author:${i+1}`, phase:'Author', schema:SCHEMA, model:MODEL, effort:'high' }).then(r=>({pass:i+1, invariants:(r&&r.invariants)||[]}));
}));
return { passes: res.filter(Boolean) };
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--stocks", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", default="opus")
    args = ap.parse_args()

    scenario = open(args.scenario, encoding="utf-8", errors="replace").read()
    sdoc = json.load(open(args.stocks))
    stocks = sdoc["stocks"] if isinstance(sdoc, dict) and "stocks" in sdoc else sdoc
    nodes = [{"id": s["id"], "name": s.get("name"), "measures": s.get("measures"),
              "inverted": bool(s.get("inverted"))} for s in stocks]
    prompt = open(PROMPT, encoding="utf-8").read()

    os.makedirs(args.out_dir, exist_ok=True)
    js = (WF.replace("__SCEN_JSON__", json.dumps(scenario))
            .replace("__NODES_JSON__", json.dumps(nodes))
            .replace("__PROMPT_JSON__", json.dumps(prompt))
            .replace("__MODEL_JSON__", json.dumps(args.model)))
    path = os.path.join(args.out_dir, "invariant_author_workflow.js")
    open(path, "w").write(js)
    print(f"wrote {path} — {len(nodes)} nodes, blind to edges, model={args.model}")
    print(f"launch: Workflow(scriptPath='{path}')")


if __name__ == "__main__":
    main()
