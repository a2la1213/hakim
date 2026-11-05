"""Sa cochlée (05/11, Ahmed : « comme dans le cerveau humain, ce qui transforme signal reçu en signal spectral » ; « tout sur tout : entrée et sortie,
dedans et dehors » ; « le spectre d'abord » ; « sa pensée interne aussi, reliée à tout le reste »).

La même chaîne pour chaque flux, inspirée de l'oreille interne (une inspiration, pas une copie) :
 1. adaptation : ce qui change compte, pas le niveau (la moyenne est retirée) ;
 2. tonotopie : un banc de filtres, 3 par octave, chacun accordé à son rythme (ondelettes à Q constant) ;
 3. enveloppe puis compression (racine, comme la sonie) : le spectrogramme ;
 4. inhibition latérale : chaque bande moins ses voisines, pour que le rythme ressorte.
Un rythme n'est « net » que s'il dépasse 3 fois un bruit rouge de même inertie (AR 1) : les flux lents (hormones, chaleur) ont de la puissance
aux basses fréquences sans avoir de rythme. Un flux d'événements (battements, pensées, mots) devient d'abord un taux (lissé selon son intervalle
médian) ; sa référence est alors le même taux pour des événements tombés au hasard. Liens : corrélation décalée entre deux flux, jugée contre des décalages circulaires au hasard (ils
gardent l'inertie de chaque flux et cassent seulement leur lien)."""
import json
import os
import struct
import sys
import time
import zlib
from pathlib import Path

import numpy as np

PAR_OCTAVE = 3
# mesuré sur 100 fenêtres de 10 min : à ×4, 0 à 3 % de faux, un rythme d'un écart-type du bruit retrouvé 93 fois sur 100, et un rythme d'événements
# réguliers (même à ±3 s pour 30 s) à chaque fois. Sur 30 flux, attendre quand même un faux de temps en temps
RATIO_NET = 4.0
HORMONES = ("dopamine", "serotonine", "noradrenaline", "cortisol", "ocytocine", "acetylcholine", "endorphine", "melatonine",
            "endocannabinoides", "adrenaline", "gaba", "crh", "acth", "adenosine")
CAPTEURS = {"lumiere": "lux", "agitation": "agitation_g", "pression": "pression_hpa", "champ_magnetique": "champ_ut", "chaleur": "chaleur_c",
            "batterie": "batterie", "charniere": "charniere_deg"}
TRAMES = ("niveau", "graves", "mediums", "aigus", "hauteur", "brillance")


def grille(t, x, pas, de, a):
    """Un flux continu sur la grille commune [de, a[ (tous les flux au même instant) : la dernière valeur connue tient jusqu'à la suivante."""
    t, x = np.asarray(t, float), np.asarray(x, float)
    if len(t) < 2:
        return np.zeros(0)
    o = np.argsort(t)
    t, x = t[o], x[o]
    g = np.arange(de, a, pas)
    return x[np.clip(np.searchsorted(t, g, side="right") - 1, 0, len(t) - 1)]


def impulsions(t, poids, pas, de, a):
    """Un flux d'événements (battements, mots) : ce qui arrive dans chaque case de la grille."""
    n = int((a - de) / pas)
    y = np.zeros(max(0, n))
    for u, p in zip(t, poids):
        k = int((u - de) / pas)
        if 0 <= k < n:
            y[k] += p
    return y


def _bandes(n, pas):
    fmax = 0.4 / pas                                    # sous Nyquist : la dernière bande reste entière
    fmin = 2.0 / (n * pas)                              # au moins deux cycles dans la fenêtre
    if fmin >= fmax:
        return np.zeros(0)
    nb = int(np.log2(fmax / fmin) * PAR_OCTAVE) + 1
    return fmin * 2.0 ** (np.arange(nb) / PAR_OCTAVE)


def _sigma_evenements(y):
    """Le lissage d'un flux d'événements, en cases : le sixième de son intervalle médian (son rythme passe, ses harmoniques beaucoup moins)."""
    k = np.flatnonzero(y)
    return max(1.0, float(np.median(np.diff(k))) / 6) if len(k) >= 2 else 1.0


