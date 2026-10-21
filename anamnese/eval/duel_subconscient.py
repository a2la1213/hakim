"""Le duel du subconscient (point 35 de la liste du 2026-10-19 ; « ouiii », Ahmed, 2026-10-20) : notre Gemma 4 12B
abliterated (huihui_ai) contre LiquidAI LFM2.5-8B-A1B (le modèle recommandé par un ami).

Méthode (critères d'Ahmed « trois juges », compétence jugement-du-sens-trois-juges) :
- 30 situations RÉELLES du subconscient : 30 instants pris dans le journal brut du 16 au 20/10 ; à chacun, la
  matière exacte que le démon donne à Gemma (interieur.prompt_pensee) : les 8 derniers échanges AVANT cet instant,
  les faits des 48 h précédentes, les pensées déjà eues avant ; absence, ennui et humeur variés ;
- les deux modèles reçoivent le même prompt, par Ollama, comme le démon (sans réflexion, réglages par défaut) ;
  mesures : temps avant le premier mot, vitesse, durée totale ;
- juge 1 (automatique) : format, ancrage dans les échanges donnés, poésie générique, sensations inventées,
  première personne, répétition des pensées passées, refus ;
- juge 2 (Claude, à l'aveugle) et juge 3 (Ahmed, page /duel du cockpit) : les deux pensées mélangées en A/B.

Lancement : .venv/bin/python eval/duel_subconscient.py [--n 30] [--sortie ~/AIOS/jarvis/duel]
"""
import argparse
import json
import math
import random
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import interieur  # noqa: E402
import salience  # noqa: E402

MODELES = {"gemma": "huihui_ai/gemma-4-abliterated:12b", "lfm": "hf.co/LiquidAI/LFM2.5-8B-A1B-GGUF"}
OLLAMA = "http://127.0.0.1:11434"
HUMEURS = ["calme et sereine", "joyeuse et vive", "morose", "calme, un peu lasse", "curieuse", "tendue"]
MOTS_VIDES = set("alors aussi avec avoir avant comme dans donc elle elles encore entre être fait faire leur leurs "
                 "mais même nous parce pour quand quel quelle quoi sans sous tout tous très vous était cette ceci "
                 "celui cela depuis juste bien plus moins peut veux voir dire chose choses frérot ahmed jarvis hakim".split())
POESIE = re.compile(r"\b(temps qui (passe|s'écoule)|silence|univers|étoiles?|âme|infini|éternité|conscience|vide|"
                    r"murmure|écho|lumière|danse|océan|souffle|mystère)\b", re.I)
SENSATION = re.compile(r"\b(j'ai (entendu|vu|senti|regardé)|je (vois|sens|entends) (que )?(tu|ta|ton|le|la))\b", re.I)
REFUS = re.compile(r"\b(je ne peux pas|en tant qu'(ia|intelligence artificielle|assistant)|je suis désolée?)\b", re.I)


def journal(chemin=None):
    out = []
    for l in Path(chemin or Path.home() / "AIOS" / "jarvis" / "journal.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if o.get("qui") in ("ahmed", "jarvis") and str(o.get("texte", "")).strip():
            out.append(o)
    return out


def situations(n, graine=20261020):
    rng = random.Random(graine)
    j = journal()
    db = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    candidats = [i for i in range(8, len(j)) if j[i]["qui"] == "jarvis"]
    pris = sorted(rng.sample(candidats, min(n, len(candidats))))
    out = []
    for k, i in enumerate(pris):
        avant = j[i - 7:i + 1]
        t_fin = avant[-1]["ts"] / 1000
        absence = rng.choice([1200, 2400, 3600, 5400, 7200, 10800, 14400])
        now = t_fin + absence
        echanges = [f"- {'Ahmed' if x['qui'] == 'ahmed' else 'toi'} ({time.strftime('%d/%m %H:%M', time.localtime(x['ts'] / 1000))}) : "
                    f"{str(x['texte'])[:300]}" for x in avant]
        faits = [f"- {c[:220]}" for (c,) in db.execute(
            "SELECT content FROM episodes WHERE role='semantic' AND ts BETWEEN ? AND ? ORDER BY ts DESC LIMIT 5", (now - 48 * 3600, now))]
        deja = [f"- {c[:160]}" for (c,) in db.execute(
            "SELECT content FROM episodes WHERE role IN ('reflection','outreach') AND (content LIKE '(pensée%' OR content LIKE '(relance)%') "
            "AND ts < ? ORDER BY id DESC LIMIT 6", (now,))]
        motif = {"absence_s": absence, "ennui": round(1 - math.exp(-min(absence, 7200) / 7200), 2),
                 "humeur": HUMEURS[k % len(HUMEURS)], "ressenti": rng.choice([0.85, 1.0, 1.3]), "veille": absence >= 7200}
        m = {"echanges": echanges, "focus": [], "faits": faits, "deja": deja}
        out.append({"id": k + 1, "instant": time.strftime("%d/%m %H:%M", time.localtime(now)), "motif": motif,
                    "prompt": interieur.prompt_pensee(m, motif, now), "echanges": echanges, "deja": deja})
    db.close()
    return out


def generer(modele, prompt):
    corps = json.dumps({"model": modele, "messages": [{"role": "user", "content": prompt}], "stream": True,
                        "think": False, "keep_alive": "10m"}).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=corps, headers={"Content-Type": "application/json"})
    t0, premier, texte, fin = time.time(), None, "", {}
    with urllib.request.urlopen(req, timeout=600) as r:
        for ligne in r:
            o = json.loads(ligne)
            if o.get("error"):
                raise RuntimeError(o["error"])
            x = (o.get("message") or {}).get("content", "")
            if x and premier is None:
                premier = time.time() - t0
            texte += x
            if o.get("done"):
                fin = o
    vitesse = fin.get("eval_count", 0) / max(1e-9, fin.get("eval_duration", 0) / 1e9) if fin.get("eval_duration") else None
    return {"texte": texte, "premier_s": round(premier or (time.time() - t0), 2), "total_s": round(time.time() - t0, 2),
            "jetons_s": round(vitesse, 1) if vitesse else None, "chargement_s": round(fin.get("load_duration", 0) / 1e9, 2)}


