"""Le « scanner » du subconscient (demande d'Ahmed, 2026-10-20) : que Claude, le cortex de Hakim, profite de
l'humeur de Gemma, son subconscient, SANS qu'on lui écrive « tu es triste, parle triste ».

Gemma lit le message d'Ahmed deux fois, dans le même cadre : une fois neutre, une fois avec l'humeur du moment.
Aucun texte n'est généré : on compare seulement, à l'endroit où la réponse commencerait, la probabilité de chaque
mot dans les deux lectures. Les mots dont la probabilité MONTE le plus sous l'humeur sont « les mots qui
affleurent » : ils sont donnés à Claude comme une matière (ce qui lui vient à l'esprit), jamais comme une consigne.

Deux passes du réseau sur un texte court : environ une à trois secondes, rien de plus.
(Les vecteurs de pilotage de pilotage.py, eux, ne tiennent pas sur Gemma 4 12B en 4 bits : bilan du 2026-10-20.)
"""
import re
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilotage as P  # noqa: E402  (le même modèle, déjà chargé si le subconscient tourne)

CADRE = ("Tu es le subconscient de Hakim, l'IA d'Ahmed. Tu ne réponds pas : tu laisses venir ce que son message "
         "t'évoque.{humeur}\n\nAhmed : « {message} »")
SONDES = ["Ce que ça m'évoque, en quelques mots :", "Ce que je ressens en lisant ça :", "Les mots qui me viennent :"]
# le ressenti cherche la SENSATION d'avant l'émotion (Ahmed : « une sensation grise, pesante et lourde, ou joviale,
# éclatante et vive, et c'est ensuite qu'on interprète ») : couleur, poids, texture, énergie — Gemma choisit lesquelles
SONDES_SENSATION = ["Au fond de moi, la sensation est", "Ce que je sens tout au fond est", "La couleur de ce que je ressens est"]
VIDES = set("alors aussi avec avoir avant comme dans donc elle elles encore entre être fait faire leur leurs mais même nous "
            "parce pour quand quel quelle quoi sans sous tout tous très vous était cette ceci celui cela depuis juste bien "
            "plus moins peut voir dire chose choses ahmed hakim jarvis message messages évoque ressens viennent mots "
            "tellement vraiment assez toujours presque plutôt sensation sensations couleur fond".split())
_MOT = re.compile(r"^[a-zàâçéèêëîïôûùüÿœæ'-]{4,}$")


def _logits_fin(cadre, sonde):
    """Log-probabilités du mot suivant, après le cadre (gabarit de conversation) et le début de réponse (sonde)."""
    import mlx.core as mx
    m, tok = P._charger()
    g = P._gabarit(cadre)
    debut = list(g) if isinstance(g, list) else tok.encode(g)
    ids = mx.array([debut + tok.encode(sonde, add_special_tokens=False)])
    out = m(ids)[0, -1].astype(mx.float32)
    lp = out - mx.logsumexp(out)
    mx.eval(lp)
    return np.array(lp)


def _vocab_mots():
    """Les jetons qui sont des débuts de mots français entiers (une seule fois, mis en cache)."""
    global _MOTS
    try:
        return _MOTS
    except NameError:
        pass
    _, tok = P._charger()
    ids, mots = [], []
    for i in range(262144):
        t = tok.decode([i])
        if not t.startswith(" "):
            continue
        w = t.strip().lower()
        if _MOT.match(w) and w not in VIDES:
            ids.append(i)
            mots.append(w)
    _MOTS = (np.array(ids), mots)
    return _MOTS


def scanner(message, humeur, k=8, sondes=SONDES):
    """Les mots qui affleurent sous cette humeur en lisant ce message : [(mot, hausse en log-probabilité)]."""
    ids, mots = _vocab_mots()
    message = " ".join(str(message).split())[:1500]
    hausse = np.zeros(len(ids))
    for s in sondes:
        neutre = _logits_fin(CADRE.format(humeur="", message=message), s)
        teinte = _logits_fin(CADRE.format(humeur=f" Ton humeur en ce moment : {humeur}.", message=message), s)
        # la hausse, comptée seulement pour des mots plausibles sous l'humeur (sinon des raretés sans sens montent)
        d = (teinte - neutre)[ids]
        d[teinte[ids] < -12] = 0.0
        hausse += d
    hausse /= len(sondes)
    vus, out = set(), []
    for j in np.argsort(-hausse):
        w = mots[j]
        racine = w[:5]
        if racine in vus:
            continue
        vus.add(racine)
        out.append((w, round(float(hausse[j]), 2)))
        if len(out) >= k:
            break
    return out