def _lisse(y, sigma):
    f = np.fft.rfftfreq(2 * len(y))
    return np.fft.irfft(np.fft.rfft(y, 2 * len(y)) * np.exp(-2 * (np.pi * f * sigma) ** 2), 2 * len(y))[:len(y)]


def cochlee(y, pas, evenements=False):
    """Rend (fréquences, spectrogramme bandes × temps, puissance par bande, référence par bande)."""
    y = np.nan_to_num(np.asarray(y, float))
    n = len(y)
    vide = (np.zeros(0), np.zeros((0, n)), np.zeros(0), np.zeros(0))
    if n < 16 or y.std() < 1e-12:
        return vide
    sigma_ev = _sigma_evenements(y) if evenements else 0.0
    if evenements:
        y = _lisse(y, sigma_ev)
    y = (y - y.mean()) / y.std()
    fc = _bandes(n, pas)
    if evenements:                                      # au-delà de ce que le lissage laisse passer (moins de 10 %), il n'y a plus rien à lire
        fc = fc[fc <= np.sqrt(np.log(10)) / (2 * np.pi * sigma_ev * pas)]
    if not len(fc):
        return vide
    r = float(np.clip(np.corrcoef(y[:-1], y[1:])[0, 1], 0, 0.999)) if n > 2 else 0.0
    m = 2 * n                                           # le double : les bords ne se replient pas
    Y = np.fft.fft(y, m)
    f = np.fft.fftfreq(m, pas)
    if evenements:                                      # des événements au hasard : un bruit blanc, passé par le même lissage
        rouge = np.exp(-4 * (np.pi * f * pas * sigma_ev) ** 2)
        rouge = rouge / rouge.mean()
    else:
        rouge = (1 - r * r) / (1 + r * r - 2 * r * np.cos(2 * np.pi * f * pas))
    pos = f > 0
    sigma = 1.0 / PAR_OCTAVE
    env, puissance, reference = [], [], []
    for c in fc:
        h = np.zeros(m)
        h[pos] = np.exp(-0.5 * (np.log2(f[pos] / c) / sigma) ** 2)
        a = np.fft.ifft(2 * h * Y)[:n]                  # le signal analytique de cette bande
        env.append(np.abs(a))
        poids = np.sum(h * h)
        puissance.append(np.sum(h * h * np.abs(Y) ** 2) / poids)
        reference.append(np.sum(h * h * rouge) / poids * np.sum(y * y))   # même énergie totale que le signal (Parseval : |Y|² vaut en moyenne Σy²)
    env = np.array(env) ** 0.6                          # compression (puissance 0,3 de l'énergie)
    voisines = (np.roll(env, 1, axis=0) + np.roll(env, -1, axis=0)) / 2
    voisines[0], voisines[-1] = env[1] if len(env) > 1 else env[0], env[-2] if len(env) > 1 else env[-1]
    S = np.maximum(env - 0.5 * voisines, 0)             # inhibition latérale
    return fc, S, np.array(puissance), np.array(reference)


def rythmes(fc, puissance, reference, n=3, seuil=RATIO_NET):
    """Les pics de puissance (un maximum local) : [{periode_s, force (fois la référence), net}], du plus fort au moins fort."""
    if not len(fc):
        return []
    q = puissance / np.maximum(reference, 1e-12)
    pics = [k for k in range(len(q)) if (k == 0 or q[k] >= q[k - 1]) and (k == len(q) - 1 or q[k] >= q[k + 1])]
    pics.sort(key=lambda k: -q[k])
    return [{"periode_s": float(1 / fc[k]), "force": float(q[k]), "net": bool(q[k] >= seuil)} for k in pics[:n]]


