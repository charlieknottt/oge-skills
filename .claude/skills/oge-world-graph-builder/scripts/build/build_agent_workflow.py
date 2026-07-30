#!/usr/bin/env python3
"""
build_agent_workflow.py - emit a one-agent Workflow (.js) for a judgment step (deterministic).

A script cannot launch an AI job in this harness, so each judgment step is compiled into a
self-contained Workflow file that the driving agent launches; its return value is saved to the next
step's input file. This emitter handles the SINGLE-agent steps: frame, stock-merge, stock-synthesis,
node-build, sidecar, edge-synthesis. (Fan-out steps use build_panel.py.)

It bundles a prompt with one or more input files (JSON embedded as parsed JSON, text embedded raw)
and runs one agent over the combination. Pass --schema to force structured JSON output.

Usage:
    python3 build_agent_workflow.py --prompt prompts/scenario_frame.md \\
        --input scenario_text=outputs/scenario_text.txt \\
        --name oge-frame --label frame --out outputs/workflows/frame.js
    python3 build_agent_workflow.py --prompt prompts/stock_synthesis.md \\
        --input consolidated_stocks=outputs/consolidated_stocks.json \\
        --input stock_redteam=outputs/stock_redteam.json \\
        --schema schemas/... --name oge-stock-synthesis --label synthesize --out .../synth.js
"""
import argparse
import json
import os
import sys

WF = r"""export const meta = { name:__NAME_JSON__, description:__DESC_JSON__, phases:[{title:'Run'}] }
const PROMPT = __PROMPT_JSON__;
const INPUTS = __INPUTS_JSON__;
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
phase('Run');
const prompt = `${PROMPT}\n\n${renderInputs(INPUTS)}`;
const opts = { label:__LABEL_JSON__, phase:'Run', model:MODEL };
if (EFFORT) opts.effort = EFFORT;
if (SCHEMA) opts.schema = SCHEMA;
const res = await agent(prompt, opts);
return SCHEMA ? res : asJson(res);
"""


def load_input(spec):
    """spec is NAME=PATH. Returns {name, kind, value}."""
    if "=" not in spec:
        raise ValueError(f"--input must be NAME=PATH, got {spec!r}")
    name, path = spec.split("=", 1)
    if path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            return {"name": name, "kind": "json", "value": json.load(f)}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return {"name": name, "kind": "text", "value": f.read()}


def main():
    ap = argparse.ArgumentParser(description="Emit a one-agent Workflow for a judgment step.")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--input", action="append", default=[], help="NAME=PATH (repeatable)")
    ap.add_argument("--name", required=True, help="workflow meta name")
    ap.add_argument("--desc", default="OGE build step")
    ap.add_argument("--label", default="step")
    ap.add_argument("--model", default=None, help="model override (default: inherit)")
    ap.add_argument("--effort", default=None)
    ap.add_argument("--schema", default=None, help="path to a JSON schema to force structured output")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
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
            .replace("__MODEL_JSON__", json.dumps(args.model))
            .replace("__EFFORT_JSON__", json.dumps(args.effort))
            .replace("__LABEL_JSON__", json.dumps(args.label))
            .replace("__SCHEMA_JSON__", json.dumps(schema)))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"wrote {args.out}  ({len(inputs)} input(s), schema={'yes' if schema else 'no'})")
    print(f"launch: Workflow(scriptPath='{args.out}')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
