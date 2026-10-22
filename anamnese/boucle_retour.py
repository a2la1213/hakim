"""La boucle de retour de la consolidation, niveau 1 MINIMAL (accord d'Ahmed, 2026-10-22 à 12:49 : « que le compteur de
nuits démarre ce soir »). Chaque nuit, elle ENREGISTRE SEULEMENT : rien n'est modifié dans la mémoire. Les actions
(renforcer, pénaliser, variantes, nuits témoins) viendront après quelques nuits de données, avec un nouvel accord.

Une ligne JSON par événement (format de Hakim, dossier du 22/10) :
  {"t", "type": "propose|utilise|rate|correction|juge", "souvenir", "message", "source", "score_recouvrement"}
- propose : chaque souvenir du balayage automatique fait pour un message d'Ahmed (rappel.jsonl du cockpit) ;
- utilise : un souvenir proposé pour ce message et relu par Hakim avec memory_lire pendant ce tour (source « lecture ») ;
- indice : au moins SEUILS["mots"] mots RARES du souvenir reviennent dans sa réponse sans être dans le message d'Ahmed
  (source « recouvrement », score = part des mots rares repris) ; PAS un usage (juge du 22/10, ci-dessous) ;
- rate : noté par Hakim (rappel_rate, source « hakim »), ou recherche manuelle hors balayage (source « recall_manuel »,
  un indice) ;
- correction : le message suivant d'Ahmed commence par une correction (motifs figés ci-dessous) : chaque souvenir
  utilisé dans la réponse corrigée ;
- juge : un résultat marqué important (importants.jsonl) ; le verdict du juge n'est pas encore structuré.
SEUILS et motifs FIGÉS avant la première nuit (empreinte dans nuits.jsonl). Fichiers : ~/AIOS/jarvis/boucle/.
"""
import hashlib
import json
import re
import time
from pathlib import Path

import rappel

JARVIS = Path.home() / "AIOS" / "jarvis"
DOSSIER = JARVIS / "boucle"
LECTURES = DOSSIER / "lectures.jsonl"           # écrit par mcp_server.memory_lire (Hakim seulement)
# « mots » : au moins 2 mots RARES du souvenir (présents dans au plus 1 % des souvenirs, 3 au moins) repris dans la réponse
# sans être dans le message d'Ahmed. Essai à blanc du 22/10 : avec tous les mots de 5 lettres, 948 « utilisés » sur 1 745
# proposés (54 %, bien trop : les mots du métier reviennent partout) ; d'où la rareté.
# Puis un juge à l'aveugle (Sonnet, 60 cas tirés de la journée) : le souvenir sert-il VRAIMENT à la réponse ? Mots rares
# repris : 2 vrais sur 20 ; mots de 5 lettres : 0 sur 20 ; aucun mot : 0 sur 20. Le recouvrement de mots n'est donc PAS
# un signal d'usage : « utilise » ne vient que de la relecture (memory_lire) ; le recouvrement est noté à part, « indice ».
SEUILS = {"mots": 2, "longueur_mot": 5, "rare_part": 0.01, "rare_min": 3, "fenetre_balayage_s": 120, "debut_correction": 80}
CORRECTION = re.compile(r"\b(non,? c'?est pas (ça|ca|ce que)|c'?est faux|t'?as faux|tu as faux|tu te trompes|pas du tout|"
                        r"n'?importe quoi|c'?est pas vrai|tu confonds|pas exactement|t'?as rien compris|mais non)\b", re.I)


def empreinte_regles():
    return hashlib.sha256(json.dumps([SEUILS, CORRECTION.pattern], sort_keys=True).encode()).hexdigest()[:16]


def _jsonl(f):
    out = []
    try:
        for l in Path(f).read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def mots(t):
    return {m for m in re.findall(r"[\wàâçéèêëîïôûùüÿœ'-]+", str(t or "").lower())
            if len(m.strip("'-")) >= SEUILS["longueur_mot"] and m not in rappel.MOTS_VIDES}


