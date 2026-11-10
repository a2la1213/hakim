"""(09/11, Ahmed : « tout ce qui arrive de ses sens traité en temps réel et parallélisé sur tous les cœurs du Mac, comme sa parole » ;
19:29-19:32 : « que tu dissocies ce que disent les autres de mes paroles » ; « reconnaître les signatures vocales en temps réel pendant le
live, et pouvoir les enregistrer à la volée ») L'OREILLE DES VOIX : un petit processus à part, qui ne fait QUE reconnaître qui parle
(l'empreinte WeSpeaker, empreinte_vocale.py, sur le processeur ; ~60-100 Mo, aucun Whisper). Avant, la seule vérification du chemin Azure
passait par l'oreille vive, occupée presque tout le temps par la transcription en direct (« occupée » : pas de vérification du tout).
Elle tourne EN MÊME TEMPS que la transcription (Azure, Whisper), jamais derrière elle.

Point d'entrée unique (prêt pour un orchestrateur) : une ligne JSON par demande sur l'entrée, une ligne par réponse sur la sortie ;
{"pret": true} au démarrage. Demandes :
- {id, op: "bloc", fichier, texte, musique, nouveau_tour} : un morceau de papa transcrit par Azure → {texte étiqueté, voix, moi}
  (empreinte_vocale.etiqueter_bloc : les voix inconnues reçoivent leur numéro temporaire tout de suite) ;
- {id, op: "prevoir", fichier} : calcule les empreintes du morceau pendant qu'Azure le transcrit (le « bloc » qui suit les retrouve) ;
- {id, op: "qui", fichier} : est-ce SA propre voix ? (empreinte_vocale.qui_parle, comme l'oreille vive) ;
- {id, op: "signature", action, personne, voix, proposition, presence} (10/11) : les signatures vocales (voir, ajouter, retirer, valider ou refuser
  une proposition de Hakim ; empreinte_vocale.signature_geste) ;
- {id, op: "fenetres", fichier, cle, musique} : le son du téléphone en cours (un live) : qui parle, fenêtre par fenêtre (1,5 s, pas de
  0,75 s), seulement les fenêtres neuves d'un même bloc (cle) → {fenetres: [[début s, fin s, qui]], voix: [qui…], nouvelles: [qui…]} ;
  pendant une musique (musique: true), seulement les voix déjà connues (papa, les nommées, celles de la salle) : jamais de numéro neuf
  (la musique créait des « voix 56, 63… », 03/11).
Les fichiers sont des WAV PCM 16 bits (n'importe quel taux, ramenés à 16 kHz). Rien de l'audio n'est gardé.
"""
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import empreinte_vocale as E  # noqa: E402

_blocs = {}                      # cle → {"fin": secondes déjà vues, "t": dernière demande}
BLOCS_MAX, BLOC_DUREE_S = 16, 120

# (09/11) « prevoir » : les empreintes d'un morceau calculées PENDANT qu'Azure le transcrit ; « bloc » les retrouve ici (même tranche de son,
# même durée minimale) au lieu de les recalculer : une fois le texte arrivé, seules les règles restent (quelques millisecondes)
_memo, MEMO_MAX = {}, 96
_embedding_vrai = E.embedding


def _embedding_memo(audio, min_s=E.PAROLE_MIN_S):
    a = np.ascontiguousarray(np.asarray(audio, dtype=np.float32))
    k = (hashlib.blake2b(a.tobytes(), digest_size=16).digest(), float(min_s))
    if k in _memo:
        return _memo[k]
    v = _embedding_vrai(a, min_s)
    _memo[k] = v
    while len(_memo) > MEMO_MAX:
        _memo.pop(next(iter(_memo)))
    return v


def prevoir(audio):
    """Les mêmes tranches que etiqueter_bloc (le morceau entier, puis ses fenêtres de 1,5 s sur ce qui sonne, ou ce qui sonne d'un bloc)."""
    a = np.asarray(audio, dtype=np.float32)
    E.embedding(a)
    d0, d1 = E._zone_parlee(a)
    n = 0
    if d1 - d0 >= 2 * E.FENETRE_S:
        p = d0
        while p + E.FENETRE_S <= d1 + 1e-6:
            E.embedding(a[int(p * E.TAUX):int((p + E.FENETRE_S) * E.TAUX)], E.SEGMENT_MIN_S)
            p += E.PAS_S
            n += 1
    elif (d1 - d0) * E.TAUX >= E.SEGMENT_MIN_S * E.TAUX:
        E.embedding(a[int(max(0.0, d0) * E.TAUX):int(max(0.0, d1) * E.TAUX)], E.SEGMENT_MIN_S)
        n = 1
    return {"fenetres": n}