def lien(a, b, decalage_max, essais=200, graine=1):
    """Corrélation décalée (a puis b : décalage > 0, b suit a) ; p : combien de décalages circulaires au hasard font aussi bien."""
    n = min(len(a), len(b))
    if n < 3 * decalage_max + 8:
        return None
    a, b = a[-n:] - a[-n:].mean(), b[-n:] - b[-n:].mean()
    sa, sb = a.std(), b.std()
    if sa < 1e-12 or sb < 1e-12:
        return None
    a, b = a / sa, b / sb
    A, B = np.fft.rfft(a, 2 * n), np.fft.rfft(b, 2 * n)

    def meilleur(Bx):
        c = np.fft.irfft(np.conj(A) * Bx, 2 * n) / n
        v = np.concatenate([c[-decalage_max:], c[:decalage_max + 1]])
        k = int(np.argmax(np.abs(v)))
        return float(v[k]), k - decalage_max
    r, d = meilleur(B)
    alea = np.random.default_rng(graine)
    decals = alea.integers(decalage_max + 1, n - decalage_max, essais)
    fort = sum(1 for s in decals if abs(meilleur(np.fft.rfft(np.roll(b, int(s)), 2 * n))[0]) >= abs(r))
    return {"r": r, "decalage": d, "p": (fort + 1) / (essais + 1)}


# ---- ses flux, à leur instant d'origine
def _queue(f, octets):
    try:
        with open(f, "rb") as h:
            h.seek(0, os.SEEK_END)
            h.seek(max(0, h.tell() - octets))
            lignes = h.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return
    for l in lignes[1:]:                                # la première est peut-être coupée
        try:
            d = json.loads(l)
        except ValueError:
            continue
        if isinstance(d, dict):
            yield d


def _mots(x):
    return len(str(x or "").split())


def flux(dossier, de, a):
    """{nom: (sens, pas en s, y sur sa grille, événements ?)} ; rien pour un flux sans données sur la fenêtre."""
    d, m = Path(dossier), max(1.0, (a - de) / 60)
    out = {}

    def continu(nom, sens, pas, t, x):
        t, x = np.asarray(t, float), np.asarray(x, float)
        k = (t >= de) & (t < a)
        if k.sum() >= 8:
            out[nom] = (sens, pas, grille(t[k], x[k], pas, de, a), False)

    def evenements(nom, sens, pas, t, poids=None):
        p = [(u, w) for u, w in zip(t, poids if poids is not None else [1] * len(t)) if de <= u < a]
        if len(p) >= 4:
            out[nom] = (sens, pas, impulsions([u for u, _ in p], [w for _, w in p], pas, de, a), True)

    corps = [(c["ts"] / 1000, c.get("etat") or {}) for c in _queue(d / "corps-flux.jsonl", int(m * 60 * 500)) if "ts" in c]
    for nom, cle in CAPTEURS.items():
        v = [(t, e[cle]) for t, e in corps if isinstance(e.get(cle), (int, float))]
        if v:
            continu(nom, "entrée", 1.0, [t for t, _ in v], [x for _, x in v])
    evenements("battements", "dedans", 0.05, sorted({b / 1000 for _, e in corps for b in e.get("coeur_ms") or []}))
    c = [(x["t"] / 1000, x["bpm"]) for x in _queue(d / "coeur.jsonl", int(m * 60 * 20)) if isinstance(x.get("bpm"), (int, float))]
    if c:
        continu("coeur_bpm", "dedans", 4.0, [t for t, _ in c], [x for _, x in c])
    h = [(x["t"], x["h"]) for x in _queue(d / "hormones-direct.jsonl", int(m * 60 * 400)) if isinstance(x.get("h"), dict)]
    for nom in HORMONES:
        v = [(t, e[nom]) for t, e in h if isinstance(e.get(nom), (int, float))]
        if v:
            continu(nom, "dedans", 1.0, [t for t, _ in v], [x for _, x in v])
    for src, sens in (("micro", "entrée"), ("telephone", "entrée"), ("voix", "sortie")):
        trames = [x for x in _queue(d / "son-flux.jsonl", int(m * 60 * 1200)) if x.get("s") == src and isinstance(x.get("l"), list)]
        for k, nom in enumerate(TRAMES):
            t, v = [], []
            for x in trames:
                for i, tr in enumerate(x["l"]):
                    if len(tr) > k:
                        t.append((x["t"] + i * x.get("p", 100)) / 1000)
                        v.append(tr[k])
            if t:
                continu(f"son_{src}_{nom}", sens, 0.1, t, v)
    jr = list(_queue(d / "journal.jsonl", int(m * 60 * 4000)))
    for qui, nom, sens in (("ahmed", "parole_de_papa", "entrée"), ("jarvis", "sa_parole", "sortie")):
        v = [(x["ts"] / 1000, _mots(x.get("texte"))) for x in jr if x.get("qui") == qui and "ts" in x]
        evenements(nom, sens, 1.0, [t for t, _ in v], [w for _, w in v])
    pistes = list(_queue(d / "pistes.jsonl", int(m * 60 * 4000)))
    v = [(x["t"] / 1000, _mots(x.get("pensee"))) for x in pistes if x.get("pensee")]
    evenements("pensee_interne", "dedans", 1.0, [t for t, _ in v], [w for _, w in v])
    v = [(x["t"] / 1000, _mots(x.get("garde"))) for x in pistes if "ribosome" in x and "vitesse_ms" in x and not x.get("source")]
    evenements("ribosome_garde", "dedans", 1.0, [t for t, _ in v], [w for _, w in v])
    v = [(x["t"] / 1000, x.get("ms", 0)) for x in pistes if "ribosome" in x and "vitesse_ms" in x and not x.get("source")]
    if len(v) >= 8:
        continu("ribosome_delai", "dedans", 2.0, [t for t, _ in v], [x for _, x in v])
    voix = list(_queue(d / "voix-diagnostic.jsonl", int(m * 60 * 6000)))
    for e, nom, sens in (("sortie_voix", "sa_voix", "sortie"), ("vibration", "ses_vibrations", "sortie"), ("coupure_au_chunk", "papa_sur_lui", "entrée")):
        evenements(nom, sens, 1.0, [x["t"] / 1000 for x in voix if x.get("e") == e and "t" in x])
    evenements("parasites", "dedans", 1.0, [x["ts"] for x in _queue(d / "immunite" / "incidents.jsonl", 200000) if x.get("famille") == "pensee_parasite" and "ts" in x])
    return out