def noter_lecture(ids, maintenant=None, fichier=None):
    f = Path(fichier or LECTURES)
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": time.time() if maintenant is None else maintenant, "ids": [int(i) for i in ids][:10]}) + "\n")


def tours(conversation):
    """[(message d'Ahmed, réponse de Hakim, ts du message, ts du message suivant d'Ahmed, texte suivant)]"""
    msgs = [m for m in conversation.get("messages", []) if isinstance(m, dict)]
    out = []
    for i, m in enumerate(msgs):
        if m.get("qui") != "u":
            continue
        rep = next((x for x in msgs[i + 1:] if x.get("qui") != "u"), None)
        suiv = next((x for x in msgs[i + 1:] if x.get("qui") == "u"), None)
        t = float(m.get("ts") or m.get("id") or 0) / 1000
        out.append((m, rep, t, float(suiv.get("ts") or suiv.get("id") or 0) / 1000 if suiv else None, (suiv or {}).get("texte", "")))
    return out


def evenements(mem, depuis, jusqua, conversation=None, balayages=None, lectures=None, rates=None, importants=None):
    """Les événements de la période [depuis, jusqua[ (secondes)."""
    conv = conversation if conversation is not None else _lire_json(JARVIS / "conversation.json")
    bal = balayages if balayages is not None else _jsonl(JARVIS / "rappel.jsonl")
    lec = lectures if lectures is not None else _jsonl(LECTURES)
    rat = rates if rates is not None else _jsonl(JARVIS / "rappels-rates.jsonl")
    imp = importants if importants is not None else _jsonl(JARVIS / "importants.jsonl")
    out = []
    contenus = {}
    rares = _rarete(mem)

    def contenu(eid):
        if eid not in contenus:
            r = mem.db.execute("SELECT content FROM episodes WHERE id = ?", (eid,)).fetchone()
            contenus[eid] = r[0] if r else ""
        return contenus[eid]
    for m, rep, t, t_suiv, texte_suiv in tours(conv):
        if not (depuis <= t < jusqua):
            continue
        mid = str(m.get("id"))
        b = min((x for x in bal if abs(x.get("ts", 0) / 1000 - t) <= SEUILS["fenetre_balayage_s"]),   # vide compris
                key=lambda x: abs(x.get("ts", 0) / 1000 - t), default=None)
        proposes = [int(i) for i in (b or {}).get("ids", [])]
        fin_tour = t_suiv if t_suiv else t + 3600
        lus = {int(i) for x in lec if t - 5 <= x.get("ts", 0) < fin_tour for i in x.get("ids", [])}
        r_mots, a_mots = mots((rep or {}).get("texte", "")), mots(m.get("texte", ""))
        utilises = []
        for eid in proposes:
            out.append({"t": t, "type": "propose", "souvenir": eid, "message": mid, "source": "balayage", "score_recouvrement": None})
            sm = {w for w in mots(contenu(eid)) if rares(w)}
            repris = (sm & r_mots) - a_mots
            score = round(len(repris) / len(sm), 3) if sm else 0.0
            if eid in lus:
                utilises.append(eid)
                out.append({"t": t, "type": "utilise", "souvenir": eid, "message": mid, "source": "lecture", "score_recouvrement": score})
            elif len(repris) >= SEUILS["mots"]:                  # un INDICE seulement (juge du 22/10 : 2 vrais sur 20)
                out.append({"t": t, "type": "indice", "souvenir": eid, "message": mid, "source": "recouvrement", "score_recouvrement": score})
        if utilises and t_suiv and CORRECTION.search(str(texte_suiv)[:SEUILS["debut_correction"]]):
            for eid in utilises:
                out.append({"t": t_suiv, "type": "correction", "souvenir": eid, "message": mid, "source": "ahmed", "score_recouvrement": None})
    for x in rat:
        ts = x.get("ts", 0)
        if not (depuis <= ts < jusqua):
            continue
        if x.get("type") == "rate":
            out += [{"t": ts, "type": "rate", "souvenir": int(i), "message": None, "source": "hakim", "score_recouvrement": None} for i in x.get("ids", [])]
        elif x.get("type") == "recherche":
            out += [{"t": ts, "type": "rate", "souvenir": int(i), "message": None, "source": "recall_manuel", "score_recouvrement": None}
                    for i in x.get("hors_balayage", [])]
    for x in imp:
        if depuis <= x.get("ts", 0) < jusqua:
            out.append({"t": x["ts"], "type": "juge", "souvenir": None, "message": None, "source": "marque_important", "score_recouvrement": None,
                        "id": x.get("id")})
    return sorted(out, key=lambda e: e["t"])


