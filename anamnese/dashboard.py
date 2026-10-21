"""dashboard.py — interface web locale pour VISUALISER l'esprit d'Anamnèse.

Affiche en direct : humeur (neuromodulateurs), identité, mémoire (+ recherche),
et les réflexions / pensées internes / métacognition.
Serveur stdlib (zéro dépendance web). Lancer : python dashboard.py → http://localhost:8765
"""
import hmac
import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import memory
import affect
import embeddings

PORT = 8765
# (audit JARVIS 2, M3, 2026-10-20) Une page web piégée pouvait lire la mémoire par rebond DNS (son domaine pointé sur
# 127.0.0.1) : seuls les en-têtes Host de cette machine passent, et l'API exige le jeton de la page (tiré au démarrage).
HOTES = {f"localhost:{PORT}", f"127.0.0.1:{PORT}", f"[::1]:{PORT}"}
JETON = secrets.token_hex(16)


def state_json():
    m = memory.Memory()
    s = affect.get_state(m)
    v, a = affect.valence_arousal(s)
    refl = m.db.execute(
        "SELECT ts, role, content FROM episodes "
        "WHERE role IN ('reflection','outreach','thought','reasoning') ORDER BY ts DESC LIMIT 15"
    ).fetchall()
    mems = m.db.execute(
        "SELECT ts, role, content, importance FROM episodes "
        "WHERE role IN ('semantic','episodic','user','assistant') ORDER BY ts DESC LIMIT 40"
    ).fetchall()
    dreams = m.db.execute(
        "SELECT ts, content FROM episodes WHERE role='dream' ORDER BY ts DESC LIMIT 20"
    ).fetchall()
    ld = m.kv_get("last_dream")
    return {
        "mood": affect.describe(m), "valence": v, "arousal": a,
        "hormones": s, "identity": m.kv_get("self_model", "(auto-modèle vide)"),
        "count": m.db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0],
        "reflections": [{"ts": ts, "role": r, "content": c} for ts, r, c in refl],
        "memories": [{"ts": ts, "role": r, "content": c, "imp": imp} for ts, r, c, imp in mems],
        "dreams": [{"ts": ts, "content": c} for ts, c in dreams],
        "dream_count": int(m.kv_get("dream_count", "0") or 0),
        "last_dream": float(ld) if ld else None,
        "self_prev": m.kv_get("self_model_prev"),
    }


def search_json(q):
    m = memory.Memory()
    res = m.retrieve(q, embeddings.embed(q), top_k=12)
    return [{"imp": round(sc, 2), "role": role, "content": content, "ts": ts}
            for sc, ts, role, content, _p in res]


PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Anamnèse — esprit</title><style>
:root{color-scheme:dark}
body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#0b0f17;color:#e5e7eb}
header{padding:18px 24px;border-bottom:1px solid #1f2937}
h1{margin:0;font-size:19px}.muted{color:#9ca3af;font-size:13px}
.mood{font-size:16px;margin-top:6px;color:#a7f3d0}
.wrap{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px 24px}
.card{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:16px}
.card h2{margin:0 0 12px;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:#9ca3af}
.row{display:flex;justify-content:space-between;font-size:13px}
.bar{height:9px;border-radius:6px;background:#1f2937;overflow:hidden;margin:3px 0 10px}
.bar>i{display:block;height:100%}
.mem{border-top:1px solid #1f2937;padding:8px 0;font-size:13px;line-height:1.4}
.mem small{color:#6b7280}
.tag{font-size:11px;padding:1px 6px;border-radius:5px;background:#1f2937;color:#9ca3af;margin-right:6px}
input{width:100%;padding:9px;background:#0b0f17;border:1px solid #374151;border-radius:8px;color:#e5e7eb;margin-bottom:10px;box-sizing:border-box}
.full{grid-column:1/3}#identity{white-space:pre-wrap;font-size:13px;line-height:1.5}
</style></head><body>
<header><h1>🧠 Anamnèse — son esprit, en direct</h1>
<div class="mood" id="mood">…</div><div class="muted" id="count"></div></header>
<div class="wrap">
<div class="card"><h2>💗 Humeur — neuromodulateurs</h2><div id="hormones"></div></div>
<div class="card"><h2>🪞 Identité (auto-modèle)</h2><div id="identity" class="muted"></div></div>
<div class="card full"><h2>🔍 Métacognition & pensées internes</h2><div id="refl"></div></div>
<div class="card full"><h2>🌙 Rêve & sommeil <span class="muted" id="dreammeta" style="text-transform:none;letter-spacing:0"></span></h2><div id="dreams"></div></div>
<div class="card full"><h2>📚 Mémoire</h2><input id="q" placeholder="rechercher dans la mémoire…"><div id="mem"></div></div>
</div><script>
const C={dopamine:'#4ade80',serotonine:'#60a5fa',noradrenaline:'#fb923c',cortisol:'#f87171',ocytocine:'#f472b6',acetylcholine:'#c084fc',endorphine:'#fcd34d'};
const when=t=>new Date(t*1000).toLocaleString('fr-FR');
const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const dreamIcon=c=>(c||'').startsWith('(rêve)')?'💭':(c||'').startsWith('(identité)')?'🪞':(c||'').startsWith('(sommeil)')?'💤':'🌙';
function mem(items){document.getElementById('mem').innerHTML=items.map(m=>
 `<div class="mem"><span class="tag">${m.role}</span>${esc(m.content)} <small>· ${m.imp!=null?m.imp:''} · ${when(m.ts)}</small></div>`).join('')||'<div class="muted">(rien)</div>';}
const J={headers:{'X-Jeton':document.querySelector('meta[name=jeton]').content}};
async function refresh(){const s=await(await fetch('/api/state',J)).json();
 document.getElementById('mood').textContent='Humeur : '+s.mood;
 document.getElementById('count').textContent=s.count+' souvenirs · valence '+s.valence.toFixed(2)+' · arousal '+s.arousal.toFixed(2);
 document.getElementById('identity').textContent=s.identity;
 document.getElementById('hormones').innerHTML=Object.entries(s.hormones).map(([k,v])=>
  `<div class="row"><span>${k}</span><span>${v.toFixed(2)}</span></div><div class="bar"><i style="width:${v*100}%;background:${C[k]||'#888'}"></i></div>`).join('');
 document.getElementById('refl').innerHTML=s.reflections.length?s.reflections.map(r=>
  `<div class="mem"><span class="tag">${r.role}</span>${esc(r.content)}<br><small>${when(r.ts)}</small></div>`).join(''):'<div class="muted">(aucune réflexion encore — lance le daemon)</div>';
 document.getElementById('dreammeta').textContent=' · '+s.dream_count+' rêve(s) · dernier sommeil : '+(s.last_dream?when(s.last_dream):'jamais')+(s.self_prev?' · identité réversible ✓':'');
 document.getElementById('dreams').innerHTML=s.dreams.length?s.dreams.map(d=>
  `<div class="mem">${dreamIcon(d.content)} ${esc(d.content)} <small>· ${when(d.ts)}</small></div>`).join(''):'<div class="muted">(aucun rêve encore — il rêve après une longue inactivité, ou au moins 1×/24h)</div>';
 mem(s.memories.map(m=>({imp:m.imp,role:m.role,content:m.content,ts:m.ts})));}
let t;document.getElementById('q').addEventListener('input',e=>{clearTimeout(t);const q=e.target.value;
 t=setTimeout(async()=>{if(!q){refresh();return}mem(await(await fetch('/api/search?q='+encodeURIComponent(q),J)).json());},300);});
refresh();setInterval(refresh,5000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else body.encode("utf-8"))

    def do_GET(self):
        u = urlparse(self.path)
        if self.headers.get("Host", "") not in HOTES:
            return self._send(403, "text/plain; charset=utf-8", "Host refusé : tableau de bord réservé à cette machine")
        if u.path.startswith("/api/") and not hmac.compare_digest(self.headers.get("X-Jeton", ""), JETON):
            return self._send(403, "text/plain; charset=utf-8", "jeton absent ou faux")
        if u.path == "/":
            self._send(200, "text/html; charset=utf-8", PAGE.replace("<head>", f'<head><meta name="jeton" content="{JETON}">', 1))
        elif u.path == "/api/state":
            self._send(200, "application/json", json.dumps(state_json()))
        elif u.path == "/api/search":
            q = parse_qs(u.query).get("q", [""])[0]
            self._send(200, "application/json", json.dumps(search_json(q) if q else []))
        else:
            self._send(404, "text/plain", "not found")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"Anamnèse dashboard → http://localhost:{PORT}  (Ctrl-C pour arrêter)")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