def _audio(fichier):
    return E.lire_wav16(fichier)


def fenetres(audio, cle="", musique=False, maintenant=None):
    """Qui parle dans les fenêtres NEUVES du son en cours (le même bloc revient plus long à chaque passage)."""
    t = time.time() if maintenant is None else maintenant
    for k in [k for k, b in _blocs.items() if t - b["t"] > BLOC_DUREE_S]:
        del _blocs[k]
    if len(_blocs) > BLOCS_MAX:
        for k in sorted(_blocs, key=lambda k: _blocs[k]["t"])[:len(_blocs) - BLOCS_MAX]:
            del _blocs[k]
    b = _blocs.setdefault(str(cle or ""), {"fin": 0.0, "t": t})
    b["t"] = t
    a = np.asarray(audio, dtype=np.float32)
    n, pas = int(E.FENETRE_S * E.TAUX), int(E.PAS_S * E.TAUX)
    debut = int(max(0.0, b["fin"] - (E.FENETRE_S - E.PAS_S)) * E.TAUX) if b["fin"] else 0
    sortie, vus, nouvelles = [], [], []
    E._charger_salle(t)
    if t - E._salle["ts"] > E.SALLE_DUREE_S:
        E._salle["voix"] = []
    E._salle["ts"] = t
    d = E._lire(None)
    papa = (lambda v: E.score_ahmed(v, d)) if d and d.get("moyenne") and len(d.get("vecteurs", [])) >= 2 else (lambda v: -1.0)
    mes = E.moyennes_moi()
    try:
        nommees = E.registre_voix()                       # (10/11) les signatures (papa, les personnes nommées, les voix partagées)
    except (OSError, ValueError):
        nommees = E.S.minimal()                           # illisible : papa par son empreinte, comme avant
    compte = {}
    avant = {x["nom"] for x in E._salle["voix"]} | {str(c.get("nom")) for c in E._salle.get("candidates", []) if c.get("nom")}
    i = debut

    def noter(debut_s, fin_s, q):
        sortie.append([round(debut_s, 2), round(fin_s, 2), q])
        if q not in vus:
            vus.append(q)
        if q.startswith("voix ") and q not in avant and q not in nouvelles:
            nouvelles.append(q)

    while i + n <= len(a):
        v = E.embedding(a[i:i + n], min_s=1.0)
        if v is not None and float(np.sqrt(np.mean(np.square(a[i:i + n])))) >= 0.003:
            q = _qui(v, papa, mes, nommees, musique, t, neuve=False, compte=compte)
            if q:
                noter(i / E.TAUX, (i + n) / E.TAUX, q)
                b.pop("seule", None)
            elif not musique:
                # (09/11, rejoué : une fenêtre à cheval sur deux voix ne ressemble à aucune et créait un faux numéro) une voix NOUVELLE naît de deux
                # fenêtres voisines qui se ressemblent ; une fenêtre seule attend la suivante (gardée d'un passage à l'autre du même bloc)
                seule = b.get("seule")
                if seule is not None and abs(seule[1] - i / E.TAUX) <= E.PAS_S + 1e-6 and float(np.dot(v, seule[0])) >= E.SEUIL_MEME_VOIX:
                    m = seule[0] + v
                    q = _qui(m / (np.linalg.norm(m) or 1.0), papa, mes, nommees, musique, t, neuve=True, compte=compte)
                    if q:
                        noter(seule[1], seule[1] + E.FENETRE_S, q)
                        noter(i / E.TAUX, (i + n) / E.TAUX, q)
                    b.pop("seule", None)
                else:
                    b["seule"] = (v, i / E.TAUX)
        b["fin"] = (i + n) / E.TAUX
        i += pas
    try:
        E._sauver_salle()
    except OSError:
        pass
    E._noter_entendues(compte, {}, t, musique)            # (10/11) les voix des signatures entendues : leur compte
    return {"fenetres": sortie, "voix": vus, "nouvelles": nouvelles}