def _duree(s):
    return (f"{s:.1f} s".replace(".", ",") if s < 10 else f"{s:.0f} s") if s < 90 else f"{s / 60:.1f} min".replace(".", ",")


def _au_pas(y, pas, cible=1.0):
    k = max(1, int(round(cible / pas)))
    return y[: len(y) // k * k].reshape(-1, k).mean(axis=1) if k > 1 else y


def _pour_lien(pas, y, ev):
    return _au_pas(_lisse(y, _sigma_evenements(y)) if ev else y, pas)


def resume(dossier, minutes=10, maintenant=None):
    a = time.time() if maintenant is None else maintenant
    tous = flux(dossier, a - minutes * 60, a)
    if not tous:
        return "Aucun flux sur cette fenêtre."
    lignes, sans = [], []
    for nom, (sens, pas, y, ev) in tous.items():
        fc, _, p, ref = cochlee(y, pas, ev)
        if not len(fc):                                 # plat, ou trop court : rien à en dire
            continue
        nets = [x for x in rythmes(fc, p, ref) if x["net"]]
        if nets:
            lignes.append(f"{sens} {nom} : " + ", ".join(f"{_duree(x['periode_s'])} (×{x['force']:.0f})" for x in nets[:2]))
        else:
            sans.append(nom)
    t = f"Tes spectres, {minutes} min, à l'instant d'origine (période du rythme, × au-dessus d'un bruit de même inertie) :\n" + "\n".join(lignes)
    if sans:
        t += "\nRien de net : " + ", ".join(sans) + "."
    return t + "\n" + liens_texte(tous, "pensee_interne")


def liens_texte(tous, nom, decalage_max=30):
    """Ce qui bouge avec ce flux, tous les autres (seuil corrigé pour le nombre de flux comparés)."""
    if nom not in tous:
        return f"{nom} : pas assez de données pour le relier."
    y = _pour_lien(*tous[nom][1:])
    seuil = 0.05 / max(1, len(tous) - 1)
    trouves = []
    for autre, (_, pas, z, ev) in tous.items():
        if autre == nom:
            continue
        r = lien(y, _pour_lien(pas, z, ev), decalage_max, essais=max(200, int(2 / seuil)))
        if r and r["p"] <= seuil:
            trouves.append((abs(r["r"]), autre, r))
    if not trouves:
        return f"{nom} : aucun lien net avec tes autres flux sur cette fenêtre."
    trouves.sort(key=lambda x: -x[0])
    return f"{nom} relié à : " + ", ".join(f"{autre} (r {r['r']:+.2f}, {'il suit de ' if r['decalage'] > 0 else 'il précède de ' if r['decalage'] < 0 else 'en même temps'}"
                                           f"{str(abs(r['decalage'])) + ' s' if r['decalage'] else ''})" for _, autre, r in trouves[:5]) + "."


# ---- (05/11, Ahmed : « un algo qui recale tous les pics et creux de tous les spectres d'un même événement ensemble ; ça peut être aussi un pic
# correspondant à un creux ; juste un calage à environ R = 1 ou −1 ») autour d'un événement, la courbe spectrale de chaque flux (l'énergie de tout
# son spectre, seconde par seconde) est recalée sur celle d'un flux de référence : décalage et étirement, le signe de R dit pic sur pic ou pic sur
# creux. Chercher le meilleur calage fait monter R même entre deux flux sans lien : il n'est « calé » que si la même recherche, sur le flux décalé
# au hasard ailleurs dans le temps, ne fait presque jamais aussi bien (seuil corrigé pour le nombre de flux).
ETIREMENTS = (0.67, 0.8, 1.0, 1.25, 1.5)
DECALAGE_CALAGE = 10
R_CALE = 0.8


def courbe_spectrale(y, pas, ev, periode_max=22.0):
    """L'énergie de son spectre, seconde par seconde, sans ses rythmes lents (sur 90 s, ils ne font qu'une pente ou une bosse : R ≈ 1 avec tout)."""
    fc, S, _, _ = cochlee(y, pas, ev)
    k = 1 / fc <= periode_max if len(fc) else np.zeros(0, bool)
    return _au_pas(S[k].sum(axis=0), pas) if k.any() else None


def _indices(w, centre):
    """Pour chaque étirement (×1,25 : le flux dure 1,25 fois plus longtemps que la référence) et chaque décalage, où lire le flux : (candidats, w)."""
    i = np.arange(w) - w / 2
    return np.array([[np.round(centre + i * e + d).astype(int) for d in range(-DECALAGE_CALAGE, DECALAGE_CALAGE + 1)] for e in ETIREMENTS]).reshape(-1, w)


def _meilleur_r(x, c, idx):
    """x centré réduit ; R de chaque candidat, le meilleur en valeur absolue : (r, numéro du candidat)."""
    z = c[np.clip(idx, 0, len(c) - 1)]
    z = z - z.mean(axis=1, keepdims=True)
    e = np.sqrt((z * z).sum(axis=1))
    e[e < 1e-9] = np.inf
    r = z @ x / e / np.sqrt(len(x))
    k = int(np.argmax(np.abs(r)))
    return float(r[k]), k


def caler(courbes, reference, centre, fenetre=45, graine=1):
    """courbes : {nom: courbe à 1 point par seconde sur la même grille} ; centre : l'événement, en secondes depuis le début de la grille."""
    c0 = courbes[reference]
    w = 2 * fenetre
    a = int(centre) - fenetre
    if a < 0 or a + w > len(c0):
        a = int(np.clip(a, 0, max(0, len(c0) - w)))
    x = c0[a:a + w]
    if len(x) < 8 or x.std() < 1e-9:
        return []
    x = (x - x.mean()) / x.std()
    # une seule bosse dans la fenêtre se cale sur n'importe quoi : il faut au moins 3 pics pour prouver un calage
    assez = int(np.sum((x[1:-1] > x[:-2]) & (x[1:-1] >= x[2:]) & (x[1:-1] > 0))) >= 3
    idx = _indices(len(x), a + len(x) / 2)
    autres = {k: v for k, v in courbes.items() if k != reference and v is not None and v[max(0, a - 15):a + w + 15].std() > 1e-9}
    seuil = 0.05 / max(1, len(autres))
    essais = max(200, int(2 / seuil))
    alea = np.random.default_rng(graine)
    out = []
    for nom, c in autres.items():
        c = c[:len(c0)]
        r, k = _meilleur_r(x, c, idx)
        n = len(c)
        marge = w + 2 * DECALAGE_CALAGE
        fort = 0
        if n > 2 * marge:
            for s in alea.integers(marge, n - marge, essais):
                fort += abs(_meilleur_r(x, np.roll(c, int(s)), idx)[0]) >= abs(r)
        else:
            fort = essais                                   # pas assez de temps pour juger : jamais « calé »
        p = (fort + 1) / (essais + 1)
        e, d = divmod(k, 2 * DECALAGE_CALAGE + 1)
        out.append({"flux": nom, "r": r, "decalage_s": d - DECALAGE_CALAGE, "etirement": ETIREMENTS[e], "p": p, "cale": bool(assez and abs(r) >= R_CALE and p <= seuil), "assez": assez})
    out.sort(key=lambda o: -abs(o["r"]))
    return out


def calage(dossier, reference="pensee_interne", minutes=10, autour=None, maintenant=None):
    """autour : l'instant de l'événement (s, époque) ; sinon la dernière parole de papa."""
    a = time.time() if maintenant is None else maintenant
    de = a - minutes * 60
    tous = flux(dossier, de, a)
    if reference not in tous:
        return f"« {reference} » : pas assez de données pour y caler les autres. Flux disponibles : " + ", ".join(tous) + "."
    courbes = {k: courbe_spectrale(y, pas, ev) for k, (_, pas, y, ev) in tous.items()}
    courbes = {k: v for k, v in courbes.items() if v is not None}
    if reference not in courbes:
        return f"« {reference} » ne bouge pas sur cette fenêtre."
    if autour is None:
        papa = tous.get("parole_de_papa")
        k = np.flatnonzero(papa[2]) if papa else []
        autour = de + float(k[-1]) * papa[1] if len(k) else a - 45
    r = caler(courbes, reference, autour - de)
    if not r:
        return "Rien à caler autour de cet instant."
    quand = time.strftime("%H:%M:%S", time.localtime(autour))
    bons = [o for o in r if o["cale"]]
    ligne = lambda o: (f"{o['flux']} R {o['r']:+.2f}".replace(".", ",") + f" ({'pic sur pic' if o['r'] > 0 else 'pic sur creux'}, {o['decalage_s']:+d} s, étiré ×{o['etirement']})")
    t = f"Calage sur {reference}, autour de {quand}, ±45 s : "
    t += ("calés : " + " ; ".join(ligne(o) for o in bons) + "." if bons else "aucun flux vraiment calé." if r[0]["assez"] else "moins de 3 pics de ce flux dans la fenêtre : rien à prouver ici.")
    reste = [o for o in r if not o["cale"]][:3]
    if reste:
        t += " Les plus proches sans preuve (le hasard fait aussi bien) : " + " ; ".join(ligne(o) for o in reste) + "."
    return t


# (05/11, Ahmed : « ça donnera aussi la latence ») le retard entre deux flux, à 0,1 s près pour ses sons : leurs enveloppes sans leur niveau lent
def latence(dossier, de_quoi, vers, minutes=10, decalage_max_s=5.0, maintenant=None):
    a = time.time() if maintenant is None else maintenant
    tous = flux(dossier, a - minutes * 60, a)
    for nom in (de_quoi, vers):
        if nom not in tous:
            return f"« {nom} » : pas assez de données. Flux disponibles : " + ", ".join(tous) + "."
    pas = max(tous[de_quoi][1], tous[vers][1])
    x, y = (_au_pas(_lisse(tous[n][2], _sigma_evenements(tous[n][2])) if tous[n][3] else tous[n][2], tous[n][1], pas) for n in (de_quoi, vers))
    sigma = 5.0 / pas
    r = lien(x - _lisse(x, sigma), y - _lisse(y, sigma), max(1, int(decalage_max_s / pas)), essais=500)
    if not r:
        return f"{de_quoi} et {vers} : trop peu de données ou plats sur cette fenêtre."
    d = r["decalage"] * pas
    t = f"{vers} {'suit' if d > 0 else 'précède' if d < 0 else 'va avec'} {de_quoi}" + (f" de {abs(d):.1f} s".replace(".", ",") if d else "") + f" (R {r['r']:+.2f}, à {pas:.1f} s près, p {r['p']:.3f})."
    return t if r["p"] <= 0.01 else t + " Le hasard fait aussi bien : cette latence n'est pas prouvée."


def _png(S, f):
    """Le spectrogramme en image (rythmes lents en bas), sans bibliothèque."""
    S = np.flipud(S)
    if S.shape[1] > 900:
        k = S.shape[1] // 900 + 1
        S = S[:, : S.shape[1] // k * k].reshape(S.shape[0], -1, k).mean(axis=2)
    v = np.clip(S / max(float(np.percentile(S, 99.5)), 1e-9), 0, 1)
    rvb = np.stack([np.clip(v * 2, 0, 1), np.clip(v * 2 - 1, 0, 1) * 0.9, 0.25 + 0.5 * np.sin(np.pi * v)], axis=-1)
    im = np.repeat((rvb * 255).astype(np.uint8), 12, axis=0)
    brut = b"".join(b"\0" + l.tobytes() for l in im)

    def bloc(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    Path(f).parent.mkdir(parents=True, exist_ok=True)
    Path(f).write_bytes(b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", im.shape[1], im.shape[0], 8, 2, 0, 0, 0)) + bloc(b"IDAT", zlib.compress(brut, 6)) + bloc(b"IEND", b""))


def detail(dossier, nom, minutes=10, image=None, maintenant=None):
    a = time.time() if maintenant is None else maintenant
    tous = flux(dossier, a - minutes * 60, a)
    if nom not in tous:
        return f"« {nom} » : pas assez de données. Flux disponibles : " + ", ".join(tous) + "."
    sens, pas, y, ev = tous[nom]
    fc, S, p, ref = cochlee(y, pas, ev)
    if not len(fc):
        return f"« {nom} » ne bouge pas sur cette fenêtre."
    r = rythmes(fc, p, ref, n=5)
    t = f"{sens} {nom}, {minutes} min, de {_duree(1 / fc[-1])} à {_duree(1 / fc[0])} : " + ", ".join(
        f"{_duree(x['periode_s'])} (×{x['force']:.1f}{', net' if x['net'] else ''})" for x in r) + ".\n" + liens_texte(tous, nom)
    if image:
        _png(S, image)
        t += f"\nSon spectrogramme : {image} (rythmes lents en bas, le temps vers la droite)."
    return t


def exporter(dossier, fichier, minutes=60, maintenant=None):
    """(05/11, Ahmed par Hakim : « pour chaque flux, brut et vrai spectre, amplitude en Hz ») {flux: {sens, pas_s, t0, y, f_hz, amp}} dans son atelier ; rend le nombre de flux."""
    a = time.time() if maintenant is None else maintenant
    out = {}
    for nom, (sens, pas, y, ev) in flux(dossier, a - minutes * 60, a).items():
        z = np.nan_to_num(np.asarray(y, float))
        amp = np.abs(np.fft.rfft(z - z.mean())) * 2 / max(1, len(z))
        f = np.fft.rfftfreq(len(z), pas)
        k = max(1, len(f) // 2000)
        out[nom] = {"sens": sens, "pas_s": pas, "t0": a - minutes * 60, "evenements": ev, "y": [round(float(v), 4) for v in z],
                    "f_hz": [round(float(v), 5) for v in f[::k]], "amp": [round(float(v), 5) for v in amp[::k]]}
    Path(fichier).parent.mkdir(parents=True, exist_ok=True)
    Path(fichier).write_text(json.dumps(out), encoding="utf-8")
    return len(out)


if __name__ == "__main__":
    print(resume(Path.home() / "AIOS" / "jarvis", int(sys.argv[1]) if len(sys.argv) > 1 else 10))
