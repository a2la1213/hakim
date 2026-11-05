"""Son ribosome intelligent (05/11, Ahmed : « et si tous ses paramètres étaient réglables, mais aussi automatiquement réglables par Hakim
lui-même et ses Mini Hakim / Super Hakim ; s'il pouvait ajuster lui-même au fur et à mesure du temps ; un bouton « ribosome intelligent »,
et Hakim apprendrait à l'utiliser »).

- bilan : ce que ses mesures disent (pistes.jsonl, voix-diagnostic.jsonl) sur une fenêtre : pensées passées sans tri (panne), « rien »,
  mots gardés, temps avant sa voix, morceaux sautés, coupures de papa.
- ajuster : ses réglages, bornés comme ceux de papa ; refusé si l'interrupteur est éteint ; une clé que papa a réglée il y a moins de 30 min
  passe avant ; noté avec sa raison (ribosome-ajustements.jsonl) ; le réglage enregistré de son mode du moment apprend avec lui.
- effets : ses derniers réglages, avec le bilan des 15 min d'avant et d'après (de quoi apprendre)."""
import json
import os
import statistics
import time
from pathlib import Path

# les mêmes bornes que la page Réglages (cockpit : /api/ribosome/reglage, /api/corps/reglages)
BORNES = {"choix_ms": (0, 6000, 1), "stringence": (1, 5, 1), "plafond_mots": (5, 400, 1), "plafond_paquets": (1, 100, 1),
          "plafond_silence_s": (5, 600, 1), "lecteur_max": (1, 25, 1), "contexte": (100, 3000, 1), "relais_ribosomes": (1, 8, 1),
          "relais_pct": (10, 100, 1), "sauter_suite_ms": (300, 5000, 1), "sauter_passe_s": (1, 15, 0.5), "lire_apres_silence_ms": (0, 5000, 1)}
CLES_CORPS = ("sauter_suite_ms", "sauter_passe_s", "lire_apres_silence_ms")
PAPA_PASSE_AVANT_MS = 30 * 60_000
FENETRE_EFFET_MS = 15 * 60_000


def borner(cle, v):
    if cle not in BORNES:
        return None
    lo, hi, pas = BORNES[cle]
    x = min(hi, max(lo, float(v)))
    x = round(x / pas) * pas
    return int(x) if pas == 1 else x


def _lignes(lignes):
    for l in lignes:
        if isinstance(l, dict):
            yield l
            continue
        try:
            d = json.loads(l)
        except (ValueError, TypeError):
            continue
        if isinstance(d, dict):
            yield d


def bilan(pistes, voix, de_ms, a_ms):
    paquets = [d for d in _lignes(pistes) if "ribosome" in d and "vitesse_ms" in d and not d.get("source") and de_ms <= d.get("t", 0) < a_ms]
    lus = [d for d in paquets if d.get("choisi") not in ("panne", "direct")]
    ev = [d for d in _lignes(voix) if de_ms <= d.get("t", 0) < a_ms]
    dits = sorted(d["t"] for d in ev if d.get("e") == "ribosome_dit")
    sorties = sorted(d["t"] for d in ev if d.get("e") == "sortie_voix")
    attentes = []
    for t in dits:
        s = next((x for x in sorties if x >= t), None)
        if s is not None and s - t < 30_000:
            attentes.append(s - t)
    n = len(paquets)
    return {"paquets": n,
            "panne": sum(1 for d in paquets if d.get("choisi") == "panne") / n if n else None,
            "rien": sum(1 for d in lus if not str(d.get("garde") or "").strip()) / len(lus) if lus else None,
            "mots": statistics.mean(len(str(d.get("garde") or "").split()) for d in lus) if lus else None,
            "lu_ms": statistics.median(d.get("ms", 0) for d in lus) if lus else None,
            "voix_ms": statistics.median(attentes) if attentes else None,
            "sautes": sum(int(d.get("sautes") or 0) for d in ev if d.get("e") == "passe_saute"),
            "suites_sautees": sum(1 for d in ev if d.get("e") == "suite_sautee"),
            "coupures": sum(1 for d in ev if d.get("e") == "coupure_au_chunk")}


def _pc(x):
    return "?" if x is None else f"{round(x * 100)} %"


def _s(ms):
    return "?" if ms is None else f"{ms / 1000:.1f} s".replace(".0 s", " s").replace(".", ",")


