"""La page d'enregistrement du test du ton (eval/ton_voix/criteres.md) : 24 extraits de la voix d'Ahmed, quatre tons ×
trois phrases × deux langues, dans un ordre mélangé une fois pour toutes. Le navigateur enregistre sans traitement (ni
gain automatique, ni réduction du bruit) et envoie un WAV ; il est gardé dans ~/AIOS/jarvis/bancs/ton-voix/clips/ jusqu'à
l'analyse. Seulement sur 127.0.0.1.

    jarvis/.venv/bin/python -B eval/ton_voix/etalonnage.py      → http://127.0.0.1:8791
"""
import json
import random
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 8791
BANC = Path.home() / "AIOS" / "jarvis" / "bancs" / "ton-voix"
CLIPS = BANC / "clips"
GRAINE = 27102026
MAX_OCTETS = 4 * 1024 * 1024

TONS = {
    "joyeux": "content, comme quand tu annonces une bonne nouvelle",
    "triste": "abattu, le cœur lourd",
    "tendu": "agacé ou inquiet, sur les nerfs",
    "pose": "calme, neutre, sans émotion particulière",
}
PHRASES = ["Je suis rentré à la maison ce soir.", "Il a appelé tout à l'heure.", "On se voit demain matin."]


def plan():
    items = [{"ton": t, "langue": l, "phrase": p} for t in TONS for l in ("fr", "darija") for p in range(len(PHRASES))]
    random.Random(GRAINE).shuffle(items)
    for i, x in enumerate(items):
        x["i"] = i
        x["fichier"] = f"{i:02d}-{x['ton']}-{x['langue']}-{x['phrase']}.wav"
    return items


def faits():
    return sorted(int(f.name[:2]) for f in CLIPS.glob("*.wav")) if CLIPS.exists() else []


