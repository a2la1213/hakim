"""Le « scanner » du subconscient (demande d'Ahmed, 2026-10-20) : que Claude, le cortex de Hakim, profite de
l'humeur de Gemma, son subconscient, SANS qu'on lui écrive « tu es triste, parle triste ».

Gemma lit le message d'Ahmed deux fois, dans le même cadre : une fois neutre, une fois avec l'humeur du moment.
Aucun texte n'est généré : on compare seulement, à l'endroit où la réponse commencerait, la probabilité de chaque
mot dans les deux lectures. Les mots dont la probabilité MONTE le plus sous l'humeur sont « les mots qui
affleurent » : ils sont donnés à Claude comme une matière (ce qui lui vient à l'esprit), jamais comme une consigne.

Deux passes du réseau sur un texte court : environ une à trois secondes, rien de plus.
(Les vecteurs de pilotage de pilotage.py, eux, ne tiennent pas sur Gemma 4 12B en 4 bits : bilan du 2026-10-20.)
"""
import os
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
            "tellement vraiment assez toujours presque plutôt sensation sensations couleur fond "
            "celle celles ceux".split())                     # (24/10) « celle » remontait dans le ressenti par Ollama
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


# ---- (24/10, piste 3 validée par Ahmed : « on fait la troisième ») le ressenti sur la Gemma d'OLLAMA, déjà en mémoire pour
# l'esprit de fond, au lieu d'une deuxième Gemma 12B chargée en MLX (7,7 Go, le Mac tombait à 10 % de mémoire libre).
# Même cadre, mêmes sondes, même gabarit de Gemma 4 (rendu par son tokenizer) ; Ollama donne les 20 mots suivants les
# plus probables (son maximum) au lieu du vocabulaire entier : la hausse d'un mot absent des 20 de la lecture neutre est
# bornée par le plus faible de ces 20 (une hausse au moins aussi grande). Le chemin MLX reste en repli.
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# (27/10) le démon pense avec Sonnet (ANAMNESE_DAEMON_MODEL) ; le ressenti lit les probabilités de GEMMA : sa variable à lui
MODELE_OLLAMA = os.environ.get("ANAMNESE_RESSENTI_MODEL") or os.environ.get("ANAMNESE_DAEMON_SECOURS", "huihui_ai/gemma-4-abliterated:12b")
GABARIT_GEMMA4 = "<|turn>user\n{cadre}<turn|>\n<|turn>model\n<|channel>thought\n<channel|>"


def _ollama(prompt, n=1, top=20):
    import json
    import urllib.request
    q = {"model": MODELE_OLLAMA, "prompt": prompt, "raw": True, "stream": False, "logprobs": True, "top_logprobs": top,
         "options": {"num_predict": n, "temperature": 0}, "keep_alive": "5m"}
    r = json.loads(urllib.request.urlopen(urllib.request.Request(f"{OLLAMA}/api/generate", data=json.dumps(q).encode(),
                                                                 headers={"Content-Type": "application/json"}), timeout=180).read())
    if r.get("error"):
        raise RuntimeError(r["error"])
    return r


def _suivants_ollama(cadre, sonde):
    """{jeton: log-probabilité} des 20 jetons suivants les plus probables, après le cadre et la sonde."""
    r = _ollama(GABARIT_GEMMA4.format(cadre=cadre) + sonde)
    lp = (r.get("logprobs") or [{}])[0].get("top_logprobs") or []
    return {x["token"]: float(x["logprob"]) for x in lp}


def _completer_ollama(prefixe, piece, max_tokens=3):
    """Un début de mot (« lour ») prolongé par Gemma elle-même jusqu'à la fin du mot."""
    mot = piece.strip()
    suite = _ollama(prefixe + piece, n=max_tokens, top=0).get("response") or ""
    m = re.match(r"^[a-zàâçéèêëîïôûùüÿœæ'-]+", suite, re.I)
    return (mot + (m.group(0) if m else "")).lower()


# Ollama ne rend que les 20 jetons suivants les plus probables : trois sondes de plus élargissent la palette (sinon une
# « tension » ne donnait que « palpable, brute, nette », 24/10)
SONDES_OLLAMA = SONDES_SENSATION + ["Dans mon corps, ce que je sens est", "Le poids de ce que je ressens est",
                                    "La texture de ce que je ressens est"]


def ressenti_ollama(humeur, contexte, k=6, candidats=14, sondes=SONDES_OLLAMA):
    """Comme ressenti(), sur la Gemma d'Ollama."""
    message = " ".join(str(contexte).split())[-1500:]
    teinte_cadre = CADRE.format(humeur=f" Ton humeur en ce moment : {humeur}.", message=message)
    hausse, n_vu = {}, {}
    for s in sondes:
        neutre = _suivants_ollama(CADRE.format(humeur="", message=message), s)
        teinte = _suivants_ollama(teinte_cadre, s)
        plancher = min(neutre.values()) if neutre else -12.0
        for t, lp in teinte.items():
            w = t.strip().lower()
            if not t.startswith(" ") or not re.match(r"^[a-zàâçéèêëîïôûùüÿœæ'-]{2,}$", w) or w in VIDES or lp < -12:
                continue
            hausse[t] = hausse.get(t, 0.0) + lp - neutre.get(t, plancher)
            n_vu[t] = n_vu.get(t, 0) + 1
    moyenne = sorted(((t, h / len(sondes)) for t, h in hausse.items()), key=lambda x: -x[1])
    prefixe = GABARIT_GEMMA4.format(cadre=teinte_cadre) + sondes[0]
    echos = {_racine(w) for w in re.findall(r"[a-zàâçéèêëîïôûùüÿœæ]{4,}", (humeur + " " + message).lower())}
    vus, out = set(), []
    for t, h in moyenne[:candidats]:
        if h <= 0:
            break
        w = _completer_ollama(prefixe, t)
        if not _MOT.match(w) or w in VIDES or _racine(w) in echos or _racine(w) in vus:
            continue
        vus.add(_racine(w))
        out.append((w, round(h, 2)))
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
        source = "gemma4-12b-abliterated (ollama)"
        try:
            if os.environ.get("JARVIS_RESSENTI_MOTEUR", "ollama") != "ollama":
                raise RuntimeError("moteur MLX demandé")
            mots = ressenti_ollama(q["humeur"], q["contexte"])
        except Exception as e:                     # repli : l'ancien chemin MLX (une deuxième Gemma, 7,7 Go)
            print(f"ressenti par Ollama impossible ({type(e).__name__}: {e}) : repli MLX", file=sys.stderr)
            mots, source = ressenti(q["humeur"], q["contexte"]), "gemma4-12b-abliterated (mlx)"
        o = {"ts": time.time(), "humeur": q["humeur"], "dernier_ts": q.get("dernier_ts"), "mots": [w for w, _ in mots],
             "hausses": [h for _, h in mots], "source": source, "duree_s": round(time.time() - t, 1)}
        sortie = Path(q["sortie"])
        tmp = sortie.with_name(sortie.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, sortie)
        print(json.dumps(o, ensure_ascii=False))
    else:
        t = time.time()
        print(scanner(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "morose"), f"{time.time() - t:.1f} s")