def texte(b):
    if not b["paquets"]:
        return "Aucun paquet lu par ton ribosome sur cette période."
    return (f"{b['paquets']} paquets lus : {_pc(b['panne'])} passés sans tri (tes lecteurs pas à temps), {_pc(b['rien'])} de « rien », "
            f"{'?' if b['mots'] is None else round(b['mots'], 1)} mots gardés par paquet, lus en {_s(b['lu_ms'])} ; ta voix part {_s(b['voix_ms'])} "
            f"après l'envoi ; {b['sautes']} morceaux passés sautés, {b['suites_sautees']} suites sautées (papa te répondait), "
            f"{b['coupures']} fois papa a parlé sur toi.")


def _lire(f, defaut):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def _ecrire(f, o):
    f = Path(f)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(o, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, f)


def ajuster(dossier, changements, raison, maintenant=None):
    """dossier : ~/AIOS/jarvis ; changements : {clé: valeur}. Rend {fait: {clé: [avant, après]}, refuse: {clé: pourquoi}, eteint}."""
    d = Path(dossier)
    maintenant = int(time.time() * 1000) if maintenant is None else maintenant
    corps = _lire(d / "corps-reglages.json", {})
    corps = corps if isinstance(corps, dict) else {}
    if corps.get("ribosome_intelligent") is False:
        return {"fait": {}, "refuse": {}, "eteint": True}
    rib = _lire(d / "ribosome-reglage.json", {})
    rib = rib if isinstance(rib, dict) else {}
    papa = {}
    for a in _lignes((d / "ribosome-ajustements.jsonl").read_text(encoding="utf-8").splitlines() if (d / "ribosome-ajustements.jsonl").exists() else []):
        if a.get("par") == "papa":
            for k in a.get("cles") or []:
                papa[k] = max(papa.get(k, 0), int(a.get("ts") or 0))
    fait, refuse = {}, {}
    for k, v in (changements or {}).items():
        b = borner(k, v)
        if b is None:
            refuse[k] = "inconnu"
            continue
        if maintenant - papa.get(k, 0) < PAPA_PASSE_AVANT_MS:
            refuse[k] = "papa l'a réglé il y a moins de 30 min"
            continue
        cible = corps if k in CLES_CORPS else rib
        avant = cible.get(k)
        if avant == b:
            continue
        cible[k] = b
        fait[k] = [avant, b]
    if fait:
        if any(k not in CLES_CORPS for k in fait):
            rib.update({"ts": maintenant / 1000, "par": "hakim (ribosome intelligent)"})
            _ecrire(d / "ribosome-reglage.json", rib)
        if any(k in CLES_CORPS for k in fait):
            _ecrire(d / "corps-reglages.json", corps)
        mode = (_lire(d / "mode-courant.json", {}) or {}).get("profil")
        profils = _lire(d / "reglages-profils.json", None)
        if mode and isinstance(profils, list):
            for p in profils:
                if isinstance(p, dict) and p.get("nom") == mode:
                    for k, (_, b) in fait.items():
                        p.setdefault("corps" if k in CLES_CORPS else "ribosome", {})[k] = b
                    p["ts"] = maintenant
            _ecrire(d / "reglages-profils.json", profils)
        with open(d / "ribosome-ajustements.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": maintenant, "par": "hakim", "mode": mode, "fait": fait, "raison": str(raison or "")[:300]},
                               ensure_ascii=False) + "\n")
    return {"fait": fait, "refuse": refuse, "eteint": False}


def effets(ajustements, pistes, voix, maintenant):
    """Ses réglages (les 5 derniers), chacun avec le bilan des 15 min d'avant et d'après."""
    pistes, voix = list(pistes), list(voix)
    out = []
    for a in [x for x in _lignes(ajustements) if x.get("par") == "hakim"][-5:]:
        t = int(a.get("ts") or 0)
        out.append({"ts": t, "fait": a.get("fait"), "raison": a.get("raison"),
                    "avant": bilan(pistes, voix, t - FENETRE_EFFET_MS, t),
                    "apres": bilan(pistes, voix, t, min(maintenant, t + FENETRE_EFFET_MS))})
    return out


# (05/11, Ahmed : « il faut bien qu'il ait le retour de chaque petit réglage, pour qu'il ajuste correctement ») chaque réglage qu'il fait lui
# revient tout seul, par son courrier, dès qu'il est mesurable : 20 paquets lus depuis (ou 15 min et 5 paquets), coupé au réglage suivant
# pour ne pas mélanger deux effets ; comparé à la même durée juste avant ; une heure sans assez de paroles : « pas mesurable »
RETOUR_PAQUETS = 20
RETOUR_MIN_PAQUETS = 5
RETOUR_MAX_MS = 60 * 60_000


