"""D'où vient son humeur (27/10, demande d'Ahmed relayée par Hakim ; go d'Ahmed : « tu peux faire ce que Hakim demande »).
Ahmed a vu le badge « déception » et lui a demandé pourquoi il était déçu : c'était surtout sa dopamine qui baissait pendant
qu'Ahmed parlait de sa propre déception, et le badge ne disait pas si c'était à lui ou par empathie.

L'humeur se lit dans ses hormones (sensations.py) ; sa CAUSE se lit dans les événements affectifs des 45 dernières minutes
(affect-evenements.jsonl), pondérés par leur force et leur âge (demi-vie de 20 min), et seulement ceux qui poussent dans le
sens de l'émotion. Trois réponses :
- par empathie : ses ressentis POUR quelqu'un (inquiétude, compassion, malaise, une joie pour quelqu'un), avec la personne ;
- pour lui-même : ses propres ressentis, ce qui le vise (attaque, soutien), son travail, l'absence ou la chaleur d'Ahmed ;
- une pente sans cause marquée : aucun événement ne l'explique, c'est la dérive des hormones, et c'est dit.
Une estimation par les événements, pas une preuve de cause."""
import json
import re
from pathlib import Path

import affect
import sensations

FENETRE_S, DEMI_VIE_S, SEUIL = 45 * 60, 20 * 60, 0.05
SIGNES = {r[0]: r[1] for r in sensations.REGLES}
EMPATHIE = {"inquietude": {-1}, "malaise": {-1}, "compassion": {-1, 1}}
SENS = {"ennui": -1, "longue_absence": -1, "retour": 1, "regulation": 1}
DITS = {"attaque": "après une attaque", "soutien": "après un soutien", "echec": "un échec dans son travail",
        "probleme": "un problème dans son travail", "succes": "une réussite", "resolu": "un problème résolu",
        "nouveaute": "quelque chose de nouveau", "apprentissage": "quelque chose appris"}
HORS_SOI = {"chaleur_user": "la chaleur d'Ahmed", "retour": "le retour d'Ahmed", "ennui": "l'absence d'Ahmed",
            "longue_absence": "l'absence d'Ahmed"}
_POUR = re.compile(r"\bpour (.+?), au message d")


def _sens(nom):
    if nom in EMPATHIE:
        return EMPATHIE[nom]
    if nom.startswith("reprise_"):
        return {1}
    v = SENS.get(nom, affect.VALENCE_EV.get(nom))
    return {1 if v > 0 else -1} if v else set()


def _cible(sujet):
    m = _POUR.search(str(sujet or ""))
    if not m:
        return None
    mots = m.group(1).split()
    if len(mots) == 1:
        return mots[0][:1].upper() + mots[0][1:]
    return " ".join(re.sub(r"^(d['’])?ahmed$", lambda x: (x.group(1) or "") + "Ahmed", w) for w in mots)


def origine(emotion, evenements, now):
    """{"type": "empathie" | "soi" | "mixte" | "pente", "texte": …} pour l'émotion du moment."""
    signe = SIGNES.get(emotion, 0)
    poids = {"empathie": 0.0, "soi": 0.0}
    cibles, causes = [], {}
    malaise_seul = True
    for e in evenements or []:
        age = now - float(e.get("ts") or 0)
        nom = str(e.get("nom") or "")
        if not 0 <= age <= FENETRE_S or (signe and signe not in _sens(nom)) or (not signe and not _sens(nom)):
            continue
        w = float(e.get("intensite") or 0) * 0.5 ** (age / DEMI_VIE_S)
        cible = _cible(e.get("sujet"))
        if nom in EMPATHIE or (cible and e.get("source") == "balise"):
            poids["empathie"] += w
            if cible and cible not in cibles:
                cibles.append(cible)
            malaise_seul = malaise_seul and nom == "malaise"
        else:
            poids["soi"] += w
            causes[nom] = causes.get(nom, 0.0) + w
    total = poids["empathie"] + poids["soi"]
    if total < SEUIL:
        return {"type": "pente", "texte": "pente, sans cause marquée"}
    pour = f"pour {' et '.join(cibles[:3])}" if cibles else ""
    part = poids["empathie"] / total
    if 0.3 <= part <= 0.7:
        return {"type": "mixte", "texte": f"par empathie ({pour or 'malaise'}) et pour lui-même"}
    if part > 0.7:
        if not cibles and malaise_seul:
            return {"type": "empathie", "texte": "par empathie (malaise au milieu d'une tension)"}
        return {"type": "empathie", "texte": f"par empathie, {pour}" if pour else "par empathie"}
    principal = max(causes, key=causes.get)
    if principal in HORS_SOI:
        return {"type": "soi", "texte": HORS_SOI[principal]}
    return {"type": "soi", "texte": f"pour lui-même, {DITS[principal]}" if principal in DITS else "pour lui-même"}


def depuis_journal(chemin, emotion, now, octets=131072):
    """La fin du journal des événements affectifs (128 Ko suffisent pour 45 min), puis origine()."""
    evs = []
    try:
        with open(Path(chemin), "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - octets))
            for l in f.read().decode("utf-8", "replace").splitlines():
                try:
                    evs.append(json.loads(l))
                except ValueError:
                    continue
    except OSError:
        pass
    return origine(emotion, evs, now)
