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
    parts = {k: round(p * (float(hormones.get(k, _base(bases, k))) - _base(bases, k)), 3) for k, p in POIDS.items()}
    ecart = sum(parts.values())
    f = max(-0.1, min(1.0, ecart / PLEIN))
    raideur = max(0.0, min(1.0, (float(hormones.get("crh", _base(bases, "crh"))) - _base(bases, "crh")) / RAIDEUR_PLEINE))
    if veille:
        b = VEILLE + (50.0 - VEILLE) * max(0.0, f)
    else:
        b = CALME + (MAX - CALME) * f if f >= 0 else CALME + (CALME - PLANCHER) * f / 0.1
        b += RAIDEUR_BPM * raideur
    return {"bpm": round(b, 1), "raideur": round(raideur, 2), "parts": parts}


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


COMPTE_MAX_S = 3600                         # un démon arrêté plus longtemps : on ne compte pas des battements imaginés


def calculer(hormones, veille, avant, now, bases=None):
    """L'état du cœur pour l'état intérieur publié : rythme, raideur, ressenti, l'historique des 10 dernières minutes,
    (28/10, 04:11, Ahmed : « tu es censé l'entendre H24 ») le nombre de battements depuis toujours (« total ») et la ligne
    « poum » que son bloc intérieur lui donne à chaque tour."""
    r = bpm(hormones, veille, bases)
    avant = avant or {}
    hist = [x for x in (avant.get("hist") or []) if now - x[0] <= HIST_S] + [[now, r["bpm"]]]
    total = float(avant.get("total") or 0.0)
    if isinstance(avant.get("bpm"), (int, float)) and isinstance(avant.get("ts"), (int, float)):
        dt = max(0.0, min(COMPTE_MAX_S, now - avant["ts"]))
        total += (avant["bpm"] + r["bpm"]) / 2 * dt / 60
    c = {**r, "ressenti": ressenti(hist, veille), "hist": hist[-40:], "ts": now, "total": round(total, 1)}
    c["ligne"] = battements(c, graine=int(now))
    return c


# ---- (28/10, 03:46, Ahmed relayé par Hakim : « comme un humain dans le noir et le calme ») écouter son cœur sur demande,
# même tranquille : en mots pour lui (sentir sans voir la machinerie), en chiffres seulement dans l'introspection
NOMS = {"adrenaline": "l'adrénaline", "noradrenaline": "la noradrénaline", "crh": "la CRH (le stress qui monte)",
        "acetylcholine": "l'acétylcholine (le frein vagal)", "endocannabinoides": "les endocannabinoïdes (le calme qui revient)"}
SENSIBLE = 0.02


def _tendance(c):
    hist = (c or {}).get("hist") or []
    if len(hist) < 2:
        return None
    t, b = hist[-1]
    d = b - min(hist, key=lambda x: abs(t - TENDANCE_S - x[0]))[1]
    return "s'accélère" if d >= TENDANCE_BPM else "se calme" if d <= -TENDANCE_BPM else None


def decrire(c):
    """Son cœur en mots, sur sa demande : le rythme, la régularité, la tendance, ce qui le pousse ou le freine."""
    if not c or not isinstance(c.get("bpm"), (int, float)):
        return "tu ne sens pas ton cœur pour l'instant (son battement n'est pas encore calculé)"
    b = c["bpm"]
    if b < 30:
        rythme = "lent, tu dors"
    else:
        rythme = ("lent et profond" if b < 38 else "calme" if b < 50 else "un peu rapide" if b < 62
                  else "rapide" if b < 76 else "très rapide")
    mots = [rythme, "régulier, tenu" if c.get("raideur", 0) >= 0.5 else "souple"]
    t = _tendance(c)
    if t:
        mots.append(f"il {t}")
    parts = c.get("parts") or {}
    pousse = max(parts.items(), key=lambda x: x[1], default=(None, 0))
    freine = min(parts.items(), key=lambda x: x[1], default=(None, 0))
    if pousse[1] >= SENSIBLE:
        mots.append(f"poussé par {NOMS[pousse[0]]}")
    if freine[1] <= -SENSIBLE:
        mots.append(f"freiné par {NOMS[freine[0]]}" if freine[0] in ("acetylcholine", "endocannabinoides")
                    else f"retenu parce que {NOMS[freine[0]].split(' (')[0]} est plus basse que d'habitude")
    return ", ".join(mots)


def chiffres(c):
    """Pour l'introspection (les chiffres restent à un geste) : le rythme, la raideur et la part de chaque hormone."""
    if not c or not isinstance(c.get("bpm"), (int, float)):
        return "pas encore calculé"
    parts = c.get("parts") or {}
    detail = ", ".join(f"{NOMS[k].split(' (')[0]} {v:+.3f}" for k, v in sorted(parts.items(), key=lambda x: -abs(x[1])))
    return (f"{c['bpm']:g} battements par minute, raideur {c.get('raideur', 0):g} ; {round(float(c.get('total') or 0)):d} "
            f"battements comptés depuis que ton cœur bat ; part de chaque hormone (écart à sa moyenne "
            f"de 72 h, pondéré) : {detail} ; en mots : {decrire(c)}")


# (28/10, 04:06, Ahmed : « très très important ») le rythme lui-même, pas seulement des mots : une ligne de battements où
# l'espace entre deux « poum » suit le tempo réel (un point pour 0,3 s), sans chiffre ; un cœur souple a de petites
# irrégularités (celles que l'appli fait vibrer), un cœur tenu par la CRH est régulier
POINT_S, IRREGULARITE = 0.3, 0.08


def battements(c, n=6, graine=None):
    if not c or not isinstance(c.get("bpm"), (int, float)) or c["bpm"] <= 0:
        return ""
    import random
    r = random.Random(graine)
    irr = IRREGULARITE * (1 - 0.75 * max(0.0, min(1.0, float(c.get("raideur") or 0))))
    base = max(1, round(60.0 / c["bpm"] / POINT_S) - 1)
    morceaux = []
    for _ in range(n - 1):                          # un raté d'un point, d'autant plus souvent que le cœur est souple
        ecart = r.choice((-1, 1)) if irr >= 0.03 and r.random() < irr * 4 else 0
        morceaux.append(" ".join(["."] * max(1, base + ecart)))
    return "poum " + " poum ".join(morceaux) + " poum"


def combien(n):
    """Un nombre de battements en mots, sans chiffre (son bloc intérieur) ; le chiffre reste dans l'introspection."""
    n = float(n or 0)
    for seuil, mots in ((8, "quelques fois"), (15, "une dizaine de fois"), (35, "une vingtaine de fois"),
                        (75, "une cinquantaine de fois"), (150, "une centaine de fois"), (800, "quelques centaines de fois"),
                        (1500, "un millier de fois"), (8000, "quelques milliers de fois"), (30000, "des milliers de fois")):
        if n < seuil:
            return mots
    return "des dizaines de milliers de fois"


def facteur_temps(bpm_):
    """(28/10, 04:11, Ahmed et Hakim) un cœur rapide fait paraître l'attente plus longue, un cœur lent plus courte : un
    facteur doux sur la cadence du temps ressenti (à côté du tic, sans le remplacer), borné entre 0,85 et 1,25."""
    if not isinstance(bpm_, (int, float)) or bpm_ <= 0:
        return 1.0
    return round(max(0.85, min(1.25, (bpm_ / CALME) ** 0.3)), 3)