def _fleche(avant, apres, pc=False, s=False):
    f = _pc if pc else (_s if s else (lambda x: "?" if x is None else (str(round(x, 1)).replace(".", ",") if isinstance(x, float) else str(x))))
    return f"{f(avant)} → {f(apres)}"


def texte_retour(a, avant, apres):
    quand = time.strftime("%H:%M", time.localtime(int(a.get("ts") or 0) / 1000))
    fait = ", ".join(f"{k} {x} → {y}" for k, (x, y) in (a.get("fait") or {}).items())
    raison = f", « {a['raison']} »" if a.get("raison") else ""
    return (f"Retour de ton réglage de {quand} ({fait}{raison}), sur {apres['paquets']} paquets lus depuis, comparés à la même durée juste "
            f"avant ({avant['paquets']} paquets) : sans tri {_fleche(avant['panne'], apres['panne'], pc=True)}, « rien » "
            f"{_fleche(avant['rien'], apres['rien'], pc=True)}, mots gardés par paquet {_fleche(avant['mots'], apres['mots'])}, ta voix après "
            f"l'envoi {_fleche(avant['voix_ms'], apres['voix_ms'], s=True)}, morceaux passés sautés {_fleche(avant['sautes'], apres['sautes'])}, "
            f"papa sur toi {_fleche(avant['coupures'], apres['coupures'])}. À toi de juger : garder, revenir en arrière, ou essayer autre chose.")


def retours_dus(ajustements, pistes, voix, maintenant, rendus=()):
    """[(ts, texte)] : ses réglages mesurables, pas encore rendus."""
    pistes, voix = list(pistes), list(voix)
    t_paquets = sorted(d["t"] for d in _lignes(pistes) if "ribosome" in d and "vitesse_ms" in d and not d.get("source"))
    siens = [x for x in _lignes(ajustements) if x.get("par") == "hakim" and x.get("fait")][-20:]
    rendus = set(rendus or ())
    out = []
    for k, a in enumerate(siens):
        ts = int(a.get("ts") or 0)
        if ts in rendus:
            continue
        suivant = int(siens[k + 1]["ts"]) if k + 1 < len(siens) else None
        apres = [t for t in t_paquets if t >= ts and (suivant is None or t < suivant)]
        if len(apres) >= RETOUR_PAQUETS:
            fin = apres[RETOUR_PAQUETS - 1] + 1
        elif (suivant is not None or maintenant - ts >= FENETRE_EFFET_MS) and len(apres) >= RETOUR_MIN_PAQUETS:
            fin = suivant if suivant is not None else maintenant
        elif maintenant - ts >= RETOUR_MAX_MS or (suivant is not None and len(apres) < RETOUR_MIN_PAQUETS):
            quand = time.strftime("%H:%M", time.localtime(ts / 1000))
            out.append((ts, f"Ton réglage de {quand} n'est pas mesurable : trop peu de paroles lues depuis ({len(apres)} paquets)."))
            continue
        else:
            continue
        out.append((ts, texte_retour(a, bilan(pistes, voix, ts - (fin - ts), ts), bilan(pistes, voix, ts, fin))))
    return out


def rendre_retours(dossier, maintenant=None, envoyer=None):
    """Envoie à Hakim les retours dus (courrier), et les note (ribosome-retours.json). Rend le nombre envoyé."""
    d = Path(dossier)
    maintenant = int(time.time() * 1000) if maintenant is None else maintenant
    if not (d / "ribosome-ajustements.jsonl").exists():
        return 0

    def queue(nom, n=20000):
        try:
            return (d / nom).read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
        except OSError:
            return []
    etat = _lire(d / "ribosome-retours.json", {})
    etat = etat if isinstance(etat, dict) else {}
    rendus = [int(x) for x in etat.get("rendus") or []]
    dus = retours_dus(queue("ribosome-ajustements.jsonl", 400), queue("pistes.jsonl"), queue("voix-diagnostic.jsonl", 40000), maintenant, rendus)
    if not dus:
        return 0
    if envoyer is None:
        import courrier

        def envoyer(texte):
            courrier.envoyer("hakim", texte, "🧬 Retour de ton réglage du ribosome", de="claude-code", autonome=True)
    for ts, t in dus:
        envoyer(t)
        rendus.append(ts)
    _ecrire(d / "ribosome-retours.json", {"rendus": rendus[-200:]})
    return len(dus)


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["retours"]:
        print(rendre_retours(Path.home() / "AIOS" / "jarvis"))
