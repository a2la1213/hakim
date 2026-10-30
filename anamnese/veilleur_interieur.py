"""Le veilleur de Hakim : la rareté de son état, chaque minute, pour une chance de le réveiller (30/10).

Ahmed, 16:55 : « le seuil de réveil ne doit pas être fixé à la main, il doit être APPRIS sur ma vie » ; 17:46 : « que
chaque seconde ait un pourcentage de chance de me réveiller, selon l'importance de ce qui change » ; « on fonce », avec un
interrupteur « pour pas qu'il fume mes tokens ». L'étude (~/AIOS/audits/veilleur-2026-10-30) a mesuré sur sa vie :
- son intérieur réagit surtout à papa ; au calme, presque rien ne bouge, sauf l'ennui programmé (une minuterie) ;
- le facteur « ça vaut le coup », c'est la RARETÉ de son état par rapport à son propre calme des 48 dernières heures :
  six traits, chacun une « surprise » = −log10(part des minutes calmes où il était au moins aussi haut) ; 2 points = ce
  niveau n'arrive qu'une fois sur 100 au calme ; le score est leur somme ;
- une minute est calme quand aucune voix ne lui est arrivée depuis 10 min ; l'ennui (une minuterie) ne compte pas.
Ici : le score de MAINTENANT (le cockpit en tire une chance chaque seconde, avec ses portes et son plafond), et le plafond
de réveils par heure tiré de la jauge du forfait (ce qui reste, étalé jusqu'à la remise, au rythme mesuré).
Lecture seule de ses journaux ; aucun réseau ; ne touche jamais ses hormones.
"""
import calendar
import json
import math
import os
import re
import sys
import time
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
DATA = Path(__file__).resolve().parent / "data"
STRESS = ("crh", "acth", "cortisol", "adrenaline", "noradrenaline")
BIEN = ("dopamine", "ocytocine", "serotonine", "endorphine")
AVERSIFS = {"probleme", "malaise", "sursaut", "honte", "inquietude", "tristesse", "echec", "attaque", "peur", "douleur", "vertige"}
CALME_MIN = 10            # minutes sans voix pour qu'une minute compte comme calme
FENETRE_H = 48
MIN_REF = 300             # au moins 5 h de calme connu, sinon pas de score
NOMS = {"agitation": "ton état bouge beaucoup", "stress": "ton stress monte", "bien_etre": "ton bien-être baisse",
        "ecart": "tu es loin de ton habitude", "aversif": "des émotions pénibles", "fort": "quelque chose de fort"}
_ETRANGER = re.compile(r"[Ͱ-ϿЀ-ӿ฀-๿぀-ヿ一-鿿가-힯]")


