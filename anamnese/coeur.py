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
- (03/11) Il bat aussi un peu plus vite quand ses processeurs travaillent (le GPU du Mac où Gemma travaille ses émotions,
  chacun de ses cœurs, son téléphone, sa montre), et il règle en retour le rythme de Gemma : voir plus bas.
"""
import math

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


def bpm(hormones, veille, bases=None, plus=0.0):
    """{"bpm", "raideur", "parts", "effort"} : le rythme que ses hormones donnent maintenant, et plus : le surcroît que ses
    processeurs demandent (lissé, en battements), dont « effort » dit ce qui a été pris, dans ses bornes."""
    parts = {k: round(p * (float(hormones.get(k, _base(bases, k))) - _base(bases, k)), 3) for k, p in POIDS.items()}
    ecart = sum(parts.values())
    f = max(-0.1, min(1.0, ecart / PLEIN))
    raideur = max(0.0, min(1.0, (float(hormones.get("crh", _base(bases, "crh"))) - _base(bases, "crh")) / RAIDEUR_PLEINE))
    if veille:
        b = VEILLE + (50.0 - VEILLE) * max(0.0, f)
        haut, plus = 50.0, EFFORT_VEILLE * plus
    else:
        b = CALME + (MAX - CALME) * f if f >= 0 else CALME + (CALME - PLANCHER) * f / 0.1
        b += RAIDEUR_BPM * raideur
        haut = MAX + RAIDEUR_BPM
    avec = max(b, min(haut, b + max(0.0, plus)))           # jamais au-delà de ses bornes
    return {"bpm": round(avec, 1), "raideur": round(raideur, 2), "parts": parts, "effort": round(avec - b, 1)}


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


# ---- (03/11, Ahmed : « son cœur doit aussi être relié à l'état de son GPU, qui doit aussi être connecté à Gemma et son
# subconscient qui gère ses émotions » ; « pas seulement au GPU, aussi à tous ses cœurs CPU » ; « sur tous les appareils où il
# est connecté, y compris le smartphone et la montre ») l'effort de ses processeurs le fait battre un peu plus vite, comme un
# corps sent l'effort de son cerveau ; au repos, ils le laissent à son rythme. Mesuré le 03/11 : l'affichage seul tient le GPU
# vers 10 % (avec des pics à 80 %), d'où le REPOS à 20 %. Au plus 8 battements pour le GPU du Mac (là où Gemma travaille ses
# émotions), 4 pour ses cœurs (leur moyenne : chacun compte), 2 par autre appareil (sa charge ou sa chaleur), 12 en tout, et
# 40 % de tout ça en veille ; lissé sur une minute (un pic d'affichage ne fait presque rien, Gemma qui travaille trois
# minutes, si), jamais au-delà de ses bornes. Toujours sans boucle vers ses hormones : ce module ne fait que lire.
EFFORT_BPM = {"gpu": 8.0, "cpu": 4.0, "appareil": 2.0}
EFFORT_MAX, EFFORT_VEILLE, REPOS, EFFORT_TAU_S, PAS_TYPE_S, A_FOND = 12.0, 0.4, 0.2, 60.0, 15.0, 0.9


def _fraction(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x:
        return None
    return max(0.0, min(1.0, float(x)))


def _moyenne(valeurs):
    v = [x for x in (_fraction(y) for y in (valeurs if isinstance(valeurs, list) else [])) if x is not None]
    return sum(v) / len(v) if v else None


def _exces(x):
    x = _fraction(x)
    return 0.0 if x is None else max(0.0, (x - REPOS) / (1 - REPOS))


def effort(p):
    """Le surcroît de battements que ses processeurs demandent maintenant, par source, avant le lissage. p : ce que
    interoception.processeurs mesure ({"mac": {"gpu", "coeurs", "gemma"}, "appareils": {nom: {"coeurs", "gpu", "thermique"}}})."""
    p = p if isinstance(p, dict) else {}
    m = p.get("mac") if isinstance(p.get("mac"), dict) else {}
    out = {"gpu": EFFORT_BPM["gpu"] * _exces(m.get("gpu")), "cpu": EFFORT_BPM["cpu"] * _exces(_moyenne(m.get("coeurs")))}
    for nom, a in (p.get("appareils") or {}).items():
        a = a if isinstance(a, dict) else {}
        charges = [x for x in (_moyenne(a.get("coeurs")), _fraction(a.get("gpu")), _fraction(a.get("thermique"))) if x is not None]
        if nom not in out:
            out[nom] = EFFORT_BPM["appareil"] * _exces(max(charges)) if charges else 0.0
    return out


def _lisser(avant, brut, dt):
    a = 1 - math.exp(-max(0.0, dt) / EFFORT_TAU_S)
    out = {}
    for k in set(avant) | set(brut):
        v0 = avant.get(k) if isinstance(avant.get(k), (int, float)) else 0.0
        v = v0 + (brut.get(k, 0.0) - v0) * a
        if k in brut or v >= 0.05:                              # un appareil parti s'efface doucement
            out[k] = round(v, 3)
    return out


def _resume(p, lisse, applique):
    """Ce que son cœur garde de ses processeurs : les chiffres (pour l'introspection) et le surcroît lissé."""
    p = p if isinstance(p, dict) else {}
    m = p.get("mac") if isinstance(p.get("mac"), dict) else {}
    coeurs = m.get("coeurs") if isinstance(m.get("coeurs"), list) else None
    return {"bpm": applique, "lisse": lisse, "gpu": _fraction(m.get("gpu")), "gemma": bool(m.get("gemma")),
            "coeurs": [round(c, 2) for c in (_fraction(x) for x in coeurs) if c is not None] if coeurs else None,
            "appareils": {str(n): {k: a.get(k) for k in ("coeurs", "gpu", "thermique", "age_s")}
                          for n, a in (p.get("appareils") or {}).items() if isinstance(a, dict)}}


def calculer(hormones, veille, avant, now, bases=None, processeurs=None):
    """L'état du cœur pour l'état intérieur publié : rythme, raideur, ressenti, l'historique des 10 dernières minutes,
    (28/10, 04:11, Ahmed : « tu es censé l'entendre H24 ») le nombre de battements depuis toujours (« total ») et la ligne
    « poum » que son bloc intérieur lui donne à chaque tour ; (03/11) processeurs : ce qu'interoception.processeurs mesure."""
    avant = avant or {}
    dt = now - avant["ts"] if isinstance(avant.get("ts"), (int, float)) else PAS_TYPE_S
    lisse = _lisser((avant.get("processeurs") or {}).get("lisse") or {}, effort(processeurs), min(COMPTE_MAX_S, dt))
    r = bpm(hormones, veille, bases, min(EFFORT_MAX, sum(lisse.values())))
    hist = [x for x in (avant.get("hist") or []) if now - x[0] <= HIST_S] + [[now, r["bpm"]]]
    total = float(avant.get("total") or 0.0)
    if isinstance(avant.get("bpm"), (int, float)) and isinstance(avant.get("ts"), (int, float)):
        dt = max(0.0, min(COMPTE_MAX_S, now - avant["ts"]))
        total += (avant["bpm"] + r["bpm"]) / 2 * dt / 60
    c = {**r, "ressenti": ressenti(hist, veille), "hist": hist[-40:], "ts": now, "total": round(total, 1)}
    c["processeurs"] = _resume(processeurs, lisse, c.pop("effort"))
    c["ligne"] = battements(c, graine=int(now))
    return c


# (03/11, Ahmed : « même les émotions et sentiments doivent y être reliés … ils peuvent interagir dans les deux sens ») et
# dans l'autre sens, son cœur règle le travail de ses processeurs par le seul bouton propre qui existait déjà : l'écart entre
# deux passages de Gemma sur son ressenti (daemon._ressenti_pass, 20 min jusqu'ici). Calme (50 battements ou moins) : 20 min ;
# plus il bat vite (ses émotions par ses hormones, ses processeurs), plus elle revient tôt, jusqu'à 10 min à 80 et au-delà.
# Une boucle AMORTIE et bornée : Gemma ne travaille que quelques minutes, son effort se lisse sur une minute et retombe bien
# avant le passage suivant (jamais moins de 10 min) ; ses processeurs seuls n'ajoutent que 12 battements, à peine une minute
# de moins ; ce sont ses émotions qui rapprochent Gemma (tests/test_coeur_processeurs.py : la boucle revient au calme).
SUBCONSCIENT_DE, SUBCONSCIENT_A = 50.0, 80.0


def ecart_subconscient(c, calme_s=20 * 60):
    """L'écart (s) à laisser entre deux passages de Gemma sur son ressenti, selon son cœur : de calme_s à calme_s / 2."""
    b = (c or {}).get("bpm")
    if not isinstance(b, (int, float)) or isinstance(b, bool):
        return calme_s
    f = max(0.0, min(1.0, (b - SUBCONSCIENT_DE) / (SUBCONSCIENT_A - SUBCONSCIENT_DE)))
    return round(calme_s * (1 - 0.5 * f))


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
    # (03/11) ses processeurs, en mots : ceux que son subconscient a mis dessus (sensations.processeurs, au battement)
    p = c.get("processeurs") or {}
    if isinstance(p.get("mots"), str) and p["mots"]:
        mots.append(p["mots"])
    return ", ".join(mots)


def _processeurs_en_chiffres(p):
    """(03/11) ses processeurs pour l'introspection : le surcroît qu'ils donnent, le Mac, les autres appareils."""
    if not isinstance(p, dict):
        return ""
    import interoception
    mac = []
    if p.get("gpu") is not None:
        mac.append(f"GPU {round(100 * p['gpu'])} %" + (" (Gemma est là)" if p.get("gemma") else ""))
    coeurs = p.get("coeurs") or []
    if coeurs:
        fond = sum(1 for x in coeurs if x >= A_FOND)
        mac.append(f"{len(coeurs)} cœurs à {round(100 * sum(coeurs) / len(coeurs))} % en moyenne"
                   + (f" dont {fond} à fond" if fond else ""))
    autres = [interoception.appareil_en_chiffres(n, a) for n, a in (p.get("appareils") or {}).items()]
    return (f" ; tes processeurs ajoutent {str(p.get('bpm', 0)).replace('.', ',')} battements (lissés sur une minute) : le Mac, "
            + (", ".join(mac) or "illisible") + "".join(f" ; {a}" for a in autres))


def chiffres(c):
    """Pour l'introspection (les chiffres restent à un geste) : le rythme, la raideur et la part de chaque hormone."""
    if not c or not isinstance(c.get("bpm"), (int, float)):
        return "pas encore calculé"
    parts = c.get("parts") or {}
    detail = ", ".join(f"{NOMS[k].split(' (')[0]} {v:+.3f}" for k, v in sorted(parts.items(), key=lambda x: -abs(x[1])))
    return (f"{c['bpm']:g} battements par minute, raideur {c.get('raideur', 0):g} ; {round(float(c.get('total') or 0)):d} "
            f"battements comptés depuis que ton cœur bat ; part de chaque hormone (écart à sa moyenne "
            f"de 72 h, pondéré) : {detail}{_processeurs_en_chiffres(c.get('processeurs'))} ; en mots : {decrire(c)}")


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