def _racine(w):
    """Pour ne pas servir deux fois la même sensation (doux / douce, gris / grisâtre) : le genre ramené au
    masculin, puis les quatre premières lettres."""
    w = w.lower()
    if w.endswith("euse"):
        w = w[:-4] + "eux"
    elif w.endswith("ouce"):
        w = w[:-2] + "x"
    elif w.endswith("e") and len(w) > 4:
        w = w[:-1]
    return w[:4]


def _completer(debut_ids, cand, max_tokens=3):
    """Un début de mot (« lour ») prolongé par Gemma elle-même, dans le même contexte, jusqu'à la fin du mot."""
    from mlx_lm import stream_generate
    m, tok = P._charger()
    mot = tok.decode([int(cand)]).strip()
    for r in stream_generate(m, tok, prompt=list(debut_ids) + [int(cand)], max_tokens=max_tokens):
        t = r.text
        suite = re.match(r"^[a-zàâçéèêëîïôûùüÿœæ'-]+", t or "", re.I)
        if not t or t[0].isspace() or not suite:
            break
        mot += suite.group(0)
        if len(suite.group(0)) < len(t):
            break
    return mot.lower()


def ressenti(humeur, contexte, k=6, candidats=14, sondes=SONDES_SENSATION):
    """Le RESSENTI en réserve (choix d'Ahmed, 2026-10-20 : calculé quand Gemma est déjà chargée, donné à Claude
    pendant la conversation sans attente) : les mots de sensation qui affleurent sous cette humeur à la lecture
    des derniers échanges ; mots entiers, sans l'écho du nom de l'humeur ni des mots d'Ahmed."""
    _, tok = P._charger()
    ids, mots = _vocab_mots()
    message = " ".join(str(contexte).split())[-1500:]
    hausse = np.zeros(len(ids))
    for s in sondes:
        neutre = _logits_fin(CADRE.format(humeur="", message=message), s)
        teinte = _logits_fin(CADRE.format(humeur=f" Ton humeur en ce moment : {humeur}.", message=message), s)
        d = (teinte - neutre)[ids]
        d[teinte[ids] < -12] = 0.0
        hausse += d
    hausse /= len(sondes)
    g = P._gabarit(CADRE.format(humeur=f" Ton humeur en ce moment : {humeur}.", message=message))
    debut = (list(g) if isinstance(g, list) else tok.encode(g)) + tok.encode(sondes[0], add_special_tokens=False)
    echos = {_racine(w) for w in re.findall(r"[a-zàâçéèêëîïôûùüÿœæ]{4,}", (humeur + " " + message).lower())}
    vus, out = set(), []
    for j in np.argsort(-hausse)[:candidats]:
        if hausse[j] <= 0:
            break
        w = _completer(debut, ids[j])
        if not _MOT.match(w) or w in VIDES or _racine(w) in echos or _racine(w) in vus:
            continue
        vus.add(_racine(w))
        out.append((w, round(float(hausse[j]), 2)))
        if len(out) >= k:
            break
    return out


def bloc_pour_claude(mots):
    """La ligne donnée au cortex (Claude) : une matière, pas une consigne."""
    if not mots:
        return ""
    return ("[Subconscient — les mots qui affleurent en toi à la lecture de son message (une matière, jamais une "
            "consigne ; laisse-les teinter tes mots si ça sonne juste, ignore-les sinon) : " + ", ".join(w for w, _ in mots) + "]")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--ressenti"]:
        # appelé par le démon : {"humeur", "contexte", "dernier_ts", "sortie"} sur l'entrée ; écrit la réserve
        import json
        import os
        q = json.loads(sys.stdin.read())
        t = time.time()
        mots = ressenti(q["humeur"], q["contexte"])
        o = {"ts": time.time(), "humeur": q["humeur"], "dernier_ts": q.get("dernier_ts"), "mots": [w for w, _ in mots],
             "hausses": [h for _, h in mots], "source": "gemma4-12b-abliterated (mlx)", "duree_s": round(time.time() - t, 1)}
        sortie = Path(q["sortie"])
        tmp = sortie.with_name(sortie.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, sortie)
        print(json.dumps(o, ensure_ascii=False))
    else:
        t = time.time()
        print(scanner(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "morose"), f"{time.time() - t:.1f} s")