PAGE = r"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Le ton de ta voix</title><style>
:root{--fond:#0f1115;--carte:#181b22;--texte:#e9ecf1;--doux:#9aa3b2;--accent:#7fb2ff;--rouge:#ff6b6b;--vert:#5fd38d}
body{margin:0;background:var(--fond);color:var(--texte);font:17px/1.5 -apple-system,system-ui,sans-serif;display:flex;justify-content:center}
main{max-width:640px;width:100%;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}.doux{color:var(--doux);font-size:15px}
.carte{background:var(--carte);border-radius:16px;padding:24px;margin:20px 0}
.ton{font-size:34px;font-weight:700;margin:6px 0}.desc{color:var(--doux)}
.phrase{font-size:22px;margin:18px 0 6px}
button{font:inherit;border:0;border-radius:12px;padding:12px 20px;margin:6px 8px 0 0;cursor:pointer;background:#2a2f3a;color:var(--texte)}
#rec{background:var(--accent);color:#0b1020;font-weight:700;min-width:180px}#rec.on{background:var(--rouge);color:#fff}
.barre{height:8px;background:#2a2f3a;border-radius:4px;overflow:hidden;margin-top:14px}.barre i{display:block;height:100%;width:0;background:var(--vert)}
#prog{height:4px;background:#2a2f3a;border-radius:2px;margin-top:10px}#prog i{display:block;height:100%;background:var(--accent);width:0}
#msg{min-height:1.5em;margin-top:10px}
</style></head><body><main>
<h1>Le ton de ta voix</h1>
<div class="doux">24 petits extraits, environ 5 minutes. Mets d'abord Hakim sur pause (⏸), sinon il va te répondre. Barre d'espace = enregistrer / arrêter.</div>
<div id="prog"><i></i></div>
<div class="carte" id="carte"></div>
<div id="msg" class="doux"></div>
</main><script>
const PLAN = __PLAN__, PHRASES = __PHRASES__, TONS = __TONS__, NOMS = {joyeux:'Joyeux', triste:'Triste', tendu:'Tendu', pose:'Posé'};
let faits = new Set(__FAITS__), i = PLAN.findIndex(x => !faits.has(x.i)); if (i < 0) i = PLAN.length;
let ctx, src, proc, flux, morceaux = [], enr = false, debut = 0, minuteur;
const $ = s => document.querySelector(s);
function rendre() {
  $('#prog i').style.width = (100 * faits.size / PLAN.length) + '%';
  if (i >= PLAN.length) { $('#carte').innerHTML = '<div class="ton">C’est fini, merci !</div><div class="desc">Dis-le à Claude Code : il lance l’analyse.</div>'; return; }
  const x = PLAN[i], p = PHRASES[x.phrase];
  $('#carte').innerHTML = `<div class="doux">Extrait ${i + 1} / ${PLAN.length}</div>
    <div class="ton">${NOMS[x.ton]}</div><div class="desc">${TONS[x.ton]}</div>
    <div class="phrase">${x.langue === 'fr' ? '« ' + p + ' »' : 'En darija, avec tes mots : <span class="doux">« ' + p + ' »</span>'}</div>
    <button id="rec">● Enregistrer</button>${faits.has(x.i) ? '<button id="suiv">Suivant →</button>' : ''}
    ${i > 0 ? '<button id="prec">← Précédent</button>' : ''}<div class="barre"><i id="niv"></i></div>`;
  $('#rec').onclick = basculer;
  if ($('#suiv')) $('#suiv').onclick = () => { i++; $('#msg').textContent = ''; rendre(); };
  if ($('#prec')) $('#prec').onclick = () => { i--; $('#msg').textContent = ''; rendre(); };
}
async function ouvrir() {
  if (ctx) return;
  flux = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 } });
  ctx = new AudioContext(); src = ctx.createMediaStreamSource(flux);
  proc = ctx.createScriptProcessor(4096, 1, 1);
  proc.onaudioprocess = e => {
    const d = e.inputBuffer.getChannelData(0); let s = 0; for (const v of d) s += v * v;
    const niv = $('#niv'); if (niv) niv.style.width = Math.min(100, Math.sqrt(s / d.length) * 400) + '%';
    if (enr) morceaux.push(new Float32Array(d));
  };
  src.connect(proc); proc.connect(ctx.destination);
}
async function basculer() {
  if (i >= PLAN.length) return;
  if (!enr) {
    try { await ouvrir(); } catch (e) { $('#msg').textContent = 'Micro refusé : ' + e.message; return; }
    await ctx.resume(); morceaux = []; enr = true; debut = Date.now();
    $('#rec').textContent = '■ Arrêter'; $('#rec').classList.add('on'); $('#msg').textContent = 'J’écoute…';
    minuteur = setTimeout(basculer, 10000);
  } else {
    enr = false; clearTimeout(minuteur);
    const duree = (Date.now() - debut) / 1000;
    $('#rec').textContent = '● Enregistrer'; $('#rec').classList.remove('on');
    if (duree < 0.8) { $('#msg').textContent = 'Trop court, recommence.'; return; }
    $('#msg').textContent = 'J’envoie…';
    const x = PLAN[i], r = await fetch('/clip/' + x.i, { method: 'POST', body: wav(morceaux, ctx.sampleRate) });
    const o = await r.json();
    if (!r.ok) { $('#msg').textContent = 'Erreur : ' + (o.erreur || r.status); return; }
    faits.add(x.i); $('#msg').textContent = `✓ gardé (${duree.toFixed(1).replace('.', ',')} s). Tu peux le refaire, ou passer au suivant.`;
    rendre();
  }
}
function wav(chunks, taux) {
  const n = chunks.reduce((a, c) => a + c.length, 0), b = new ArrayBuffer(44 + 2 * n), v = new DataView(b);
  const ecr = (o, s) => { for (let k = 0; k < s.length; k++) v.setUint8(o + k, s.charCodeAt(k)); };
  ecr(0, 'RIFF'); v.setUint32(4, 36 + 2 * n, true); ecr(8, 'WAVE'); ecr(12, 'fmt '); v.setUint32(16, 16, true);
  v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, taux, true); v.setUint32(28, taux * 2, true);
  v.setUint16(32, 2, true); v.setUint16(34, 16, true); ecr(36, 'data'); v.setUint32(40, 2 * n, true);
  let o = 44; for (const c of chunks) for (const s of c) { v.setInt16(o, Math.max(-1, Math.min(1, s)) * 0x7fff, true); o += 2; }
  return new Blob([b], { type: 'audio/wav' });
}
document.addEventListener('keydown', e => { if (e.code === 'Space') { e.preventDefault(); basculer(); } });
rendre();
</script></body></html>"""


class Page(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, o):
        corps = json.dumps(o, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):
        if self.path != "/":
            return self._json(404, {"erreur": "inconnu"})
        corps = (PAGE.replace("__PLAN__", json.dumps(plan(), ensure_ascii=False))
                 .replace("__PHRASES__", json.dumps(PHRASES, ensure_ascii=False))
                 .replace("__TONS__", json.dumps(TONS, ensure_ascii=False))
                 .replace("__FAITS__", json.dumps(faits()))).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corps)

    def do_POST(self):
        m = re.fullmatch(r"/clip/(\d{1,2})", self.path)
        items = plan()
        if not m or int(m.group(1)) >= len(items):
            return self._json(404, {"erreur": "extrait inconnu"})
        n = int(self.headers.get("Content-Length") or 0)
        if not 44 < n <= MAX_OCTETS:
            return self._json(413, {"erreur": "taille"})
        corps = self.rfile.read(n)
        if corps[:4] != b"RIFF" or corps[8:12] != b"WAVE":
            return self._json(400, {"erreur": "pas un WAV"})
        CLIPS.mkdir(parents=True, exist_ok=True)
        (CLIPS / items[int(m.group(1))]["fichier"]).write_bytes(corps)      # une prise refaite remplace l'ancienne
        return self._json(200, {"ok": True, "faits": len(faits())})


if __name__ == "__main__":
    BANC.mkdir(parents=True, exist_ok=True)
    (BANC / "plan.json").write_text(json.dumps(plan(), ensure_ascii=False, indent=1))
    print(f"http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Page).serve_forever()
