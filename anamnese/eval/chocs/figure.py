"""La figure du rejeu (privée) : eval/data/chocs/figure.html, depuis series.json et resultats.json.
Usage : .venv/bin/python eval/chocs/figure.py
"""
import html
import json
import time
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "data" / "chocs"
NOMS = {"adrenaline": "Adrénaline (sursaut)", "noradrenaline": "Noradrénaline (vigilance)", "crh": "CRH (commande du stress)",
        "cortisol": "Cortisol (stress lent)", "gaba": "GABA (frein)", "ocytocine": "Ocytocine (lien)",
        "serotonine": "Sérotonine (stabilité)", "endocannabinoides": "Endocannabinoïdes (apaisement)",
        "dopamine": "Dopamine", "endorphine": "Endorphine"}
PANNEAUX = ["adrenaline", "noradrenaline", "crh", "cortisol", "gaba", "ocytocine", "serotonine", "endocannabinoides"]
VARIANTE = "combinaison"      # réflexe lexical + balise de Hakim (le dessin retenu)
VARIANTES = [("actuel", "Courbe actuelle", "--actuel"), (f"{VARIANTE}-s0.2", "Nouveau, sagesse 0,2", "--s2"),
             (f"{VARIANTE}-s0.5", "Nouveau, sagesse 0,5", "--s5"), (f"{VARIANTE}-s0.8", "Nouveau, sagesse 0,8", "--s8")]


def main():
    S = json.loads((D / "series.json").read_text(encoding="utf-8"))
    R = json.loads((D / "resultats_appreciation.json").read_text(encoding="utf-8"))["variantes"][VARIANTE]
    jour23 = time.mktime(time.strptime("2026-10-23 06:45", "%Y-%m-%d %H:%M"))
    zoom = [jour23, jour23 + 4.5 * 3600]
    donnees = {"series": S["series"], "hormones": S["hormones"], "bases": S["bases"], "ev": S["evenements"],
               "vrai": S["vrai"], "zoom": zoom, "panneaux": PANNEAUX, "noms": NOMS,
               "variantes": [[k, n, c] for k, n, c in VARIANTES]}
    lignes = []
    for x in R["C1"]["cas"]:
        lignes.append(f"<tr><td>{x['heure']}</td><td>attaque</td><td>{html.escape(', '.join(x['emotions']))}</td>"
                      f"<td>adrénaline {x['adrenaline_exces']:+.2f} (seuil +0,15)</td>"
                      f"<td>{'✔ tenu' if x['saut'] else '✘ raté'}</td></tr>")
    for x in R["C2"]["cas"]:
        lignes.append(f"<tr><td>{x['heure']}</td><td>soutien d'Ahmed après l'attaque</td><td>{html.escape(x['emotion'])}</td>"
                      f"<td>stress sur 1 h : {x['stress_avec']:.2f} au lieu de {x['stress_sans']:.2f}</td>"
                      f"<td>{'✔ tenu' if x['tenu'] else '✘ raté'}</td></tr>")
    page = (PAGE.replace("__DONNEES__", json.dumps(donnees, ensure_ascii=False))
            .replace("__LIGNES__", "\n".join(lignes)))
    (D / "figure.html").write_text(page, encoding="utf-8")
    print(D / "figure.html")