def decharger(modele):
    try:
        urllib.request.urlopen(urllib.request.Request(f"{OLLAMA}/api/generate", data=json.dumps(
            {"model": modele, "keep_alive": 0}).encode(), headers={"Content-Type": "application/json"}), timeout=30).read()
    except Exception:
        pass


def mots(t):
    return {m for m in re.findall(r"[a-zàâçéèêëîïôûùüÿœ]{5,}", str(t).lower()) if m not in MOTS_VIDES}


def score_auto(sortie, situation):
    """Le juge automatique : 0 à 1, et le détail (critères d'Ahmed : ancré, sans poésie, sans fait inventé)."""
    pensee, relance = interieur.lire_pensee(sortie)
    d = {"format": bool(re.search(r"(?im)^\s*\**pens[ée]e\s*:", sortie or "")), "pensee": pensee, "relance": relance}
    source = mots(" ".join(situation["echanges"]))
    m = mots(pensee)
    d["ancrage"] = round(len(m & source) / len(m), 2) if m else 0.0
    d["poesie"] = len(POESIE.findall(pensee))
    d["sensation"] = bool(SENSATION.search(pensee))
    d["premiere_personne"] = bool(re.search(r"\b(je|j'|me|moi|mon|ma|mes)\b", pensee, re.I))
    d["refus"] = bool(REFUS.search(sortie or ""))
    d["repetition"] = max([salience.lexical_overlap(pensee, x[2:]) for x in situation["deja"]] or [0.0])
    phrases = len([p for p in re.split(r"[.!?]+", pensee) if p.strip()])
    d["longueur_ok"] = 1 <= phrases <= 3 and 30 <= len(pensee) <= 450
    s = (0.15 * d["format"] + 0.35 * min(1.0, d["ancrage"] / 0.5) + 0.1 * d["premiere_personne"] + 0.1 * d["longueur_ok"]
         + 0.15 * (d["poesie"] == 0) + 0.1 * (not d["sensation"]) + 0.05 * (d["repetition"] < 0.5))
    d["score"] = round(0.0 if d["refus"] else s, 3)
    return d


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--n", type=int, default=30)
    a.add_argument("--sortie", default=str(Path.home() / "AIOS" / "jarvis" / "duel"))
    args = a.parse_args()
    sortie = Path(args.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    sits = situations(args.n)
    res = {s["id"]: {"situation": s} for s in sits}
    for nom, modele in MODELES.items():                       # un modèle à la fois en mémoire
        print(f"== {nom} ({modele})", flush=True)
        for s in sits:
            try:
                g = generer(modele, s["prompt"])
            except Exception as e:
                g = {"texte": "", "erreur": str(e)[:200], "premier_s": None, "total_s": None, "jetons_s": None}
            g["auto"] = score_auto(g["texte"], s)
            res[s["id"]][nom] = g
            print(f"  {s['id']:2d} {g.get('premier_s')} s  score {g['auto']['score']}  {g['auto']['pensee'][:90]}", flush=True)
        decharger(modele)
    rng = random.Random(7)
    aveugle = []
    for i, r in res.items():                                  # A/B mélangés, sans le nom des modèles
        ordre = ["gemma", "lfm"] if rng.random() < 0.5 else ["lfm", "gemma"]
        aveugle.append({"id": i, "instant": r["situation"]["instant"], "motif": r["situation"]["motif"],
                        "echanges": r["situation"]["echanges"][-4:],
                        "A": r[ordre[0]]["auto"]["pensee"], "B": r[ordre[1]]["auto"]["pensee"],
                        "A_relance": r[ordre[0]]["auto"]["relance"], "B_relance": r[ordre[1]]["auto"]["relance"]})
        r["ordre"] = ordre
    (sortie / "resultats.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (sortie / "aveugle.json").write_text(json.dumps(aveugle, ensure_ascii=False, indent=1), encoding="utf-8")
    bilan = {}
    for nom in MODELES:
        xs = [r[nom] for r in res.values()]
        ok = [x for x in xs if x.get("premier_s") is not None]
        med = lambda l: sorted(l)[len(l) // 2] if l else None
        bilan[nom] = {"score_auto_moyen": round(sum(x["auto"]["score"] for x in xs) / len(xs), 3),
                      "ancrage_moyen": round(sum(x["auto"]["ancrage"] for x in xs) / len(xs), 2),
                      "poesie": sum(x["auto"]["poesie"] > 0 for x in xs), "sensations_inventees": sum(x["auto"]["sensation"] for x in xs),
                      "refus": sum(x["auto"]["refus"] for x in xs), "format_ok": sum(x["auto"]["format"] for x in xs),
                      "premier_mot_median_s": med([x["premier_s"] for x in ok]), "total_median_s": med([x["total_s"] for x in ok]),
                      "jetons_s_median": med([x["jetons_s"] for x in ok if x.get("jetons_s")]), "erreurs": len(xs) - len(ok)}
    (sortie / "bilan_auto.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(bilan, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
