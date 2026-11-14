#!/usr/bin/env python3
"""Fin de phrase de papa (14/11, Ahmed par Hakim : « quand on parle longtemps, il saute dans mes pauses et coupe ou répond à côté ;
qu'il laisse finir mes phrases longues »). Mesure EN LECTURE SEULE sur les vrais journaux, et rejeu de l'ancienne et de la nouvelle règle.

  python3 mesure/fin-de-phrase.py [JOUR mm-jj]      (défaut : aujourd'hui)

Sources (~/AIOS/jarvis, jamais écrites) :
  journal.jsonl         — ses messages et ceux de papa (horloge du Mac) : une suite collée au message d'avant = une fin de tour
                          prématurée (sa phrase continuait) ; « [coupé : Ahmed a repris la parole] » = sa réponse coupée ;
  voix-dite.jsonl       — ce que sa voix a vraiment dit : une réponse coupée a-t-elle sonné ?
  voix-diagnostic.jsonl — la page (horloge du téléphone) : fin_anticipee (silence, ce qu'il attendait), premier_mot (t - ms = début
                          d'un tour), tour_temps (attente de fin de tour, transcription) ;
  son-flux.jsonl        — le micro du téléphone à 100 ms (horloge du Mac), pour les blancs de papa.
"""
import bisect, collections, datetime, json, os, re, sys, unicodedata

J = os.path.expanduser('~/AIOS/jarvis')
JOUR = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime('%m-%d')
jour = lambda t: datetime.datetime.fromtimestamp(t / 1000).strftime('%m-%d')
hms = lambda t: datetime.datetime.fromtimestamp(t / 1000).strftime('%H:%M:%S')
norm = lambda s: re.sub(r'\s+', ' ', s or '').strip()
def lire(nom):
    out = []
    with open(os.path.join(J, nom), encoding='utf-8') as f:
        for l in f:
            try: out.append(json.loads(l))
            except ValueError: pass
    return out

# ---------- 1. journal : fins prématurées (suites collées) et réponses coupées, par jour ----------
JO = [o for o in lire('journal.jsonl') if o.get('qui') in ('ahmed', 'jarvis')]
par_jour = collections.defaultdict(collections.Counter)
prec = None; coupees_depuis = 0
for o in JO:
    d = jour(o['ts'])
    if o['qui'] == 'jarvis':
        if 'repris la parole' in o['texte']: par_jour[d]['coupees'] += 1; coupees_depuis += 1
        continue
    t = norm(o['texte']); par_jour[d]['messages_papa'] += 1
    if prec and t.startswith(norm(prec['texte'])) and len(t) > len(norm(prec['texte'])) and o['ts'] - prec['ts'] < 30000:
        par_jour[d]['suites_collees'] += 1; par_jour[d]['coupees_dans_une_suite'] += coupees_depuis
    prec = o; coupees_depuis = 0
print('1. Journal (horloge du Mac) — par jour : messages de papa, suites collées (fin de tour prématurée), réponses coupées')
for d in sorted(par_jour)[-7:]:
    c = par_jour[d]
    print(f'   {d} : {c["messages_papa"]:4d} messages · {c["suites_collees"]:3d} suites collées · {c["coupees"]:3d} réponses coupées'
          f' (dont {c["coupees_dans_une_suite"]} au milieu d\'une suite)')

# ---------- 2. réponses coupées : sa voix a-t-elle sonné ? ----------
def n(s):
    s = unicodedata.normalize('NFD', (s or '').lower()); s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()
VD = [v for v in lire('voix-dite.jsonl') if jour(v['t_ms']) == JOUR]
coupees = [o for o in JO if o['qui'] == 'jarvis' and jour(o['ts']) == JOUR and 'repris la parole' in o['texte']]
sonne = 0
for o in coupees:
    tete = ' '.join(n(re.sub(r'[⟮\[]{2}.*?[⟯\]]{2}', '', o['texte'].split('[coupé')[0])).split()[:4])
    if tete and any(o['ts'] - 3000 <= v['t_ms'] <= o['ts'] + 20000 and (n(v['texte']).startswith(tete[:12]) or (tete.startswith(n(v['texte'])[:12]) and len(n(v['texte'])) >= 6)) for v in VD):
        sonne += 1
print(f'\n2. {JOUR} : {len(coupees)} réponses coupées, dont {sonne} dont la voix a sonné (voix-dite), {len(coupees) - sonne} jamais entendues')

# ---------- 3. la page : fins anticipées, ce qu'il attendait, et le blanc de papa derrière ----------
P = sorted((o for o in lire('voix-diagnostic.jsonl') if jour(o['t']) == JOUR), key=lambda o: o['t'])
fins = [o for o in P if o['e'] == 'fin_anticipee']
att = collections.Counter((o.get('par'), o.get('attendu')) for o in fins)
sil = sorted(o['silence_ms'] for o in fins)
print(f'\n3. Page ({JOUR}, horloge du téléphone) : {len(fins)} fins de tour anticipées ; silence médian {sil[len(sil)//2] if sil else "-"} ms ;'
      f' par (chemin, attendu) : {dict(att)}')
