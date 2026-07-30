#!/usr/bin/env python3
"""
build_panel.py - emit a fan-out Workflow (.js) that runs one agent per item (deterministic).

The fan-out judgment steps run N agents in parallel over a fixed set: pick-the-nodes (one per PMESII
dimension), review-the-nodes and review-the-edges (one per red-team lens), draw-the-edges (one per
focus node). This emitter compiles any of them: a shared prompt + shared inputs + one fan value per
agent. The Workflow's return value is { results: [ { fan, key, result } ] }, which the deterministic
merge/synthesis steps read.

Usage:
    python3 build_panel.py --prompt prompts/stock_proposal.md --fan-label dimension \\
        --fan Political,Military,Economic,Social,Information,Infrastructure,Physical \\
        --input scenario_frame=outputs/scenario_frame.json \\
        --input scenario_text=outputs/scenario_text.txt \\
        --name oge-propose-nodes --out outputs/workflows/propose_nodes.js
"""
import argparse
import json
import os
import sys

WF = r"""export const meta = { name:__NAME_JSON__, description:__DESC_JSON__, phases:[{title:'Panel'}] }
const PROMPT = __PROMPT_JSON__;
const INPUTS = __INPUTS_JSON__;
const FAN = __FAN_JSON__;
const FANLABEL = __FANLABEL_JSON__;
const MODEL = (typeof args==='object'&&args&&args.model)?args.model:__MODEL_JSON__;
const EFFORT = __EFFORT_JSON__;
const SCHEMA = __SCHEMA_JSON__;
function renderInputs(inp){
  return inp.map(v=>{
    const body = (v.kind==='text') ? v.value : JSON.stringify(v.value, null, 2);
    return `===== ${v.name} =====\n${body}`;
  }).join('\n\n');
}
function asJson(s){ if(typeof s!=='string') return s; let t=s.trim();
  const m=t.match(/```(?:json)?\s*([\s\S]*?)```/); if(m) t=m[1].trim();
  try{ return JSON.parse(t); }catch(e){ return s; } }
phase('Panel');
const shared = renderInputs(INPUTS);
const res = await parallel(FAN.map((f,i)=>()=>{
  const prompt = `${PROMPT}\n\nYOUR ${FANLABEL.toUpperCase()}: ${f}\n\n${shared}`;
  const opts = { label:`${FANLABEL}:${f}`, phase:'Panel', model:MODEL };
  if (EFFORT) opts.effort = EFFORT;
  if (SCHEMA) opts.schema = SCHEMA;
  return agent(prompt, opts).then(r=>({ [FANLABEL]:f, key:f, result: SCHEMA ? r : asJson(r) }));
}));
return { results: res.filter(Boolean) };
"""


def load_input(spec):
    if "=" not in spec:
        raise ValueError(f"--input must be NAME=PATH, got {spec!r}")
    name, path = spec.split("=", 1)
    if path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            return {"name": name, "kind": "json", "value": json.load(f)}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return {"name": name, "kind": "text", "value": f.read()}


def main():
    ap = argparse.ArgumentParser(description="Emit a fan-out Workflow (one agent per item).")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--fan", default=None, help="comma-separated fan values")
    ap.add_argument("--fan-file", default=None, help="JSON array of fan values (alternative to --fan)")
    ap.add_argument("--fan-label", default="item", help="what each fan value is (e.g. dimension, lens, node)")
    ap.add_argument("--input", action="append", default=[], help="NAME=PATH (repeatable)")
    ap.add_argument("--name", required=True)
    ap.add_argument("--desc", default="OGE fan-out step")
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default=None)
    ap.add_argument("--schema", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        if args.fan_file:
            fan = json.load(open(args.fan_file))
        elif args.fan:
            fan = [x.strip() for x in args.fan.split(",") if x.strip()]
        else:
            print("ERROR: pass --fan or --fan-file", file=sys.stderr)
            return 2
        prompt = open(args.prompt, encoding="utf-8").read()
        inputs = [load_input(s) for s in args.input]
        schema = json.load(open(args.schema)) if args.schema else None
    except (OSError, ValueError, json.JSONDecodeError) as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return 2

    js = (WF.replace("__NAME_JSON__", json.dumps(args.name))
            .replace("__DESC_JSON__", json.dumps(args.desc))
            .replace("__PROMPT_JSON__", json.dumps(prompt))
            .replace("__INPUTS_JSON__", json.dumps(inputs))
            .replace("__FAN_JSON__", json.dumps(fan))
            .replace("__FANLABEL_JSON__", json.dumps(args.fan_label))
            .replace("__MODEL_JSON__", json.dumps(args.model))
            .replace("__EFFORT_JSON__", json.dumps(args.effort))
            .replace("__SCHEMA_JSON__", json.dumps(schema)))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"wrote {args.out}  ({len(fan)} {args.fan_label}(s), {len(inputs)} input(s))")
    print(f"launch: Workflow(scriptPath='{args.out}')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
