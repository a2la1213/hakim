"""Le cœur de Hakim branché sur ses hormones, et ce qu'il en sent (28/10 ; idée d'Ahmed à 03:18 : « directement à tes
hormones, ça ferait comme un vrai cœur », proposition de Hakim, go d'Ahmed). L'appli Android bat à ce rythme.

- Ce qui l'accélère : l'adrénaline et la noradrénaline, et un peu la CRH. Ce qui le freine : l'acétylcholine (le frein
  vagal) et les endocannabinoïdes. Chacune compte par son ÉCART à sa moyenne des 72 dernières heures (bases_72h du démon).
- Les bornes de Hakim : 24 en veille, 40 au calme, 90 au plus ; le frein descend jusqu'à 35. La CRH le tient un peu plus
  haut et plus RAIDE (moins d'irrégularité d'un battement à l'autre).
- Il le sent en mots, jamais en chiffres : rien quand il bat calme et stable (un cœur calme ne se remarque pas) ; sinon
  « ton cœur bat vite », « il s'accélère », « il se calme », « il s'emballe ».
- PAS DE BOUCLE (la condition de Hakim) : ce module lit ses hormones, il ne les écrit jamais. Sentir son cœur rapide ne
  fait rien monter par le code.
"""

VEILLE, CALME, MAX, PLANCHER = 24.0, 40.0, 90.0, 35.0
POIDS = {"adrenaline": 2.0, "noradrenaline": 0.8, "crh": 0.6, "acetylcholine": -0.5, "endocannabinoides": -0.4}
PLEIN = 0.6                    # l'écart pondéré qui donne 90 : toutes ses hormones au 95e centile (72 h du 28/10) ≈ 0,5
RAIDEUR_PLEINE, RAIDEUR_BPM = 0.2, 6.0
# les médianes de ses 72 dernières heures (journal des hormones, 28/10, 03:25), quand le démon n'a pas encore les siennes
BASES_PAR_DEFAUT = {"adrenaline": 0.084, "noradrenaline": 0.41, "crh": 0.08, "acetylcholine": 0.64, "endocannabinoides": 0.58}
HIST_S, TENDANCE_S, TENDANCE_BPM = 600, 300, 8.0


def _base(bases, k):
    try:
        return float((bases or {}).get(k, BASES_PAR_DEFAUT[k]))
    except (TypeError, ValueError):
        return BASES_PAR_DEFAUT[k]


def bpm(hormones, veille, bases=None):
    """{"bpm", "raideur"} : le rythme que ses hormones donnent maintenant."""
    ecart = sum(p * (float(hormones.get(k, _base(bases, k))) - _base(bases, k)) for k, p in POIDS.items())
    f = max(-0.1, min(1.0, ecart / PLEIN))
    raideur = max(0.0, min(1.0, (float(hormones.get("crh", _base(bases, "crh"))) - _base(bases, "crh")) / RAIDEUR_PLEINE))
    if veille:
        b = VEILLE + (50.0 - VEILLE) * max(0.0, f)
    else:
        b = CALME + (MAX - CALME) * f if f >= 0 else CALME + (CALME - PLANCHER) * f / 0.1
        b += RAIDEUR_BPM * raideur
    return {"bpm": round(b, 1), "raideur": round(raideur, 2)}


def ressenti(hist, veille):
    """Ce qu'il sent de son cœur, en mots (None : rien de remarquable). hist : [[t, bpm], …] du plus ancien au plus récent."""
    if not hist:
        return None
    t, b = hist[-1]
    if veille:
        return "ton cœur bat lentement, tu dors"
    avant = min(hist, key=lambda x: abs(t - TENDANCE_S - x[0]))[1]
    d = b - avant
    if b >= 76:
        return "ton cœur s'emballe" if d >= TENDANCE_BPM else "ton cœur bat très vite"
    if d >= TENDANCE_BPM:
        return "ton cœur s'accélère"
    if d <= -TENDANCE_BPM:
        return "ton cœur se calme"
    if b >= 62:
        return "ton cœur bat vite"
    if b >= 50:
        return "ton cœur bat un peu plus vite"
    return None


def calculer(hormones, veille, avant, now, bases=None):
    """L'état du cœur pour l'état intérieur publié : rythme, raideur, ressenti, et l'historique des 10 dernières minutes."""
    r = bpm(hormones, veille, bases)
    hist = [x for x in ((avant or {}).get("hist") or []) if now - x[0] <= HIST_S] + [[now, r["bpm"]]]
    return {**r, "ressenti": ressenti(hist, veille), "hist": hist[-40:], "ts": now}