def _qui(v, papa, mes, nommees, musique, t, neuve=True, compte=None):
    """Les règles d'empreinte_vocale (etiqueter.connu) : soi, une signature (papa, une nommée, ou le doute « papa ou Ali ? » d'une voix
    partagée, 10/11), une voix de la salle, une candidate déjà née, sinon (neuve) une nouvelle candidate numérotée ; None : personne de
    connu (et neuve=False). nommees : le registre des signatures (E.registre_voix())."""
    sm = E.score_moi(v, mes)[0]
    sa = papa(v)
    proches = [(float(np.dot(v, x["c"])), x) for x in E._salle["voix"]]
    s, x = max(proches, key=lambda p: p[0]) if proches else (-1.0, None)
    r = E.S.reconnaitre(v, nommees, papa if sa > -1.0 else None) if nommees else None
    sr = r["score"] if r else -1.0
    if sm >= E.SEUIL_MOI and sm > max(sa, s, sr) + 0.05:
        return "ta propre voix"
    if r:
        if compte is not None:
            compte[r["voix"]] = compte.get(r["voix"], 0) + 1
        q = E.qui_de(r)
        return E.NOM_PAPA if q == "Ahmed" else q
    # pas de « registre inhabituel » ici (le doute rattaché à papa) : au téléphone, papa est rare (un vocal) ; mesuré le 09/11 sur les voix
    # du Mac, une citation arabe d'une autre voix à 0,41 de son empreinte passait pour lui
    if x is not None and s >= E.SEUIL_MEME_VOIX:
        x["c"] = (x["c"] * x["n"] + v) / (x["n"] + 1)
        x["c"] /= (np.linalg.norm(x["c"]) or 1.0)
        x["n"] += 1
        x["m"] = x.get("m", 0) + (1 if musique else 0)
        return x["nom"]
    # une candidate : la plus proche, ou une neuve (jamais pendant une musique), avec son numéro temporaire tout de suite
    cands = [(float(np.dot(v, k["c"])), k) for k in E._salle.get("candidates", [])]
    sk, k = max(cands, key=lambda p: p[0]) if cands else (-1.0, None)
    if k is None or sk < E.SEUIL_MEME_VOIX:
        if musique or not neuve:
            return None
        k = {"c": v, "n": 0, "m": 0, "parole": []}
        E._salle.setdefault("candidates", []).append(k)
    c = k["c"] * k["n"] + v
    k["c"] = c / (np.linalg.norm(c) or 1.0)
    k["n"] += 1
    k["m"] += 1 if musique else 0
    k["parole"].append([t, E.PAS_S])
    k["nom"] = k.get("nom") or E._prochain_numero(papa(v) > -1.0)
    if E._parole(k, t) >= E.CONFIRMER_S:                  # assez parlé : elle entre dans la salle, avec le même numéro
        E._salle["candidates"] = [c for c in E._salle["candidates"] if c is not k]   # par identité (leurs tableaux ne se comparent pas)
        E._salle["voix"].append({"nom": k["nom"], "c": k["c"], "n": k["n"], "m": k["m"]})
    return k["nom"]


def repondre(d):
    op = d.get("op")
    t0 = time.time()
    if op == "bloc":
        r = E.etiqueter_bloc(_audio(str(d["fichier"])), str(d.get("texte") or ""), musique=bool(d.get("musique")),
                             nouveau_tour=d.get("nouveau_tour") is not False)
    elif op == "prevoir":
        r = prevoir(_audio(str(d["fichier"])))
    elif op == "qui":
        r = E.qui_parle(_audio(str(d["fichier"])))
    elif op == "fenetres":
        r = fenetres(_audio(str(d["fichier"])), str(d.get("cle") or ""), bool(d.get("musique")))
    elif op == "signature":                               # (10/11) les gestes de papa sur les signatures (la page Voix)
        r = E.signature_geste(d)
    else:
        r = {"erreur": f"op inconnue : {str(op)[:20]}"}
    return {**r, "ms": int((time.time() - t0) * 1000)}


def main():
    E.embedding = _embedding_memo                         # les empreintes déjà calculées par « prevoir » sont retrouvées
    try:                                                  # (10/11) au démarrage : le registre des signatures (migré la première fois)
        E.registre_voix()
    except Exception as e:  # noqa: BLE001  (sans registre, l'oreille reconnaît comme avant : papa par son empreinte)
        print(f"[oreille des voix] signatures : {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)
    try:
        E.embedding(np.zeros(16000 * 2, dtype=np.float32) + 1e-3, min_s=1.0)   # le modèle chargé d'avance
    except Exception:  # noqa: BLE001  (sans modèle, chaque demande le dira)
        pass
    print(json.dumps({"pret": True}), flush=True)
    for ligne in sys.stdin:
        try:
            d = json.loads(ligne)
        except ValueError:
            continue
        try:
            sortie = repondre(d)
        except Exception as e:  # noqa: BLE001  (une demande ratée ne tue pas l'oreille)
            sortie = {"erreur": str(e)[:200]}
        print(json.dumps({"id": d.get("id"), **sortie}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