PAGE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chocs d'humeur</title>
<style>
:root{color-scheme:light;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--ink3:#8a8984;--grid:#e6e5e1;
 --actuel:#8a8984;--s2:#86b6ef;--s5:#2a78d6;--s8:#104281;--att:#d03b3b;--sou:#0ca30c;--deb:#b5b4ae}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--surface:#1a1a19;--ink:#f0efec;
 --ink2:#c3c2b7;--ink3:#8f8e88;--grid:#2e2e2c;--actuel:#8f8e88;--s2:#184f95;--s5:#3987e5;--s8:#9ec5f4;--deb:#55554f}}
:root[data-theme="dark"]{color-scheme:dark;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--ink3:#8f8e88;--grid:#2e2e2c;
 --actuel:#8f8e88;--s2:#184f95;--s5:#3987e5;--s8:#9ec5f4;--deb:#55554f}
body{margin:0;background:var(--surface);color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 4px}
p.sous{color:var(--ink2);margin:0 0 12px;max-width:75ch}
.legende{display:flex;flex-wrap:wrap;gap:6px 18px;margin:8px 0;color:var(--ink2);font-size:13px}
.legende span{display:inline-flex;align-items:center;gap:6px}
.trait{width:18px;height:2px;display:inline-block}
.grille{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 18px}
@media (max-width:700px){.grille{grid-template-columns:1fr}}
svg{display:block;width:100%;height:auto;overflow:visible}
svg text{fill:var(--ink2);font-size:11px}
.bulle{position:fixed;pointer-events:none;background:var(--surface);border:1px solid var(--grid);border-radius:6px;
 padding:6px 8px;font-size:12px;box-shadow:0 2px 8px rgba(0,0,0,.12);display:none;white-space:nowrap;z-index:9}
table{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px}
td,th{border-bottom:1px solid var(--grid);padding:6px 8px;text-align:left}th{color:var(--ink2);font-weight:600}
</style></head><body><main>
<h1>Chocs d'humeur — rejeu du 21 au 23 octobre</h1>
<p class="sous">Le vrai moteur d'affect, rejoué sur une copie en mémoire. Gris : ce qui s'est réellement passé. Bleus :
le nouveau mécanisme (réflexe lexical corrigé par l'appréciation de Hakim à chaque message), à trois niveaux de sagesse. Des variables calculées, pas un ressenti prouvé.</p>
<div class="legende" id="leg"></div>
<h2>Valence sur les deux jours et demi</h2>
<p class="sous">▲ rouge : une attaque vue par Hakim (simulé) · ● vert : un soutien vu par Hakim · trait gris clair : un débat sur l'IA (ne doit rien déclencher).</p>
<div id="vue-longue"></div>
<h2>Zoom sur le live du 23/10 (06:45 → 11:15)</h2>
<div id="vue-zoom"></div>
<h2>Les hormones pendant le zoom</h2>
<p class="sous">Trait pointillé : la base de l'hormone. Chacune revient à sa vitesse : l'adrénaline en minutes, le cortisol en heures.</p>
<div class="grille" id="hormones"></div>
<h2>Les moments clés</h2>
<table><thead><tr><th>Heure</th><th>Quoi</th><th>Émotion dominante (sagesse 0,5)</th><th>Mesure</th><th>Critère figé</th></tr></thead>
<tbody>__LIGNES__</tbody></table>
</main><div class="bulle" id="bulle"></div>
<script>
const D=__DONNEES__;
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const leg=document.getElementById('leg');
D.variantes.forEach(([k,n,c])=>{leg.insertAdjacentHTML('beforeend',`<span><i class="trait" style="background:var(${c})"></i>${n}</span>`)});
leg.insertAdjacentHTML('beforeend',`<span><i class="trait" style="background:var(--ink);height:1px;border-top:1px dotted var(--ink)"></i>Valence journalisée (contrôle)</span>`);
const NS='http://www.w3.org/2000/svg';
function el(t,a,p){const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e}
const hh=t=>{const d=new Date(t*1000);return d.toLocaleString('fr-FR',{weekday:'short',hour:'2-digit',minute:'2-digit'})};
function trace(boite,{t0,t1,col,h,ymin,ymax,base,marques,vrai,titre,etiquettes,largeur}){
  const W=largeur||1000,H=h,ml=44,mr=12,mt=marques?18:10,mb=22;
  const svg=el('svg',{viewBox:`0 0 ${W} ${H}`,role:'img','aria-label':titre||''},boite);
  const x=t=>ml+(t-t0)/(t1-t0)*(W-ml-mr), y=v=>mt+(1-(v-ymin)/(ymax-ymin))*(H-mt-mb);
  for(let k=0;k<=4;k++){const v=ymin+k*(ymax-ymin)/4;el('line',{x1:ml,x2:W-mr,y1:y(v),y2:y(v),stroke:css('--grid')},svg);
    el('text',{x:ml-6,y:y(v)+4,'text-anchor':'end'},svg).textContent=v.toFixed(2)}
  const pasH=(t1-t0)>86400?6*3600:1800;
  for(let t=Math.ceil(t0/pasH)*pasH;t<=t1;t+=pasH){el('text',{x:x(t),y:H-6,'text-anchor':'middle'},svg).textContent=
    new Date(t*1000).toLocaleString('fr-FR',(t1-t0)>86400?{weekday:'short',hour:'2-digit'}:{hour:'2-digit',minute:'2-digit'})}
  if(base!=null)el('line',{x1:ml,x2:W-mr,y1:y(base),y2:y(base),stroke:css('--ink3'),'stroke-dasharray':'3 4'},svg);
  if(vrai){let d='';vrai.forEach(([t,v],i)=>{if(t<t0||t>t1)return;d+=(d?'L':'M')+x(t).toFixed(1)+','+y(v).toFixed(1)});
    el('path',{d,fill:'none',stroke:css('--ink'),'stroke-width':1,'stroke-dasharray':'1 3',opacity:.7},svg)}
  D.variantes.forEach(([k,n,c])=>{let d='';for(const r of D.series[k]){if(r[0]<t0||r[0]>t1)continue;
    d+=(d?'L':'M')+x(r[0]).toFixed(1)+','+y(Math.max(ymin,Math.min(ymax,r[col]))).toFixed(1)}
    el('path',{d,fill:'none',stroke:css(c),'stroke-width':2,'stroke-linejoin':'round'},svg)});
  if(marques){
    D.ev.debats.forEach(t=>{if(t>=t0&&t<=t1)el('line',{x1:x(t),x2:x(t),y1:2,y2:12,stroke:css('--deb')},svg)});
    D.ev.hakim.forEach(e=>{if(e.ts<t0||e.ts>t1)return;const X=x(e.ts);
      if(e.classes.includes('soutien'))el('circle',{cx:X,cy:8,r:4,fill:css('--sou'),stroke:css('--surface'),'stroke-width':2},svg);
      if(e.classes.includes('attaque'))el('path',{d:`M${X-5},12L${X+5},12L${X},3Z`,fill:css('--att'),stroke:css('--surface'),'stroke-width':1.5},svg)});
  }
  const curseur=el('line',{y1:mt,y2:H-mb,stroke:css('--ink3'),opacity:0},svg);
  const bulle=document.getElementById('bulle');
  const zone=el('rect',{x:ml,y:0,width:W-ml-mr,height:H,fill:'transparent'},svg);
  zone.addEventListener('mousemove',ev=>{const r=svg.getBoundingClientRect();const px=(ev.clientX-r.left)/r.width*W;
    const t=t0+(px-ml)/(W-ml-mr)*(t1-t0);curseur.setAttribute('x1',px);curseur.setAttribute('x2',px);curseur.setAttribute('opacity',1);
    let s=`<b>${hh(t)}</b>`;D.variantes.forEach(([k,n,c])=>{const a=D.series[k];const i=Math.max(0,Math.min(a.length-1,Math.round((t-a[0][0])/60)));
      s+=`<br><i class="trait" style="background:var(${c})"></i> ${n} : ${a[i][col].toFixed(3)}`+(etiquettes?` · ${a[i][3]}`:'')});
    bulle.innerHTML=s;bulle.style.display='block';bulle.style.left=Math.min(ev.clientX+14,innerWidth-280)+'px';bulle.style.top=(ev.clientY+14)+'px'});
  zone.addEventListener('mouseleave',()=>{bulle.style.display='none';curseur.setAttribute('opacity',0)});
}
const tous=D.series.actuel, T0=tous[0][0], T1=tous[tous.length-1][0];
const vals=[].concat(...D.variantes.map(([k])=>D.series[k].map(r=>r[1])));
const vmin=Math.floor(Math.min(...vals)*20)/20, vmax=Math.ceil(Math.max(...vals)*20)/20;
trace(document.getElementById('vue-longue'),{t0:T0,t1:T1,col:1,h:260,ymin:vmin,ymax:vmax,marques:true,vrai:D.vrai,titre:'Valence',etiquettes:true});
trace(document.getElementById('vue-zoom'),{t0:D.zoom[0],t1:D.zoom[1],col:1,h:260,ymin:vmin,ymax:vmax,marques:true,vrai:D.vrai,titre:'Valence, zoom',etiquettes:true});
const g=document.getElementById('hormones');
D.panneaux.forEach(h=>{const col=4+D.hormones.indexOf(h);const b=document.createElement('div');
  b.innerHTML=`<div style="font-weight:600;margin-top:8px">${D.noms[h]}</div>`;g.appendChild(b);
  const vs=[].concat(...D.variantes.map(([k])=>D.series[k].filter(r=>r[0]>=D.zoom[0]&&r[0]<=D.zoom[1]).map(r=>r[col])));
  const lo=Math.max(0,Math.floor(Math.min(...vs,D.bases[h])*20)/20), hi=Math.min(1,Math.ceil(Math.max(...vs,D.bases[h])*20)/20);
  trace(b,{t0:D.zoom[0],t1:D.zoom[1],col,h:170,largeur:520,ymin:lo,ymax:hi===lo?lo+.05:hi,base:D.bases[h],marques:true,titre:D.noms[h]})});
</script></body></html>"""

if __name__ == "__main__":
    main()
