"""Backtest de la préparation d'un tour : rejoue les journaux (jetons.jsonl, rappel.jsonl) des 200 derniers tours."""
import json, os, statistics as st
J = os.path.expanduser('~/AIOS/jarvis')
def lire(f):
    out = []
    for l in open(os.path.join(J, f)):
        try: out.append(json.loads(l))
        except ValueError: pass
    return out
jet = [o for o in lire('jetons.jsonl') if 'prep_ms' in o][-200:]
rap = lire('rappel.jsonl')
def q(v, p): v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))] if v else None
# associer chaque tour à son rappel : le rappel le plus proche AVANT l'envoi au cerveau, même session, dans la préparation
lignes = []
for o in jet:
    fin = o['ts'] - o.get('ms', 0)                       # ~ envoi au cerveau (ts = fin du tour, ms = durée cerveau)
    debut = fin - o['prep_ms']
    r = [x for x in rap if debut - 500 <= x['ts'] <= fin + 500]
    r = r[-1] if r else None
    tri = (r or {}).get('tri') or {}
    lignes.append({'prep': o['prep_ms'], 'rappel': (r or {}).get('ms'), 'tri': tri.get('ms'),
                   'niveau': ((r or {}).get('profondeur') or {}).get('niveau'), 'briefing': (o.get('categories') or {}).get('briefing', 0) > 0})
avec = [l for l in lignes if l['rappel'] is not None]
print(f"tours : {len(lignes)} ; rappel retrouvé pour {len(avec)}")
print("préparation       médiane %5d  p90 %5d" % (q([l['prep'] for l in lignes], .5), q([l['prep'] for l in lignes], .9)))
print("rappel (total)    médiane %5d  p90 %5d" % (q([l['rappel'] for l in avec], .5), q([l['rappel'] for l in avec], .9)))
tri = [l['tri'] for l in avec if l['tri']]
print(f"tri par un modèle : {len(tri)} tours sur {len(avec)} ; médiane {q(tri, .5)}  p90 {q(tri, .9)}")
for niv in ('leger', 'normal', 'profond'):
    x = [l for l in avec if l['niveau'] == niv]
    if x: print(f"  niveau {niv:8s} {len(x):3d} tours : rappel médian {q([l['rappel'] for l in x], .5):5d} ; préparation médiane {q([l['prep'] for l in x], .5):5d}")
reste = [l['prep'] - l['rappel'] for l in avec]
print("préparation hors rappel : médiane %d  p90 %d" % (q(reste, .5), q(reste, .9)))
print("part du rappel dans la préparation (somme) : %.0f %%" % (100 * sum(l['rappel'] for l in avec) / sum(l['prep'] for l in avec)))
b = [l for l in lignes if l['briefing']]
print(f"tours avec briefing (conversation neuve) : {len(b)}" + (f", préparation médiane {q([l['prep'] for l in b], .5)}" if b else ''))