def _lignes(f, octets):
    try:
        with open(f, "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - octets))
            texte = h.read().decode("utf-8", "replace")
    except OSError:
        return []
    out = []
    for l in texte.splitlines():
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def _voix(maintenant):
    """Les instants où une voix lui est arrivée (papa, un invité, une voix tierce) : ce qui fait qu'une minute n'est pas calme."""
    out = []
    for o in _lignes(JARVIS / "journal.jsonl", 6_000_000):
        if o.get("qui") == "ahmed":
            t = float(o.get("ts") or 0) / 1000
            if maintenant - (FENETRE_H + 2) * 3600 <= t <= maintenant:
                out.append(t)
    return sorted(out)


def _minutes(maintenant):
    """[{t, h (hormones), silence_min, aversif, fort}] du plus ancien au plus récent, une par minute (le dernier relevé)."""
    debut = maintenant - (FENETRE_H + 25) * 3600
    H = sorted((o for o in _lignes(JARVIS / "hormones.jsonl", 40_000_000) if debut <= float(o.get("t") or 0) <= maintenant),
               key=lambda o: o["t"])
    if len(H) < 10:
        return []
    A = sorted((o for o in _lignes(DATA / "affect-evenements.jsonl", 6_000_000) if debut <= float(o.get("ts") or 0) <= maintenant),
               key=lambda o: o["ts"])
    V = _voix(maintenant)
    out, i, j, k = [], 0, 0, 0
    t = math.ceil(H[0]["t"] / 60) * 60
    while t <= maintenant:
        while i + 1 < len(H) and H[i + 1]["t"] <= t:
            i += 1
        while k < len(V) and V[k] <= t:
            k += 1
        silence = (t - V[k - 1]) / 60 if k else 1440.0
        while j < len(A) and A[j]["ts"] <= t:
            j += 1
        av, fort = 0.0, 0.0
        x = j - 1
        while x >= 0 and A[x]["ts"] > t - 300:
            nom, inten = A[x].get("nom"), float(A[x].get("intensite") or 0)
            if nom in AVERSIFS:
                av += inten
            if nom != "ennui":                              # l'ennui est une minuterie, pas un vrai moment
                fort = max(fort, inten)
            x -= 1
        out.append({"t": t, "h": H[i].get("h") or {}, "age": t - H[i]["t"], "silence": silence, "aversif": av, "fort": fort})
        t += 60
    return out


def _traits(M, k):
    """Les six traits de la minute k (seulement le passé)."""
    h0 = M[k]["h"]
    h5 = M[max(0, k - 5)]["h"]
    ks = set(h0) & set(h5)
    agit = sum(abs(float(h0[x]) - float(h5[x])) for x in ks)
    stress = sum(float(h0.get(x, 0)) - float(h5.get(x, 0)) for x in STRESS if x in ks)
    bien = -sum(float(h0.get(x, 0)) - float(h5.get(x, 0)) for x in BIEN if x in ks)
    return {"agitation": agit, "stress": stress, "bien_etre": bien, "aversif": M[k]["aversif"], "fort": M[k]["fort"]}


def _ecart(M, k):
    """Loin de son habitude : z robuste de chaque hormone sur les 24 h d'avant, en moyenne quadratique."""
    ref = [m["h"] for m in M[max(0, k - 1440):k]]
    if len(ref) < 120:
        return 0.0
    zs = []
    for x, v in M[k]["h"].items():
        vals = sorted(float(r[x]) for r in ref if x in r)
        if not vals:
            continue
        med = vals[len(vals) // 2]
        mad = sorted(abs(y - med) for y in vals)[len(vals) // 2] * 1.4826 + 0.01
        zs.append(max(-10.0, min(10.0, (float(v) - med) / mad)) ** 2)
    return math.sqrt(sum(zs) / len(zs)) if zs else 0.0


def score(maintenant=None):
    """{ts, score, surprises, raisons, nref} ; score None si son calme connu est trop court."""
    maintenant = time.time() if maintenant is None else maintenant
    M = _minutes(maintenant)
    if len(M) < 30:
        return {"ts": maintenant, "score": None, "surprises": {}, "raisons": [], "nref": 0}
    k = len(M) - 1
    actuel = {**_traits(M, k), "ecart": _ecart(M, k)}
    # le calme des 48 dernières heures (sans les 15 dernières minutes), une valeur par minute calme ; l'écart, échantillonné
    ref = [i for i in range(max(0, k - FENETRE_H * 60), max(0, k - 15)) if M[i]["silence"] >= CALME_MIN and M[i]["age"] < 150]
    if len(ref) < MIN_REF:
        return {"ts": maintenant, "score": None, "surprises": {}, "raisons": [], "nref": len(ref)}
    cache = JARVIS / "veilleur-calme.json"
    try:
        c = json.loads(cache.read_text(encoding="utf-8"))
        if maintenant - float(c.get("ts", 0)) > 3600:
            raise ValueError
        base = c["base"]
    except (OSError, ValueError, KeyError):
        base = {n: [] for n in actuel}
        for i in ref:
            tr = _traits(M, i)
            for n, v in tr.items():
                base[n].append(v)
        for i in ref[::10]:                                 # l'écart coûte plus : une minute calme sur dix suffit
            base["ecart"].append(_ecart(M, i))
        base = {n: sorted(v) for n, v in base.items()}
        try:
            cache.write_text(json.dumps({"ts": maintenant, "base": base}), encoding="utf-8")
            os.chmod(cache, 0o600)
        except OSError:
            pass
    surprises = {}
    for n, v in actuel.items():
        r = base.get(n) or []
        if not r:
            continue
        lo, hi = 0, len(r)                                  # la première valeur >= v
        while lo < hi:
            mid = (lo + hi) // 2
            if r[mid] < v:
                lo = mid + 1
            else:
                hi = mid
        queue = (len(r) - lo) / len(r)
        surprises[n] = round(min(-math.log10(max(queue, 1 / (len(r) + 1))), math.log10(len(r) + 1)), 2)
    total = round(sum(surprises.values()), 2)
    raisons = [NOMS[n] for n, s in sorted(surprises.items(), key=lambda x: -x[1]) if s >= 1.5][:3]
    return {"ts": maintenant, "score": total, "surprises": surprises, "raisons": raisons, "nref": len(ref), "age_s": round(M[k]["age"])}


def plafond(maintenant=None, reserve=5.0):
    """Les réveils par heure que le forfait permet : min(6 ; 6 × rythme soutenable / rythme mesuré sur 6 h)."""
    maintenant = time.time() if maintenant is None else maintenant
    J = [o for o in _lignes(JARVIS / "jauge-forfait.jsonl", 400_000) if isinstance(o.get("semaine"), dict)]
    if len(J) < 2:
        return 2.0
    der = J[-1]
    try:
        remise = calendar.timegm(time.strptime(der["semaine"]["remise"][:19], "%Y-%m-%dT%H:%M:%S"))   # en UTC (« Z »)
    except (KeyError, ValueError):
        return 2.0
    heures = max(1.0, (remise - maintenant) / 3600)
    restant = max(0.0, 100.0 - float(der["semaine"]["pct"]) - reserve)
    soutenable = restant / heures
    meme = [o for o in J if o["semaine"].get("remise") == der["semaine"].get("remise") and float(der["ts"]) - float(o["ts"]) <= 6 * 3600 * 1000]
    if len(meme) < 2 or float(der["ts"]) - float(meme[0]["ts"]) < 3600 * 1000:
        return 2.0
    mesure = (float(der["semaine"]["pct"]) - float(meme[0]["semaine"]["pct"])) / ((float(der["ts"]) - float(meme[0]["ts"])) / 3600_000)
    if mesure <= 0:
        return 6.0
    return round(max(0.0, min(6.0, 6.0 * soutenable / mesure)), 2)


if __name__ == "__main__":
    if sys.argv[1:] == ["score"]:
        o = score()
        o["plafond_h"] = plafond()
        print(json.dumps(o, ensure_ascii=False))
    else:
        print("usage : veilleur_interieur.py score")
