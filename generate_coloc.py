#!/usr/bin/env python3
"""Génère index.html (planning coloc Théo / Jeanne / Pierre) depuis des liens iCal.

Usage :
  python generate_coloc.py                       # liens dans ICAL_PIERRE / ICAL_THEO / ICAL_JEANNE
  python generate_coloc.py --ics Pierre=lien_ou_fichier.ics Théo=... Jeanne=...
  python generate_coloc.py --offline             # réutilise donnees_coloc.json sans rien télécharger
"""
import argparse, json, os, re, sys, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
ENV = {"Pierre": "ICAL_PIERRE", "Théo": "ICAL_THEO", "Jeanne": "ICAL_JEANNE"}


def load(src):
    if src.startswith("webcal://"):
        src = "https://" + src[len("webcal://"):]
    if src.startswith("http"):
        req = urllib.request.Request(src, headers={"User-Agent": "planning-coloc"})
        import ssl
        try:
            import certifi  # certificats à jour (évite les soucis de Windows)
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = ssl.create_default_context()
        return urllib.request.urlopen(req, timeout=60, context=ctx).read().decode("utf-8", "replace")
    return open(src, encoding="utf-8").read()


def parse_dt(params, val):
    if "VALUE=DATE" in params or len(val) == 8:
        return datetime.strptime(val[:8], "%Y%m%d"), True
    if val.endswith("Z"):
        d = datetime.strptime(val, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(PARIS)
    else:
        m = re.search(r"TZID=([^;:]+)", params)
        try:
            tz = ZoneInfo(m.group(1)) if m else PARIS
        except Exception:
            tz = PARIS
        d = datetime.strptime(val[:15], "%Y%m%dT%H%M%S").replace(tzinfo=tz).astimezone(PARIS)
    return d.replace(tzinfo=None), False


def parse_ics(text, who):
    text = re.sub(r"\r?\n[ \t]", "", text)
    out, cur = [], None
    for line in text.splitlines():
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            if "DTSTART" in cur:
                s, allday = parse_dt(*cur["DTSTART"])
                summ = cur.get("SUMMARY", ("", ""))[1].replace("\\,", ",").replace("\\n", " ").strip()
                rec = {"date": s.strftime("%Y-%m-%d"), "who": who, "poste": summ}
                if allday:
                    rec["allday"] = True
                elif "DTEND" in cur:
                    e, _ = parse_dt(*cur["DTEND"])
                    rec.update(start=s.strftime("%H:%M"), end=e.strftime("%H:%M"),
                               dur=int((e - s).total_seconds() // 60))
                    if rec["dur"] <= 0:
                        continue
                else:
                    continue
                out.append(rec)
            cur = None
        elif cur is not None and ":" in line:
            k, v = line.split(":", 1)
            cur[k.split(";")[0].upper()] = (k.upper(), v)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ics", nargs="*", default=[])
    ap.add_argument("--json", default="donnees_coloc.json")
    ap.add_argument("-o", "--out", default="index.html")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    srcs = dict(s.split("=", 1) for s in a.ics)
    for who, var in ENV.items():
        if who not in srcs and os.environ.get(var):
            srcs[who] = os.environ[var]
    if srcs and not a.offline:
        recs = []
        for who, src in srcs.items():
            r = parse_ics(load(src), who)
            print(f"{who} : {len(r)} évènements")
            recs += r
        recs = [dict(t) for t in {tuple(sorted(r.items())) for r in recs}]
        recs.sort(key=lambda r: (r["date"], r.get("start", ""), r["who"]))
        dates = [r["date"] for r in recs] or [datetime.now().strftime("%Y-%m-%d")]
        data = {"source": datetime.now(PARIS).isoformat(timespec="seconds"),
                "from": min(dates), "to": max(dates), "people": sorted(srcs), "records": recs}
        json.dump(data, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    else:
        data = json.load(open(a.json, encoding="utf-8"))
    extra_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evenements_coloc.json")
    if os.path.exists(extra_path):
        extra = json.load(open(extra_path, encoding="utf-8"))
        data["evenements"] = extra.get("evenements", [])
        data["vacances"] = extra.get("vacances", [])
    open(a.out, "w", encoding="utf-8").write(PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    print(f"{a.out} écrit : {len(data['records'])} évènements, synchro {data['source']}")


PAGE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Planning coloc</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@1,500&family=Jost:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--bg:#ece7e1;--card:#faf8f5;--ink:#4a4440;--mut:#a0958c;--line:#ebe5de;--H:700px;
--Tb:#efd5c3;--Tt:#7d5640;--Jb:#d6dfcb;--Jt:#566a4b;--Pb:#d0dce4;--Pt:#4d6477}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.25 "Jost",system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:14px}
.bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.bar .sp{flex:1}
button{font:inherit;border:0;background:#f6f2ed;border-radius:99px;padding:6px 13px;cursor:pointer;color:var(--ink)}
button:hover{background:#efe8e0}
button.on{background:var(--ink);color:#faf8f5}
.seg{display:inline-flex;gap:4px}
#banner{position:relative;font-size:12px;color:var(--mut)}
#banner.old{background:#f6e1df;color:#8a4b45;border-radius:99px;padding:6px 14px;cursor:help}
#banner .tip{display:none;position:absolute;left:10px;top:100%;margin-top:4px;background:var(--ink);color:#fff;padding:5px 10px;border-radius:10px;z-index:30;white-space:nowrap}
#banner.old:hover .tip{display:block}
.sheet{background:var(--card);border-radius:24px;padding:22px 26px 16px;box-shadow:0 6px 30px rgba(90,70,50,.08)}
.head{display:flex;align-items:baseline;gap:16px;margin-bottom:12px}
.head h1{margin:0;font:italic 500 30px "Cormorant Garamond",Georgia,serif;letter-spacing:.01em}
.head .wk{color:var(--mut);font-size:13px;letter-spacing:.14em;text-transform:uppercase}
.grid{display:grid;grid-template-columns:30px repeat(7,1fr);column-gap:8px}
.dh{text-align:center;padding-bottom:6px}
.dh b{font:600 11px "Jost",sans-serif;letter-spacing:.16em;text-transform:uppercase}
.dh span{display:block;color:var(--mut);font-size:11px;margin-top:1px}
.dh.today b{color:#c0714f}
.ini{display:flex;margin-top:5px}.ini i{flex:1;margin:0 2px;font-style:normal;font-size:10px;font-weight:600;padding-bottom:2px;border-bottom:3px solid}
.ini .T{color:var(--Tt);border-color:var(--Tb)}.ini .J{color:var(--Jt);border-color:var(--Jb)}.ini .P{color:var(--Pt);border-color:var(--Pb)}
.chips{display:flex;flex-direction:column;gap:2px;margin-top:5px}
.chip{font-size:10px;line-height:1.2;background:#efe8f3;color:#5e4d74;border-radius:8px;padding:2px 6px;text-align:left}
.notes{margin-top:14px;padding:0 4px}
.notes b{font:italic 500 17px "Cormorant Garamond",Georgia,serif;color:var(--mut)}
.notes i{display:block;height:30px;border-bottom:1px solid #e0d8cf}
.axis{position:relative;height:var(--H)}
.axis i{position:absolute;right:3px;font-style:normal;font-size:9.5px;color:var(--mut);transform:translateY(-50%)}
.axis i.k{font-size:13px;font-weight:600;color:var(--ink)}
.body{position:relative;height:var(--H);display:flex;gap:3px;border-radius:16px;padding:6px 3px;background:#f3eee8;overflow:hidden}
.col{position:relative;flex:1;height:100%}
.b{position:absolute;left:0;right:0;border-radius:12px;padding:5px 0;display:flex;flex-direction:column;align-items:center;justify-content:space-between;
 font-size:10px;font-weight:500;overflow:hidden;z-index:3}
.b .lab{writing-mode:vertical-rl;font-weight:500;font-size:11px;white-space:nowrap;overflow:hidden;letter-spacing:.02em}
.T .b{background:var(--Tb);color:var(--Tt)}.J .b{background:var(--Jb);color:var(--Jt)}.P .b{background:var(--Pb);color:var(--Pt)}
.ch{position:absolute;left:0;right:0;z-index:2;border-radius:12px;display:flex;justify-content:center;padding-top:5px;font-size:16px;line-height:1;overflow:hidden;
 background:#e8e1d9}
.ad{position:absolute;left:0;right:0;top:0;bottom:0;z-index:1;display:flex;align-items:center;justify-content:center;background:#ebe5de;border-radius:12px;color:var(--mut);font-size:11px}
.ad span{writing-mode:vertical-rl}
.ad.vac span{background:rgba(255,255,255,.8);padding:8px 3px;border-radius:8px;font-weight:500}
.T .ad.vac{background:repeating-linear-gradient(135deg,var(--Tb) 0 5px,#fbf5ee 5px 10px);color:var(--Tt)}
.J .ad.vac{background:repeating-linear-gradient(135deg,var(--Jb) 0 5px,#f6f9f2 5px 10px);color:var(--Jt)}
.P .ad.vac{background:repeating-linear-gradient(135deg,var(--Pb) 0 5px,#f3f7fa 5px 10px);color:var(--Pt)}
.com{position:absolute;left:0;right:0;border-radius:12px;z-index:1;pointer-events:none;text-align:center;font-size:20px;line-height:1;padding-top:6px;background:repeating-linear-gradient(135deg,rgba(214,150,140,.3) 0 1px,transparent 1px 5px),#fbf4f2}
.np{position:absolute;inset:0;z-index:0;border-radius:16px;display:flex;align-items:center;justify-content:center;color:#cfc6bd;font-size:12px;pointer-events:none}
.np span,.miss{writing-mode:vertical-rl}
.miss{position:absolute;left:0;right:0;top:8px;text-align:center;color:#c2b8ae;font-size:10px;font-style:italic}
.foot{display:flex;justify-content:space-between;margin-top:12px;font-size:11px;color:var(--mut)}
@page{size:A4 landscape;margin:6mm}
@media print{
 :root{--H:100mm}
 .chip{font-size:7.5px;padding:1px 4px}
 .notes{margin-top:3mm}.notes b{font-size:12px}.notes i{height:7.2mm}
 body{background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
 .wrap{padding:0;max-width:none}.noprint{display:none!important}
 .sheet{box-shadow:none;padding:2mm 0 0;border-radius:0;background:#fff}
 .head h1{font-size:22px}.head{margin-bottom:3px}
 .axis i{font-size:7px}.axis i.k{font-size:9.5px}
 .b{font-size:8.5px}.b .lab{font-size:8.5px}.com{font-size:15px}
 .grid{grid-template-columns:24px repeat(7,1fr);column-gap:5px}
}
</style></head><body><div class="wrap">
<div class="bar noprint">
 <button id="prev">◀</button><button id="today">aujourd'hui</button><button id="next">▶</button>
 <span class="sp"></span><div id="banner"></div>
 
 <button onclick="window.print()">🖨️ Imprimer / PDF</button>
</div>
<div class="sheet">
 <div class="head"><h1>coolocs ✨</h1><span class="wk" id="wk"></span></div>
 <div class="grid" id="grid"></div>
 <div class="notes"><b>notes</b><i></i><i></i><i></i></div>
 <div class="foot"><span>🐑 repos après une garde · 🎉 tous les trois dispos</span><span id="sync"></span></div>
</div></div>
<script>
const D = __DATA__;
const PEOPLE=[{k:'Théo',c:'T'},{k:'Jeanne',c:'J'},{k:'Pierre',c:'P'}];
const CHUT_MORNING=810, CHUT_MIDNIGHT=660, THRESH=3;
const pad=n=>String(n).padStart(2,'0');
const mins=s=>{const [h,m]=s.split(':').map(Number);return h*60+m};
const dnum=s=>{const [y,m,d]=s.split('-').map(Number);return Date.UTC(y,m-1,d)/864e5};
const dstr=n=>new Date(n*864e5).toISOString().slice(0,10);
const fr=n=>{const s=dstr(n);return s.slice(8)+'/'+s.slice(5,7)};
const hm=m=>pad(Math.floor(m/60)%24)+'h'+pad(m%60);
const dow=n=>new Date(n*864e5).getUTCDay();
const JOURS=['Dimanche','Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi'];
const work={}, chut={}, notes={};
const add=(map,p,dn,a,b,x)=>{const k=p+'|'+dn;(map[k]=map[k]||[]).push({a,b,...x})};
function spread(map,p,d0,s,E,x){
  for(let cur=s;cur<E;){const ds=Math.floor(cur/1440)*1440,se=Math.min(E,ds+1440);
    add(map,p,d0+ds/1440,cur-ds,se-ds,{...x,cont:cur>s,more:se<E});cur=se}}
const clean=t=>t.replace(/^Internes\s*/i,'').replace(/\b\d{1,2}h(\d{2})?\s*-\s*(\d{1,2}h(\d{2})?|minuit)\b/ig,'').replace(/\s+/g,' ').trim();
const evs={}, evBusy={};
const hmin=t=>{const m=t.match(/(\d{1,2})h(\d{2})?/);return m?(+m[1])*60+(+(m[2]||0)):null};
function evInterval(x){
  if(!x.heure)return [480,1080];
  const parts=x.heure.split('–'), a=hmin(parts[0]);
  const b=parts[1]?hmin(parts[1]):a+120;
  return [a,b];
}
(D.evenements||[]).forEach(x=>{const k=dnum(x.date);(evs[k]=evs[k]||[]).push(x);
  const [a,b]=evInterval(x);
  if(x.bloque!==false)x.qui.forEach(q=>add(evBusy,q,k,a,b,{}))});
(D.vacances||[]).forEach(v=>{for(let n=dnum(v.du);n<=dnum(v.au);n++)add(notes,v.qui,n,0,1440,{label:'vacances',emo:'🏖️'})});
D.records.forEach(r=>{
  const d0=dnum(r.date);
  if(r.allday){add(notes,r.who,d0,0,1440,{label:r.poste});return}
  const s=mins(r.start);let e;
  if(r.dur)e=s+r.dur;else{e=mins(r.end);if(e===0)e=1440;else if(e<=s)e+=1440}
  spread(work,r.who,d0,s,e,{label:clean(r.poste),txt:hm(s)+'–'+hm(e),end:hm(e)});
  let ce=null;
  if(e%1440===0)ce=e+CHUT_MIDNIGHT;
  else if(e>1440&&e%1440<CHUT_MORNING)ce=Math.floor(e/1440)*1440+CHUT_MORNING;
  if(ce)spread(chut,r.who,d0,e,ce,{});
});
function together(dn,awake){
  const iv=[];
  PEOPLE.forEach(p=>{(work[p.k+'|'+dn]||[]).forEach(x=>iv.push([x.a,x.b]));(evBusy[p.k+'|'+dn]||[]).forEach(x=>iv.push([x.a,x.b]));
    if(awake)(chut[p.k+'|'+dn]||[]).forEach(x=>iv.push([x.a,x.b]))});
  iv.sort((x,y)=>x[0]-y[0]);
  const free=[];let cur=0;
  iv.forEach(([a,b])=>{if(a>cur)free.push([cur,a]);cur=Math.max(cur,b)});
  if(cur<1440)free.push([cur,1440]);
  return free.filter(([a,b])=>b-a>=60);
}
const toN=dnum(D.to);
const mondayOf=n=>n-((dow(n)+6)%7);
const t0=new Date(), todayN=Math.floor(Date.UTC(t0.getFullYear(),t0.getMonth(),t0.getDate())/864e5);
let ws=mondayOf(todayN), mode='eve';
const L=m=>(m/1440*100)+'%', W=(a,b)=>((b-a)/1440*100)+'%';
function emo(label,a){
  const l=label.toLowerCase();let e=[];
  if(/garde/.test(l))e.push('🌙');else if(/\bwe\b/.test(l))e.push('🌿');else if(/sam/.test(l))e.push('☀️');
  else e.push(a<600?'🌤️':a<900?'☕':'🌆');
  if(/\bua\b/.test(l))e.push('🚑');if(/chir/.test(l))e.push('🩺');if(/\bmed\b/.test(l))e.push('💊');
  return e.join('');
}
function col(p,dn){
  const k=p.k+'|'+dn; let h='<div class="col '+p.c+'">';
  if(D.people&&!D.people.includes(p.k))return h+'<div class="miss">lien iCal manquant</div></div>';
  (notes[k]||[]).forEach(x=>h+=`<div class="ad${x.emo?' vac':''}"><span>${x.emo||'📅'} ${x.label}</span></div>`);
  (chut[k]||[]).forEach(x=>h+=`<div class="ch${x.cont?' cs':''}" title="${p.k} : repos jusqu'à ${hm(x.b)}" style="top:${L(x.a)};height:${W(x.a,x.b)}">🐑</div>`);
  const wl=(work[k]||[]).slice().sort((u,v)=>u.a-v.a);
  wl.forEach((x,i)=>{
    const nx=wl[i+1], clip=nx&&nx.a<x.b, db=clip?nx.a:x.b;
    const cls=(x.cont?' cs':'')+(x.more?' ce':'');
    const e0=x.cont?'':emo(x.label,x.a);
    const lab=(db-x.a>=120)?`<span class="lab">${e0}${x.label?' '+x.label:''}</span>`:'<span></span>';
    h+=`<div class="b${cls}" title="${p.k} — ${x.label} (${x.txt})" style="top:calc(${L(x.a)} + 1px);height:calc(${W(x.a,db)} - 2px)"><span>${x.cont?'↳':hm(x.a)}</span>${lab}<span>${clip?'':x.more?'↴':hm(x.b)}</span></div>`});
  return h+'</div>';
}
function chips(dn){
  return '<div class="chips">'+(evs[dn]||[]).map(x=>{
    const all=x.qui.length===3, who=all?'':' ('+x.qui.map(q=>q[0]).join('')+')';
    const t=`${x.emoji} ${x.heure?x.heure+' ':''}${x.label}${who}${x.incertain?' ?':''}`;
    return `<div class="chip" title="${x.label}${x.lieu?' — '+x.lieu:''}${x.heure?' — '+x.heure:''}${x.incertain?' (à vérifier)':''}">${t}</div>`}).join('')+'</div>';
}
function render(){
  document.getElementById('wk').textContent='Semaine du '+fr(ws)+' au '+fr(ws+6)+'/'+dstr(ws+6).slice(0,4);
  let g='<div></div>';
  for(let i=0;i<7;i++){const dn=ws+i;
    g+=`<div class="dh ${dn===todayN?'today':''}"><b>${JOURS[dow(dn)].slice(0,3)}</b><span>${fr(dn)}</span><div class="ini">${PEOPLE.map(p=>`<i class="${p.c}">${p.k[0]}</i>`).join('')}</div>${chips(dn)}</div>`}
  g+='<div class="axis">';
  for(let i=0;i<=24;i++)g+=`<i class="${[8,12,18].includes(i)?'k':''}" style="top:calc(6px + (100% - 12px) * ${i/24})">${i}h</i>`;
  g+='</div>';
  for(let i=0;i<7;i++){
    const dn=ws+i; g+='<div class="body">';
    if(dn>toN)g+='<div class="np"><span>planning pas encore publié</span></div>';
    else if(mode!=='none'&&!(D.people&&D.people.length<3))together(dn,mode==='eve').forEach(([a,b])=>g+=`<div class="com" style="top:${L(a)};height:${W(a,b)}">🎉</div>`);
    g+=PEOPLE.map(p=>col(p,dn)).join('');
    g+='</div>';
  }
  document.getElementById('grid').innerHTML=g;
}
prev.onclick=()=>{ws-=7;render()};next.onclick=()=>{ws+=7;render()};today.onclick=()=>{ws=mondayOf(todayN);render()};
document.querySelectorAll('#modes button').forEach(b=>b.onclick=()=>{mode=b.dataset.m;
  document.querySelectorAll('#modes button').forEach(x=>x.classList.toggle('on',x===b));render()});
(function(){
  const src=new Date(D.source),days=Math.floor((Date.now()-src)/864e5);
  const f=src.toLocaleString('fr-FR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',timeZone:'Europe/Paris'});
  document.getElementById('sync').textContent='synchro '+f;
  const el=document.getElementById('banner');
  if(days>=THRESH){el.className='old';
    el.innerHTML=`⚠️ Données figées depuis ${days} jours (synchro : ${f}). Merci d'harceler Pierre pour une mise à jour.<span class="tip">📍 1 avenue de l'ancien vélodrome, Toulouse</span>`}
  else el.textContent='🔄 Synchro iCal : '+f;
})();
render();
</script></body></html>
"""

if __name__ == "__main__":
    main()
