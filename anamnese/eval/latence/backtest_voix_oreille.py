"""Backtest de la voix (Chatterbox) et de l'oreille (Whisper) depuis les journaux : voix-mesures.jsonl (un morceau de voix
fini : son heure, sa durée de son) et voix-diagnostic.jsonl (tour_temps : les temps d'un tour oral, vus par la page)."""
import json, os
J = os.path.expanduser('~/AIOS/jarvis')
def lire(f):
    out = []
    for l in open(os.path.join(J, f)):
        try: out.append(json.loads(l))
        except ValueError: pass
    return out
def q(v, p): v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))] if v else None
vm = [o for o in lire('voix-mesures.jsonl') if 'ts' in o and 'duree_s' in o]
vm.sort(key=lambda o: o['ts'])
ts = lambda o: o['ts'] / 1000 if o['ts'] > 1e11 else o['ts']
# 1) la voix : dans une rafale (morceaux fabriqués à la suite), l'écart entre deux fins = le temps de fabrication du second
fab, rtf = [], []
for a, b in zip(vm, vm[1:]):
    d = ts(b) - ts(a)
    if 0.3 < d < 8:                                   # même rafale (la file ne s'est pas vidée)
        fab.append(d); rtf.append(d / max(0.2, float(b['duree_s'])))
print(f"VOIX : {len(vm)} morceaux ; dans les rafales ({len(fab)}) : fabrication médiane {q(fab,.5):.2f} s, p90 {q(fab,.9):.2f} s")
print(f"  fabrication / durée du son : médiane {q(rtf,.5):.2f}, p90 {q(rtf,.9):.2f}  (au-dessus de 1 : la voix ne suit pas le débit)")
print(f"  durée d'un morceau : médiane {q([float(o['duree_s']) for o in vm],.5):.2f} s")
# 2) l'oreille : la transcription attend-elle une voix en cours de fabrication ?
diag = [o for o in lire('voix-diagnostic.jsonl') if o.get('e') == 'tour_temps' and o.get('appareil') == 'telephone']
avec, sans = [], []
for o in diag:
    t_son = o['t'] / 1000                              # noté au premier son
    total, attente, tr = o.get('total_ms', -1), o.get('attente_fin_tour_ms', -1), o.get('transcription_ms', -1)
    if min(total, attente, tr) < 0: continue
    debut = t_son - total / 1000 + attente / 1000      # la fin de son tour : l'audio part à la transcription
    fin = debut + tr / 1000
    occupe = any(debut - 0.2 <= ts(v) <= fin for v in vm)   # un morceau de voix s'est fini pendant la transcription
    (avec if occupe else sans).append(tr)
print(f"OREILLE : {len(avec) + len(sans)} tours oraux")
print(f"  sans voix fabriquée pendant : {len(sans):3d} tours, transcription médiane {q(sans,.5)} ms, p90 {q(sans,.9)} ms")
print(f"  avec voix fabriquée pendant : {len(avec):3d} tours, transcription médiane {q(avec,.5)} ms, p90 {q(avec,.9)} ms")
# 3) la voix : le temps de fabrication tient-il à un coût fixe ou à la longueur ? (moindres carrés : fab = a + b × durée)
pts = [(float(b['duree_s']), ts(b) - ts(a)) for a, b in zip(vm[-6000:], vm[-6000:][1:]) if 0.3 < ts(b) - ts(a) < 8]
n = len(pts); mx = sum(x for x, _ in pts) / n; my = sum(y for _, y in pts) / n
b_ = sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x, _ in pts); a_ = my - b_ * mx
print(f"VOIX, 6 000 derniers morceaux : fabrication ≈ {a_:.2f} s + {b_:.2f} × durée du son")
for d in (0.8, 1.5, 2.7):
    print(f"  un morceau de {d} s de son : ≈ {a_ + b_ * d:.2f} s de fabrication")