debuts = sorted(o['t'] - o['ms'] + 380 for o in P if o['e'] == 'premier_mot')   # sa voix : début du tour + 0,5 s de préécoute - 0,12 s de tenue
AT = [o for o in JO if o['qui'] == 'ahmed']; ATT = [o['ts'] for o in AT]
lignes = []
for o in fins:
    L = o['t'] - o['silence_ms']; i = bisect.bisect_left(debuts, o['t'])
    if i == 0 or i >= len(debuts): continue
    D = L - debuts[i - 1]
    if not 0 <= D <= 120000: continue
    k = bisect.bisect_left(ATT, o['t'] + 500)
    colle = None
    if k < len(AT) and AT[k]['ts'] <= o['t'] + 8000:
        t, p = norm(AT[k]['texte']), norm(AT[k - 1]['texte']) if k else ''
        colle = bool(p and t.startswith(p) and AT[k]['ts'] - AT[k - 1]['ts'] < 30000)
    lignes.append({'t': o['t'], 'L': L, 'D': D, 'blanc': debuts[i] - L, 'colle': colle})
pre = [x for x in lignes if x['blanc'] < 3000]
B = [(0, 1000), (1000, 1500), (1500, 2000), (2000, 2500), (2500, 3000)]
print(f'   rejouées : {len(lignes)} ; papa a repris en moins de 3 s (fin prématurée) : {len(pre)} ; blanc de papa :',
      ' '.join(f'{a/1000:g}-{b/1000:g} s : {sum(1 for x in pre if a <= x["blanc"] < b)}' for a, b in B))

# ---------- 4. coût : la transcription part en avance à 0,5 s ; fermer le tour plus tard ne coûte que ce qui dépasse ----------
TT = [o for o in P if o['e'] == 'tour_temps' and o.get('transcription_ms', -1) >= 0]
print(f'\n4. Coût d\'une fermeture de tour plus tardive (tours répondus à voix : {len(TT)}) : max(0, T − attente − transcription)')
for T in (1000, 1200, 1500, 2000, 2500):
    c = sorted(max(0, T - x['attente_fin_tour_ms'] - x['transcription_ms']) for x in TT)
    if c: print(f'   T = {T/1000:g} s : moyen {sum(c)/len(c):.0f} ms, médian {c[len(c)//2]} ms, p90 {c[int(len(c)*0.9)]} ms, nul pour {100*sum(1 for v in c if v == 0)/len(c):.0f} %')
tot = sorted(x['total_ms'] for x in TT if x.get('total_ms', -1) >= 0)
if tot: print(f'   pour mémoire, de sa dernière voix au premier son de Hakim : médiane {tot[len(tot)//2]/1000:.1f} s (p10 {tot[len(tot)//10]/1000:.1f} s)')

# ---------- 5. rejeu de la règle (parler.js, plancherFinDeTour) sur ces fins anticipées ----------
# ANCIEN : ton tour se ferme à 0,5 s de silence. NOUVEAU : pareil pour ta parole courte ; 2 s si ta parole est longue (2 s de voix :
# ici sa durée depuis le début du tour, au moins 2,3 s, ses petits blancs compris) ou si tu reprenais ta phrase (moins de 4 s après ta
# dernière voix connue, ou une suite collée au message d'avant)
fins_connues = sorted(o['t'] - o['silence_ms'] for o in fins)
def reprise(x):
    debut = x['L'] - x['D']                                             # début de sa voix dans ce tour
    k = bisect.bisect_left(fins_connues, debut) - 1
    return k >= 0 and 0 < debut - fins_connues[k] < 4000
def plancher(x, LONG=2300, PL=2000):
    return PL if (x['D'] >= LONG or x['colle'] or reprise(x)) else 500
vraies = [x for x in lignes if x['blanc'] >= 3000]
ev = [x for x in pre if x['blanc'] < plancher(x)]
lg = sum(1 for x in vraies if plancher(x) == 2000)
print('\n5. Rejeu — ANCIEN : 0,5 s ; NOUVEAU : 0,5 s si ta parole est courte, 2 s si elle est longue (2 s de voix) ou si tu reprends ta phrase')
print(f'   fins prématurées évitées : {len(ev)} / {len(pre)} ; restent {len(pre) - len(ev)}')
print(f'   vraies fins (tu n\'as pas repris avant 3 s) : {lg} / {len(vraies)} attendent 2 s (coût : la ligne T = 2 s du point 4) ; {len(vraies) - lg} inchangées')
print('   restent prématurées (heure, ton blanc en s) :', [(hms(x['t']), round(x['blanc']/1000, 1)) for x in pre if x not in ev])