def _rarete(mem):
    """Une fonction mot → vrai s'il est RARE dans la mémoire (au plus 1 % des souvenirs du vécu et du savoir, 3 au moins)."""
    df, n = {}, 0
    marques = ",".join("?" * len(rappel.ROLES))
    for (c,) in mem.db.execute(f"SELECT content FROM episodes WHERE role IN ({marques})", rappel.ROLES):
        n += 1
        for w in mots(c):
            df[w] = df.get(w, 0) + 1
    seuil = max(SEUILS["rare_min"], SEUILS["rare_part"] * n)
    return lambda w: df.get(w, 0) <= seuil


def _lire_json(f):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def nuit(mem, maintenant=None, dossier=None, **sources):
    """La passe de la nuit : les événements depuis la dernière nuit, écrits, et une ligne de bilan. Rend le bilan."""
    maintenant = time.time() if maintenant is None else maintenant
    d = Path(dossier or DOSSIER)
    d.mkdir(parents=True, exist_ok=True)
    nuits = _jsonl(d / "nuits.jsonl")
    depuis = nuits[-1]["jusqua"] if nuits else maintenant - 86400
    ev = evenements(mem, depuis, maintenant, **sources)
    with (d / "evenements.jsonl").open("a", encoding="utf-8") as h:
        for e in ev:
            h.write(json.dumps(e, ensure_ascii=False) + "\n")
    compte = lambda typ, src=None: sum(1 for e in ev if e["type"] == typ and (src is None or e["source"] == src))
    p, u = compte("propose"), compte("utilise")
    b = {"nuit": len(nuits) + 1, "date": time.strftime("%Y-%m-%d", time.localtime(maintenant)), "depuis": depuis, "jusqua": maintenant,
         "messages": len({e["message"] for e in ev if e["type"] == "propose"}), "proposes": p, "utilises": u,
         "utilises_lecture": compte("utilise", "lecture"), "indices_recouvrement": compte("indice", "recouvrement"),
         "rates_hakim": compte("rate", "hakim"), "rates_indices": compte("rate", "recall_manuel"), "corrections": compte("correction"),
         "juge": compte("juge"), "taux_utilise": round(u / p, 3) if p else None, "regles": empreinte_regles()}
    with (d / "nuits.jsonl").open("a", encoding="utf-8") as h:
        h.write(json.dumps(b, ensure_ascii=False) + "\n")
    return b


def resume(dossier=None):
    n = _jsonl(Path(dossier or DOSSIER) / "nuits.jsonl")
    if not n:
        return "Ta boucle de retour (niveau 1, elle note seulement) : aucune nuit encore."
    x = n[-1]
    return (f"Ta boucle de retour (niveau 1, elle note seulement) : {len(n)} nuit(s) ; la dernière : {x['messages']} message(s), "
            f"{x['utilises']}/{x['proposes']} souvenirs proposés utilisés, {x['rates_hakim']} raté(s) noté(s), {x['corrections']} correction(s) d'Ahmed.")
