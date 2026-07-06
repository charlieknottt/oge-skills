#!/usr/bin/env python3
"""
render_preview.py - turn a world_graph.json into a self-contained, playable index.html
that renders IDENTICALLY to the Gordian Knot demo UI (gordian_knot_sim.html).

The CSS and the JS engine/layout/zoom/inspector are reused verbatim from that demo, so the
output matches it exactly: white ruled background, hsl(120*g/100,58%,62%) red->green node
fill, monospace values, swimlane group boxes, curved edges (dashed = negative), wheel-zoom +
drag-pan + fit, hover-to-light, click-for-inspector, and play-with-pause-at-injects. Only the
DATA (nodes, edges, groups, synthetic decisions/injects, round/tick config) is generated from
the supplied world_graph.json.

This is the deterministic SHOWCASE engine (a math demo for vetting propagation), NOT the
runtime; at game time Claude is the physics. The graph carries a 0-1 edge magnitude and an
integer lag, so this uses magnitude directly as the edge weight and maps dynamics
{Level,Lever,Accumulator,Drifter} -> rate params, and uses the edge lag directly.

Usage:
    python3 render_preview.py world_graph.json
    python3 render_preview.py world_graph.json --out index.html --rounds 6 --ticks 6 --seed 0
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import RATES, SPEED, SAT_A, mag_weight  # single source of truth for the physics
# left-to-right swimlane order: inputs -> world -> outcomes (others appended in first-seen order)
GROUP_PREF = ["Levers", "Buildouts", "Compromise", "Supply", "Infrastructure", "Economy",
              "Outcomes", "Pool"]


def build_data_js(graph, rounds, ticks, seed):
    nodes = graph["nodes"]
    edges = graph["edges"]
    by_id = {n["id"]: n for n in nodes}

    raw = {}
    type_map = {}
    inv_map = {}
    for n in nodes:
        au, ad = RATES.get(n["type"], RATES["Level"])
        raw[n["id"]] = [n["label"], float(n["starting_value"]), au, ad,
                        (0 if n.get("inverted") else 1), n["category"]]
        type_map[n["id"]] = n["type"]
        inv_map[n["id"]] = bool(n.get("inverted"))

    edge_js = [[e["source"], e["target"],
                round(mag_weight(e.get("magnitude", 0.6)) * (1 if e.get("sign", "+") == "+" else -1), 3),
                int(e.get("lag", 1)), e.get("mechanism", "")]
               for e in edges if e["source"] in by_id and e["target"] in by_id]

    # group swimlanes by category, ordered by preference then first appearance
    cats = []
    for n in nodes:
        if n["category"] not in cats:
            cats.append(n["category"])
    seen_order = {c: i for i, c in enumerate(cats)}
    cats.sort(key=lambda c: (GROUP_PREF.index(c) if c in GROUP_PREF else len(GROUP_PREF), seen_order[c]))
    groups = [{"key": c, "name": c, "ids": [n["id"] for n in nodes if n["category"] == c]} for c in cats]

    # synthesize decisions (player invests in levers/buildouts) and injects (worsen threats)
    levers = [n["id"] for n in nodes if n["type"] == "Lever"]
    accums = [n["id"] for n in nodes if n["type"] == "Accumulator"]
    threats = [n["id"] for n in nodes if n.get("inverted")]
    levels = [n["id"] for n in nodes if n["type"] == "Level"]
    ptargets = (levers + accums) or levels or [n["id"] for n in nodes]
    inject_rounds = sorted({r for r in (2, 4) if r <= rounds})

    decisions, di = [], 0
    for r in range(1, rounds + 1):
        if r in inject_rounds:
            continue
        tgt = ptargets[(di + seed) % len(ptargets)]
        spend = {"budget": 30} if di % 2 == 0 else {"polcap": 20}
        decisions.append({"round": r, "target": tgt, "amt": 30, "spend": spend,
                          "label": "Invest in " + by_id[tgt]["label"]})
        di += 1

    events, ti = [], 0
    for r in inject_rounds:
        if threats:
            tgt = threats[(ti + seed) % len(threats)]
            events.append({"round": r, "target": tgt, "amt": 45,
                           "label": "Compromise / threat escalates: " + by_id[tgt]["label"]})
        elif levels:
            tgt = levels[(ti + seed) % len(levels)]
            events.append({"round": r, "target": tgt, "amt": -32,
                           "label": "Adverse shock: " + by_id[tgt]["label"]})
        ti += 1

    res = {"budget": {"start": 70, "regen": 18, "cap": 100},
           "polcap": {"start": 55, "regen": 12, "cap": 100}}

    j = json.dumps
    return (
        "const SPEED=" + repr(SPEED) + ", TPR=" + str(ticks) + ", ROUNDS=" + str(rounds) +
        ", TOTAL=ROUNDS*TPR, SAT_A=" + repr(SAT_A) + ", MINV=0, MAXV=100;\n"
        "const RAW=" + j(raw) + ";\n"
        "const IDS=Object.keys(RAW);\n"
        "const LABEL={},BASE={},AUP={},ADN={},WANT={};\n"
        "IDS.forEach(i=>{const r=RAW[i];LABEL[i]=r[0];BASE[i]=r[1];AUP[i]=r[2]*SPEED;ADN[i]=r[3]*SPEED;WANT[i]=!!r[4];});\n"
        "const TYPE=" + j(type_map) + ";\n"
        "const INV=" + j(inv_map) + ";\n"
        'const DESC={"Level":"goal-seeks its drivers","Lever":"held \\u2014 moves only on a decision or inject",'
        '"Accumulator":"builds slowly, breaks fast","Drifter":"slow-moving state"};\n'
        "const EDGES=" + j(edge_js) + ";\n"
        "const EVENTS=" + j(events) + ";\n"
        "const DECISIONS=" + j(decisions) + ";\n"
        "const RES=" + j(res) + ";\n"
        "const GROUPS=" + j(groups) + ";\n"
    )


def title_of(graph):
    s = graph.get("scenario") or "World Graph"
    return s.replace("_", " ").replace("-", " ").strip().title()


def scenario_slug(graph, graph_path):
    """A filesystem-safe scenario name for the output file: scenario field if present,
    else derived from the input filename (stripping a trailing _graph / _world_graph)."""
    base = graph.get("scenario")
    if not base:
        base = os.path.splitext(os.path.basename(graph_path))[0]
        for suffix in ("_world_graph", "_graph"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
    slug = "".join(c if (c.isalnum() or c in "_-") else "_" for c in base.lower().replace(" ", "_"))
    slug = slug.strip("_-") or "world_graph"
    return slug


# ---- PART 1: HTML head + body + <script> (verbatim from gordian_knot_sim.html; __TITLE__ swapped) ----
PART1 = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OGE World Graph &mdash; __TITLE__</title>
<style>
  :root{ --ink:#111; --line:#000; --soft:#999; --faint:#dcdcdc; --bg:#fff; }
  *{box-sizing:border-box;}
  html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);
    font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;font-size:15px;}
  .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;}
  header{padding:10px 16px;border-bottom:2px solid var(--line);}
  header h1{font-size:20px;margin:0;letter-spacing:.3px;}
  header p{margin:4px 0 0;color:#444;font-size:14px;}
  #main{display:flex;height:calc(100% - 66px);}
  #graphwrap{position:relative;flex:1;overflow:hidden;border-right:2px solid var(--line);}
  svg{width:100%;height:100%;display:block;background:
    repeating-linear-gradient(0deg,#fafafa 0 24px,#fff 24px 25px);cursor:grab;}
  svg.panning{cursor:grabbing;}
  #zoomctl{position:absolute;left:10px;bottom:10px;display:flex;gap:4px;}
  #zoomctl button{width:30px;height:30px;}
  button{font:inherit;background:#fff;color:var(--ink);border:1.5px solid var(--line);
    padding:5px 9px;cursor:pointer;border-radius:3px;}
  button:hover{background:var(--ink);color:#fff;}
  button:disabled{opacity:.35;cursor:default;background:#fff;color:var(--ink);}
  button.attn{background:#d00;color:#fff;border-color:#d00;}
  button.attn:hover{background:#a00;color:#fff;}
  aside{width:360px;min-width:360px;overflow-y:auto;padding:14px;}
  .card{border:1.5px solid var(--line);border-radius:4px;padding:10px;margin-bottom:12px;}
  .card h2{font-size:14px;margin:0 0 8px;text-transform:uppercase;letter-spacing:.6px;border-bottom:1px solid var(--faint);padding-bottom:5px;}
  .roundbar{display:flex;align-items:center;gap:6px;margin-bottom:8px;}
  .roundbar .lbl{flex:1;text-align:center;font-weight:700;font-size:12px;}
  input[type=range]{width:100%;accent-color:#111;}
  .res{margin:8px 0;}
  .res .top{display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;}
  .bar{height:12px;border:1.5px solid var(--line);background:#fff;border-radius:2px;overflow:hidden;}
  .bar > div{height:100%;background:repeating-linear-gradient(45deg,#444 0 5px,#777 5px 10px);}
  .evt{padding:7px 8px;border:1px solid var(--faint);border-left:4px solid #000;border-radius:3px;margin-bottom:6px;font-size:12px;}
  .evt.inject{border-left-style:dashed;}
  .evt.fire{border-color:#d00;border-left-color:#d00;background:#ffe9e9;animation:flashred 1s ease-in-out infinite;}
  .evt.fire .tag{color:#c00;}
  @keyframes flashred{0%,100%{background:#ffe9e9;}50%{background:#ffc6c6;}}
  .muted{color:#777;}
  .detail dl{margin:0;} .detail dt{font-weight:700;margin-top:6px;} .detail dd{margin:1px 0 0;}
  .drv{font-size:11.5px;padding:4px 0;border-bottom:1px dotted var(--faint);}
  .drv .w{font-weight:700;}
  .legend > div{display:flex;align-items:center;gap:7px;margin:7px 0;font-size:13px;}
  .legend .muted{display:block;}
  .grad{width:90px;height:12px;border:1px solid var(--line);
    background:linear-gradient(90deg,hsl(0,58%,62%),hsl(60,58%,62%),hsl(120,58%,62%));}
  .lineP,.lineN{width:26px;height:0;border-top:2px solid #000;}
  .lineN{border-top-style:dashed;}
  text{ -webkit-user-select:none; user-select:none; }
  .gbox{fill:#fbfbfb;stroke:var(--faint);stroke-width:1;}
  .glabel{fill:#555;font-size:17px;font-weight:800;letter-spacing:.5px;text-transform:uppercase;}
  .node rect{stroke:var(--line);stroke-width:1.5;cursor:pointer;transition:fill .4s ease;}
  .node.sel rect{stroke-width:3.5;}
  @keyframes nodepulse{0%,100%{filter:drop-shadow(0 0 2px var(--glow));}50%{filter:drop-shadow(0 0 20px var(--glow));}}
  .node.flash{animation:nodepulse .85s ease-in-out infinite;}
  .node.flash > rect{stroke-width:4;}
  .node .nlabel{font-size:15px;font-weight:700;pointer-events:none;}
  .node .nval{font-size:23px;font-weight:800;pointer-events:none;}
  .edge{stroke:#cfcfcf;stroke-width:1.6;fill:none;cursor:pointer;}
  .edge.neg{stroke-dasharray:6 4;}
  .edge.hi{stroke:#000;stroke-width:3.2;}
  .edge.dim{stroke:#eee;}
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <p>OGE World Graph &middot; <span class="mono">__SLUG__</span></p>
</header>
<div id="main">
  <div id="graphwrap">
    <svg id="svg"><g id="viewport"></g></svg>
    <div id="zoomctl">
      <button id="zin" title="Zoom in">+</button>
      <button id="zout" title="Zoom out">&minus;</button>
      <button id="zfit" title="Fit / reset" style="width:auto">fit</button>
    </div>
  </div>
  <aside>
    <div class="card">
      <div class="roundbar">
        <button id="prev">&#9664; Tick</button>
        <div class="lbl mono" id="roundLbl">Tick 0</div>
        <button id="next">Tick &#9654;</button>
      </div>
      <input type="range" id="slider" min="0" max="0" value="0" step="1">
      <div style="text-align:center;margin-top:6px;"><button id="play">&#9654; Play</button>
      <button id="reset">&#8635; Restart</button></div>
      <div class="muted" style="margin-top:6px;font-size:11px;text-align:center">Play steps tick-by-tick and pauses at each inject / decision.</div>
    </div>

    <div class="card">
      <h2>Resources (this round)</h2>
      <div class="res">
        <div class="top"><span>Budget</span><span class="mono" id="budTxt">0</span></div>
        <div class="bar"><div id="budBar" style="width:0%"></div></div>
      </div>
      <div class="res">
        <div class="top"><span>Political Capital</span><span class="mono" id="polTxt">0</span></div>
        <div class="bar"><div id="polBar" style="width:0%"></div></div>
      </div>
    </div>

    <div class="card">
      <h2>Decisions &amp; Injects</h2>
      <div id="events"></div>
    </div>

    <div class="card detail">
      <h2 id="detTitle">Inspector</h2>
      <div id="detBody"></div>
    </div>

    <div class="card legend">
      <h2>Legend</h2>
      <div><span class="grad"></span><span>red = bad state &rarr; green = good</span></div>
      <div><span class="lineP"></span><span>positive edge (move together)</span></div>
      <div><span class="lineN"></span><span>negative edge (oppose)</span></div>
      <div class="muted" style="margin-top:6px">Inverted nodes read high = bad. <b>Hover</b> a node to light its links; <b>click</b> a node for its drivers, an <b>edge</b> for its weight &amp; lag. <b>Play</b> animates every tick and pauses (flashing red) at each round boundary that fires an inject or decision &mdash; click <b>Continue</b> to proceed. Drag to pan, scroll to zoom.</div>
    </div>
  </aside>
</div>

<script>
"""

# ---- PART 2 (the generated data block) goes here ----

# ---- PART 3: engine + layout + render + zoom + inspector (verbatim; GROUPS removed, inspector typ tweaked) ----
PART3 = r"""
//================= ENGINE =================
const squash=d=>SAT_A*Math.tanh(d/SAT_A);
const clampDev=(d,i)=>Math.max(MINV-BASE[i],Math.min(MAXV-BASE[i],d));
function contrib(now,lag,w,wantHigh){const cn=w*squash(now),cl=w*squash(lag);
  return wantHigh?(cn<=cl?cn:cl):(cn>=cl?cn:cl);}

function simulate(){
  const shock={};
  const add=(round,id,amt)=>{const t=(round-1)*TPR;(shock[t]=shock[t]||{});shock[t][id]=(shock[t][id]||0)+amt;};
  EVENTS.forEach(e=>add(e.round,e.target,e.amt));
  DECISIONS.forEach(d=>add(d.round,d.target,d.amt));
  const dev=[{}]; IDS.forEach(i=>dev[0][i]=0);
  if(shock[0]) for(const i in shock[0]) dev[0][i]=clampDev(dev[0][i]+shock[0][i],i);
  for(let t=0;t<TOTAL;t++){
    const cur=dev[t], tg={}, ac={};
    IDS.forEach(i=>{tg[i]=0;ac[i]=false;});
    for(const e of EDGES){
      const now=cur[e[0]], lg=(t-e[3]>=0)?dev[t-e[3]][e[0]]:0;
      const c=contrib(now,lg,e[2],WANT[e[1]]);
      tg[e[1]]+=c; if(Math.abs(c)>1e-6) ac[e[1]]=true;
    }
    const nx={};
    IDS.forEach(i=>{let v=cur[i];
      if(ac[i]){const a=(tg[i]>=v)?AUP[i]:ADN[i]; v=v+a*(tg[i]-v);}
      nx[i]=clampDev(v,i);});
    if(shock[t+1]) for(const i in shock[t+1]) nx[i]=clampDev(nx[i]+shock[t+1][i],i);
    dev.push(nx);
  }
  return dev;
}
const TRAJ=simulate();

function resourcesAt(r){
  let b=RES.budget.start,p=RES.polcap.start;
  for(let k=1;k<=r;k++){
    if(k>=2){b=Math.min(RES.budget.cap,b+RES.budget.regen);p=Math.min(RES.polcap.cap,p+RES.polcap.regen);}
    DECISIONS.filter(d=>d.round===k).forEach(d=>{b-=(d.spend.budget||0);p-=(d.spend.polcap||0);});
    b=Math.max(0,b);p=Math.max(0,p);
  }
  return {budget:Math.round(b*10)/10,polcap:Math.round(p*10)/10};
}

//================= LAYOUT =================
const LAB_WRAP=15, LH=18, GAP_LV=8, VAL_H=26, PAD=13;
const NW=160, COLW=255, TOPY=86, VGAP=58;
const WRAP={}, NHGT={};
IDS.forEach(id=>{ const ls=wrapText(LABEL[id],LAB_WRAP); WRAP[id]=ls;
  NHGT[id]=PAD*2 + ls.length*LH + GAP_LV + VAL_H; });
const colOf=g=> g.ids.length ? g.ids.reduce((s,id)=>s+NHGT[id],0)+(g.ids.length-1)*VGAP : 0;
let colHeight=0; GROUPS.forEach(g=>{colHeight=Math.max(colHeight,colOf(g));});
const POS={};
GROUPS.forEach((g,gi)=>{
  const x=60+gi*COLW; const h=colOf(g);
  let y=TOPY+(colHeight-h)/2;
  g.box={x:x-24,y:TOPY-54,w:NW+48,h:colHeight+54};
  g.ids.forEach(id=>{ const nh=NHGT[id];
    POS[id]={x:x+NW/2, y:y+nh/2, w:NW, h:nh, lines:WRAP[id]};
    y+=nh+VGAP; });
});
const GW=60+GROUPS.length*COLW+60, GH=TOPY+colHeight+60;

//================= SVG RENDER =================
const SVGNS="http://www.w3.org/2000/svg";
const svg=document.getElementById("svg"), vp=document.getElementById("viewport");
function el(t,a){const e=document.createElementNS(SVGNS,t);for(const k in a)e.setAttribute(k,a[k]);return e;}

const defs=el("defs",{});
[["arr","#d2d2d2"],["arrhi","#000"]].forEach(([id,c])=>{
  const m=el("marker",{id,viewBox:"0 0 10 10",refX:9,refY:5,markerWidth:7,markerHeight:7,orient:"auto-start-reverse"});
  m.appendChild(el("path",{d:"M0,0 L10,5 L0,10 z",fill:c})); defs.appendChild(m);
});
vp.appendChild(defs);

function wrapText(str,max){const out=[],words=str.split(" ");let line="";
  words.forEach(w=>{if((line+" "+w).trim().length>max){if(line)out.push(line);line=w;}else line=(line+" "+w).trim();});
  if(line)out.push(line); return out;}
GROUPS.forEach(g=>{
  vp.appendChild(el("rect",{class:"gbox",x:g.box.x,y:g.box.y,width:g.box.w,height:g.box.h,rx:8}));
  const tx=g.box.x+14, maxW=g.box.w-28;
  const t=el("text",{class:"glabel",x:tx,y:g.box.y+32}); vp.appendChild(t);
  // greedy word-wrap so a long category name never bleeds past its swimlane box
  const words=g.name.split(" "), lines=[]; let cur="";
  t.textContent=g.name;
  if(t.getComputedTextLength()>maxW && words.length>1){
    words.forEach(w=>{ const test=cur?cur+" "+w:w; t.textContent=test;
      if(t.getComputedTextLength()>maxW && cur){lines.push(cur);cur=w;} else cur=test; });
    if(cur) lines.push(cur);
  } else { lines.push(g.name); }
  // baselines shifted up when wrapped so all lines stay inside the 54px header band
  const n=lines.length, y0=g.box.y+(n>1?22:32);
  t.textContent="";
  lines.forEach((ln,i)=>{ const ts=el("tspan",{x:tx,y:y0+i*18}); ts.textContent=ln; t.appendChild(ts);
    // last-resort: compress any single line still wider than the box (e.g. one very long word)
    if(ts.getComputedTextLength()>maxW){ts.setAttribute("textLength",maxW);ts.setAttribute("lengthAdjust","spacingAndGlyphs");} });
});

function border(c,tx,ty){const dx=tx-c.x,dy=ty-c.y;if(!dx&&!dy)return{x:c.x,y:c.y};
  const hw=c.w/2,hh=c.h/2;
  const s=Math.min(dx?hw/Math.abs(dx):1e9, dy?hh/Math.abs(dy):1e9);
  return {x:c.x+dx*s,y:c.y+dy*s};}
const edgeEls=[];
EDGES.forEach((e,idx)=>{
  const a=POS[e[0]],b=POS[e[1]]; const p1=border(a,b.x,b.y),p2=border(b,a.x,a.y);
  const dx=p2.x-p1.x,dy=p2.y-p1.y,len=Math.hypot(dx,dy)||1;
  const k=Math.max(16,Math.min(70,len*0.12));
  const cx=(p1.x+p2.x)/2+(dy/len)*k, cy=(p1.y+p2.y)/2-(dx/len)*k;
  const ln=el("path",{d:`M${p1.x},${p1.y} Q${cx},${cy} ${p2.x},${p2.y}`,
    class:"edge"+(e[2]<0?" neg":""),"marker-end":"url(#arr)"});
  ln.addEventListener("click",ev=>{ev.stopPropagation();selectEdge(idx);});
  vp.appendChild(ln); edgeEls.push(ln);
});

const nodeEls={};
IDS.forEach(id=>{
  const p=POS[id];
  const g=el("g",{class:"node",transform:`translate(${p.x-p.w/2},${p.y-p.h/2})`});
  const rect=el("rect",{x:0,y:0,width:p.w,height:p.h,rx:9,fill:"#ccc"});
  g.appendChild(rect);
  p.lines.forEach((ln,i)=>{const lab=el("text",{class:"nlabel",x:p.w/2,y:PAD+13+i*LH,"text-anchor":"middle"});lab.textContent=ln;g.appendChild(lab);});
  const val=el("text",{class:"nval",x:p.w/2,y:PAD+p.lines.length*LH+GAP_LV+19,"text-anchor":"middle"}); val.textContent="--";
  g.appendChild(val);
  g.addEventListener("click",ev=>{ev.stopPropagation();selectNode(id);});
  g.addEventListener("mouseenter",()=>{if(!selNode)EDGES.forEach((e,idx)=>{if(e[0]===id||e[1]===id)edgeEls[idx].classList.add("hi");});});
  g.addEventListener("mouseleave",()=>{if(!selNode)edgeEls.forEach(l=>l.classList.remove("hi"));});
  vp.appendChild(g); nodeEls[id]={g,rect,val};
});

//================= PAN / ZOOM =================
let tx=0,ty=0,scale=1;
function applyVT(){
  vp.style.transition="transform 0.08s ease-out";
  vp.style.transform=`translate(${tx}px,${ty}px) scale(${scale})`;
  vp.style.transformOrigin="0 0";
}
function fit(){const r=svg.getBoundingClientRect();const s=Math.min(r.width/GW,r.height/GH)*0.96;
  scale=s; tx=(r.width-GW*s)/2; ty=(r.height-GH*s)/2; applyVT();}
window.addEventListener("resize",fit);
svg.addEventListener("wheel",ev=>{ev.preventDefault();
  const r=svg.getBoundingClientRect();const mx=ev.clientX-r.left,my=ev.clientY-r.top;
  const f=ev.deltaY<0?1.03:1/1.03; const ns=Math.max(0.15,Math.min(5,scale*f));
  tx=mx-(mx-tx)*(ns/scale); ty=my-(my-ty)*(ns/scale); scale=ns; applyVT();
},{passive:false});
let pan=null;
svg.addEventListener("mousedown",ev=>{if(ev.target.closest(".node")||ev.target.closest(".edge"))return;
  pan={x:ev.clientX,y:ev.clientY,tx,ty};svg.classList.add("panning");});
window.addEventListener("mousemove",ev=>{if(!pan)return;tx=pan.tx+(ev.clientX-pan.x);ty=pan.ty+(ev.clientY-pan.y);applyVT();});
window.addEventListener("mouseup",()=>{pan=null;svg.classList.remove("panning");});
svg.addEventListener("click",ev=>{if(!ev.target.closest(".node")&&!ev.target.closest(".edge"))clearSel();});
document.getElementById("zin").onclick=()=>{scale=Math.min(5,scale*1.2);applyVT();};
document.getElementById("zout").onclick=()=>{scale=Math.max(0.15,scale/1.2);applyVT();};
document.getElementById("zfit").onclick=fit;

//================= SELECTION / INSPECTOR =================
let selNode=null;
function clearSel(){selNode=null;
  IDS.forEach(i=>nodeEls[i].g.classList.remove("sel"));
  edgeEls.forEach(l=>{l.classList.remove("hi","dim");l.setAttribute("marker-end","url(#arr)");});
  detTitle.textContent="Inspector"; detBody.innerHTML='<span class="muted">Hover a node to light its links. Click a node for what drives it, or an edge for its weight, lag, and mechanism.</span>';
}
function dim(){edgeEls.forEach(l=>{l.classList.add("dim");l.classList.remove("hi");});}
function selectNode(id){
  clearSel(); selNode=id; nodeEls[id].g.classList.add("sel"); dim();
  EDGES.forEach((e,idx)=>{if(e[0]===id||e[1]===id){const l=edgeEls[idx];l.classList.remove("dim");l.classList.add("hi");l.setAttribute("marker-end","url(#arrhi)");}});
  const inc=EDGES.filter(e=>e[1]===id), out=EDGES.filter(e=>e[0]===id);
  const typ = TYPE[id] + (DESC[TYPE[id]]?(" — "+DESC[TYPE[id]]):"") + (INV[id]?" · inverted (higher = worse)":"");
  let h=`<dl><dt>${LABEL[id]}</dt><dd class="muted">${typ}</dd>`;
  h+=`<dt>State now</dt><dd class="mono">${Math.round(BASE[id]+TRAJ[tick][id])} / 100 &nbsp; (baseline ${BASE[id]}, ${WANT[id]?"higher = better":"higher = worse"})</dd></dl>`;
  if(inc.length){h+=`<dt style="font-weight:700;margin-top:8px">Driven by</dt>`;
    inc.forEach(e=>{h+=`<div class="drv"><span class="w">${e[2]>0?"+":""}${e[2]}</span> &larr; ${LABEL[e[0]]} <span class="muted">(lag ${e[3]})</span><br><span class="muted">${e[4]}</span></div>`;});}
  else h+=`<div class="drv muted">No incoming edges &mdash; moved only by a decision or White Cell inject.</div>`;
  if(out.length){h+=`<dt style="font-weight:700;margin-top:8px">Drives</dt>`;
    out.forEach(e=>{h+=`<div class="drv"><span class="w">${e[2]>0?"+":""}${e[2]}</span> &rarr; ${LABEL[e[1]]} <span class="muted">(lag ${e[3]})</span></div>`;});}
  detTitle.textContent="Node"; detBody.innerHTML=h;
}
function selectEdge(idx){
  clearSel(); dim(); const l=edgeEls[idx];l.classList.remove("dim");l.classList.add("hi");l.setAttribute("marker-end","url(#arrhi)");
  const e=EDGES[idx];
  nodeEls[e[0]].g.classList.add("sel"); nodeEls[e[1]].g.classList.add("sel");
  detTitle.textContent="Edge";
  detBody.innerHTML=`<dl><dt>${LABEL[e[0]]} &rarr; ${LABEL[e[1]]}</dt>
    <dd class="mono" style="font-size:14px">weight ${e[2]>0?"+":""}${e[2]} &nbsp;&middot;&nbsp; lag ${e[3]} tick${e[3]===1?"":"s"} &nbsp;&middot;&nbsp; ${e[2]>0?"positive":"negative"}</dd>
    <dt>Mechanism</dt><dd>${e[4]}</dd>
    <dt>Timing</dt><dd class="muted">Harm transmits next tick; benefit waits the full lag (asymmetric-lag rule).</dd></dl>`;
}

//================= TICK PLAYBACK =================
let tick=0, timer=null, awaitEvent=false;
const INTERVAL=600;
const roundLbl=document.getElementById("roundLbl"),slider=document.getElementById("slider"),
      evBox=document.getElementById("events"),detTitle=document.getElementById("detTitle"),detBody=document.getElementById("detBody"),
      budBar=document.getElementById("budBar"),polBar=document.getElementById("polBar"),budTxt=document.getElementById("budTxt"),polTxt=document.getElementById("polTxt"),
      playBtn=document.getElementById("play");
function colorFor(g){return `hsl(${(120*g/100).toFixed(0)},58%,62%)`;}
function roundAt(t){return Math.min(Math.floor(t/TPR)+1,ROUNDS);}
function isEventBoundary(t){ if(t%TPR!==0) return false; const r=t/TPR+1; return r<=ROUNDS && (EVENTS.some(e=>e.round===r)||DECISIONS.some(d=>d.round===r)); }
function render(t){
  tick=t; const d=TRAJ[t]; const r=roundAt(t); const fire=isEventBoundary(t);
  IDS.forEach(i=>{let v=BASE[i]+d[i]; v=Math.max(0,Math.min(100,v));
    const good=WANT[i]?v:100-v; nodeEls[i].rect.setAttribute("fill",colorFor(good)); nodeEls[i].val.textContent=Math.round(v);
    nodeEls[i].g.classList.remove("flash");});
  roundLbl.textContent=`Tick ${t} / ${TOTAL}  ·  Round ${r}`; slider.value=t;
  const res=resourcesAt(r);
  budBar.style.width=res.budget+"%"; polBar.style.width=res.polcap+"%";
  budTxt.textContent=res.budget+" / 100"; polTxt.textContent=res.polcap+" / 100";
  const inj=EVENTS.filter(e=>e.round===r), dec=DECISIONS.filter(e=>e.round===r);
  if(fire){ [...inj,...dec].forEach(e=>{ const n=nodeEls[e.target]; if(!n) return;
    n.g.style.setProperty("--glow", n.rect.getAttribute("fill")); n.g.classList.add("flash"); }); }
  let h="";
  inj.forEach(e=>{h+=`<div class="evt inject${fire?' fire':''}"><span class="tag">&#9672; WHITE CELL INJECT</span><br>${e.label}<br><span class="mono muted">${LABEL[e.target]} ${e.amt>=0?"+":""}${e.amt}</span></div>`;});
  dec.forEach(e=>{const sp=Object.entries(e.spend).map(([k,v])=>`${v} ${k}`).join(", ");
    h+=`<div class="evt${fire?' fire':''}"><span class="tag">&#9632; PLAYER DECISION</span><br>${e.label}<br><span class="mono muted">${LABEL[e.target]} +${e.amt} &nbsp;&middot;&nbsp; cost: ${sp}</span></div>`;});
  if(!h)h=`<span class="muted">${t%TPR===0?'Round boundary &mdash; no decision or inject this round. ':'Propagating between rounds&hellip; '}watch the ticks settle.</span>`;
  evBox.innerHTML=h;
  if(selNode) selectNode(selNode);
}
function stopTimer(){ if(timer){clearInterval(timer);timer=null;} }
function setTick(t,fromPlay){
  t=Math.max(0,Math.min(TOTAL,t)); render(t);
  if(fromPlay && isEventBoundary(t)){ stopTimer(); awaitEvent=true; playBtn.textContent="▶ Continue"; playBtn.classList.add("attn"); }
}
function startTimer(){ stopTimer(); timer=setInterval(()=>{
  if(tick>=TOTAL){ stopTimer(); playBtn.textContent="▶ Play"; return; } setTick(tick+1,true); }, INTERVAL); }
function manualGo(t){ stopTimer(); awaitEvent=false; playBtn.classList.remove("attn"); playBtn.textContent="▶ Play"; setTick(t,false); }
document.getElementById("prev").onclick=()=>manualGo(tick-1);
document.getElementById("next").onclick=()=>manualGo(tick+1);
document.getElementById("reset").onclick=()=>manualGo(0);
slider.oninput=()=>manualGo(+slider.value);
playBtn.onclick=()=>{
  if(timer){ stopTimer(); playBtn.textContent="▶ Play"; return; }
  awaitEvent=false; playBtn.classList.remove("attn");
  if(tick>=TOTAL) setTick(0,false);
  playBtn.textContent="❚❚ Pause"; startTimer();
};

//================= INIT =================
slider.min=0; slider.max=TOTAL; clearSel(); fit(); render(0);
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="Render a world_graph.json as a Gordian-style playable index.html.")
    ap.add_argument("graph", help="path to world_graph.json")
    ap.add_argument("--out", default=None, help="output html path (default: <scenario>.html next to the graph)")
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--ticks", type=int, default=6, help="ticks per round")
    ap.add_argument("--seed", type=int, default=0, help="rotates the synthetic decision/inject selection")
    args = ap.parse_args()

    try:
        with open(args.graph, "r", encoding="utf-8") as f:
            graph = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return 2
    if not graph.get("nodes"):
        print("ERROR: graph has no nodes", file=sys.stderr)
        return 2

    data_js = build_data_js(graph, args.rounds, args.ticks, args.seed)
    slug = scenario_slug(graph, args.graph)
    title = slug.replace("_", " ").replace("-", " ").title()
    html = PART1.replace("__TITLE__", title).replace("__SLUG__", slug) + data_js + PART3

    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.graph)), slug + ".html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    n_dec = data_js.count('"label"')  # rough
    print(f"rendered -> {out}")
    print(f"  {len(graph['nodes'])} nodes, {len(graph['edges'])} edges, "
          f"{args.rounds} rounds x {args.ticks} ticks = {args.rounds*args.ticks} ticks")
    print(f"  UI matches gordian_knot_sim.html (white bg, hsl red->green nodes, zoom/pan, inspector, play)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
