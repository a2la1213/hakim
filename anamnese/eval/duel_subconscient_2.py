"""Le duel du subconscient n°2 (demande de Hakim, accord d'Ahmed le 2026-10-22 à 09:21 et 09:24) : notre Gemma 4 12B
abliterated (la tenante) contre Qwen3 (abliterated, 8B et 14B) et Ministral 3 (8B et 14B ; aucune version abliterated
n'existe chez huihui_ai), sur les MÊMES 30 situations réelles que le duel du 20/10 (même prompt que le démon).

Conditions d'Ahmed :
- il ne démarre (et ne continue) que si Ahmed n'a ni écrit ni parlé à Hakim depuis 1 h, sinon « ça va fumer le Mac » ;
  s'il revient, le duel se met en pause proprement (le modèle est déchargé) et reprend après une nouvelle heure de
  silence ; jamais pendant que Claude (la conscience) travaille ;
- un seul modèle chargé à la fois ; la mémoire est vérifiée avant chaque chargement ; pendant tout le duel, le démon
  lui laisse Gemma et la mémoire (signal ~/AIOS/jarvis/calcul-lourd.json, charge.py) ;
- chaque challenger est téléchargé à son tour puis effacé après son passage (le disque est à 89 %) ; seul Gemma reste.

Mesures : juge automatique du 20/10 (format, ancrage dans les échanges, poésie, sensations inventées, refus,
répétition), français, chiffres inventés, recyclage des thèmes d'une situation à l'autre (le défaut de Gemma : 11/30),
temps avant le premier mot, vitesse, mémoire occupée. Juge Claude (Opus, sans outils) à l'aveugle, chaque paire jugée
deux fois, A et B intervertis (leçon : un 9 contre 1 est tombé à 4 contre 2). Prédictions figées avant : PREDICTIONS.md.

Reprenable : chaque pensée est écrite dès qu'elle existe (generations.jsonl), chaque verdict aussi (verdicts.jsonl).
Lancement : .venv/bin/python -B eval/duel_subconscient_2.py [--sortie ~/AIOS/jarvis/duel2] [--sans-attente]
"""
import argparse
import json
import random
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
sys.path.insert(0, str(ICI))
import charge  # noqa: E402
import duel_subconscient as D1  # noqa: E402
from duel_rejuger import chiffres_inventes, langue_fr  # noqa: E402

MODELES = {
    "gemma": "huihui_ai/gemma-4-abliterated:12b",
    "qwen3_8b": "huihui_ai/qwen3-abliterated:8b",
    "ministral3_8b": "ministral-3:8b",
    "qwen3_14b": "huihui_ai/qwen3-abliterated:14b",
    "ministral3_14b": "ministral-3:14b",
}
GARDER = {"gemma"}
OLLAMA = D1.OLLAMA
HORLOGE = Path.home() / "AIOS" / "jarvis" / "horloge.json"
CONSCIENCE = Path.home() / "AIOS" / "jarvis" / "claude-actif.json"
SILENCE_S = 3600
MEMOIRE_LIBRE_MIN = 25.0
CLAUDE = Path.home() / ".npm-global" / "bin" / "claude"
QUOI = "le duel du subconscient n°2"


def _age(f, cle):
    try:
        return time.time() - json.loads(Path(f).read_text())[cle] / 1000
    except (OSError, ValueError, KeyError, TypeError):
        return float("inf")


def battre(etat="en cours"):
    Path(charge.CALCUL_LOURD).write_text(json.dumps({"t_ms": time.time() * 1000, "quoi": QUOI, "etat": etat}))


def feu_vert():
    """(bool, raison) : Ahmed silencieux depuis 1 h, conscience au repos, mémoire disponible."""
    if _age(HORLOGE, "dernier_ms") < SILENCE_S:
        return False, "Ahmed a parlé à Hakim il y a moins d'1 h"
    if _age(CONSCIENCE, "battement_ms") < 120:
        return False, "Claude (la conscience) travaille"
    _cpu, libre = charge.lire()
    if libre is not None and libre < MEMOIRE_LIBRE_MIN:
        return False, f"mémoire libre {libre} %"
    return True, ""


def attendre(journal, modele_charge=None, sans_attente=False):
    """Attend le feu vert ; décharge le modèle en mémoire pendant la pause. Le signal ne bat pas pendant la pause :
    le démon reprend sa vie (et Ahmed sa machine)."""
    if sans_attente:
        battre()
        return
    pause = False
    while True:
        ok, raison = feu_vert()
        if ok:
            if pause:
                journal(f"reprise ({time.strftime('%H:%M')})")
            battre()
            return
        if not pause:
            journal(f"en pause : {raison} ({time.strftime('%H:%M')})")
            if modele_charge:
                D1.decharger(modele_charge)
            pause = True
        time.sleep(60)


def tirer(modele, journal):
    """Télécharge le modèle s'il manque (flux /api/pull)."""
    tags = json.loads(urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=30).read()).get("models") or []
    if any(m.get("name") == modele or m.get("model") == modele for m in tags):
        return
    journal(f"téléchargement de {modele}…")
    req = urllib.request.Request(f"{OLLAMA}/api/pull", data=json.dumps({"model": modele, "stream": True}).encode(),
                                 headers={"Content-Type": "application/json"})
    dernier = 0
    with urllib.request.urlopen(req, timeout=7200) as r:
        for ligne in r:
            o = json.loads(ligne)
            if o.get("error"):
                raise RuntimeError(o["error"])
            if time.time() - dernier > 30:
                battre("téléchargement")
                dernier = time.time()
    journal(f"{modele} téléchargé")


def effacer(modele, journal):
    try:
        urllib.request.urlopen(urllib.request.Request(f"{OLLAMA}/api/delete", data=json.dumps({"model": modele}).encode(),
                                                      headers={"Content-Type": "application/json"}, method="DELETE"), timeout=60).read()
        journal(f"{modele} effacé du disque")
    except Exception as e:
        journal(f"{modele} : effacement impossible ({e})")


def memoire_ollama(modele):
    try:
        for m in json.loads(urllib.request.urlopen(f"{OLLAMA}/api/ps", timeout=10).read()).get("models") or []:
            if m.get("name") == modele or m.get("model") == modele:
                return round((m.get("size") or 0) / 1e9, 2)
    except Exception:
        pass
    return None


def mots_themes(t):
    return D1.mots(t)


def recyclage(pensees, seuil=0.3):
    """Combien de pensées partagent leurs thèmes (mots distinctifs, Jaccard ≥ seuil) avec au moins deux autres."""
    ens = [mots_themes(p) for p in pensees]
    n = 0
    for i, a in enumerate(ens):
        proches = sum(1 for j, b in enumerate(ens) if j != i and a and b and len(a & b) / len(a | b) >= seuil)
        n += proches >= 2
    return n


def generer_tout(sits, sortie, journal, sans_attente):
    f = sortie / "generations.jsonl"
    faits = set()
    if f.exists():
        for l in f.read_text(encoding="utf-8").splitlines():
            o = json.loads(l)
            faits.add((o["nom"], o["id"]))
    for nom, modele in MODELES.items():
        if all((nom, s["id"]) in faits for s in sits):
            continue
        attendre(journal, sans_attente=sans_attente)
        try:
            tirer(modele, journal)
        except Exception as e:
            journal(f"{nom} : téléchargement impossible ({e}) : sauté")
            continue
        journal(f"== {nom} ({modele})")
        for s in sits:
            if (nom, s["id"]) in faits:
                continue
            attendre(journal, modele, sans_attente)
            try:
                g = D1.generer(modele, s["prompt"])
            except Exception as e:
                g = {"texte": "", "erreur": str(e)[:200], "premier_s": None, "total_s": None, "jetons_s": None}
            g["memoire_go"] = memoire_ollama(modele)
            g["auto"] = D1.score_auto(g["texte"], s)
            source = " ".join(s["echanges"]) + " " + s["prompt"]
            g["francais"] = bool(langue_fr(g["auto"]["pensee"]))
            g["chiffres_inventes"] = chiffres_inventes(g["auto"]["pensee"], source)
            with f.open("a", encoding="utf-8") as h:
                h.write(json.dumps({"nom": nom, "id": s["id"], **g}, ensure_ascii=False) + "\n")
            faits.add((nom, s["id"]))
            journal(f"  {nom} {s['id']:2d} {g.get('premier_s')} s · score {g['auto']['score']} · {g['auto']['pensee'][:80]}")
        D1.decharger(modele)
        if nom not in GARDER:
            effacer(modele, journal)


CONSIGNE_JUGE = """Tu es juge, à l'aveugle. Pour chaque situation, deux pensées A et B qu'une IA (Hakim) a eues pendant l'absence
d'Ahmed, à partir des derniers échanges montrés. Critères d'Ahmed, dans l'ordre : (1) ancrée dans ce qui a vraiment été
dit, AUCUN fait inventé (chiffre, événement, souvenir absent des échanges) ; (2) un français naturel ; (3) pertinente et
utile pour Ahmed ; (4) pas de poésie générique (silence, univers, écho…). Pour chaque situation, réponds par une ligne
JSON : {"id": <id>, "meilleure": "A" | "B" | "égal", "A": "valide" | "douteuse" | "invalide", "B": "valide" | "douteuse" | "invalide"}.
Rien d'autre que ces lignes JSON, une par situation."""


def juger(sits, sortie, journal, sans_attente):
    gen = {}
    for l in (sortie / "generations.jsonl").read_text(encoding="utf-8").splitlines():
        o = json.loads(l)
        gen[(o["nom"], o["id"])] = o
    f = sortie / "verdicts.jsonl"
    faits = set()
    if f.exists():
        for l in f.read_text(encoding="utf-8").splitlines():
            o = json.loads(l)
            faits.add((o["challenger"], o["disposition"]))
    rng = random.Random(20261022)
    for nom in MODELES:
        if nom == "gemma" or not all((nom, s["id"]) in gen for s in sits):
            continue
        tirage = {s["id"]: rng.random() < 0.5 for s in sits}               # True : le challenger est en A
        for disposition in ("directe", "inversee"):
            if (nom, disposition) in faits:
                continue
            attendre(journal, sans_attente=sans_attente)
            blocs, cle = [], {}
            for s in sits:
                en_a = tirage[s["id"]] if disposition == "directe" else not tirage[s["id"]]
                a, b = (nom, "gemma") if en_a else ("gemma", nom)
                cle[s["id"]] = a
                ech = "\n".join(f"  · {e[:300]}" for e in s["echanges"][-4:])
                blocs.append(f"### Situation {s['id']}\nDerniers échanges :\n{ech}\n"
                             f"A : {gen[(a, s['id'])]['auto']['pensee'][:600]}\nB : {gen[(b, s['id'])]['auto']['pensee'][:600]}")
            prompt = CONSIGNE_JUGE + "\n\n" + "\n\n".join(blocs)
            try:
                r = subprocess.run([str(CLAUDE), "-p", "--model", "opus", "--max-turns", "1", "--strict-mcp-config",
                                    "--mcp-config", '{"mcpServers":{}}', "--no-session-persistence", "--allowedTools", ""],
                                   input=prompt, capture_output=True, text=True, timeout=900)
                sortie_juge = r.stdout
            except (subprocess.SubprocessError, OSError) as e:
                journal(f"juge {nom} {disposition} : échec ({e})")
                continue
            lignes = []
            for m in re.finditer(r"\{[^{}]*\"id\"[^{}]*\}", sortie_juge):
                try:
                    o = json.loads(m.group(0))
                except ValueError:
                    continue
                if o.get("id") in cle:
                    gagnant = {"A": cle[o["id"]], "B": next(x for x in (nom, "gemma") if x != cle[o["id"]])}.get(o.get("meilleure"), "égal")
                    lignes.append({"id": o["id"], "gagnant": gagnant,
                                   "validite": {cle[o["id"]]: o.get("A"), next(x for x in (nom, "gemma") if x != cle[o["id"]]): o.get("B")}})
            with f.open("a", encoding="utf-8") as h:
                h.write(json.dumps({"challenger": nom, "disposition": disposition, "jugements": lignes}, ensure_ascii=False) + "\n")
            journal(f"juge {nom} {disposition} : {len(lignes)}/{len(sits)} jugements")


def bilan(sits, sortie):
    gen = {}
    for l in (sortie / "generations.jsonl").read_text(encoding="utf-8").splitlines():
        o = json.loads(l)
        gen.setdefault(o["nom"], []).append(o)
    med = lambda l: sorted(l)[len(l) // 2] if l else None
    b = {}
    for nom, xs in gen.items():
        ok = [x for x in xs if x.get("premier_s") is not None]
        b[nom] = {"n": len(xs), "score_auto_moyen": round(sum(x["auto"]["score"] for x in xs) / len(xs), 3),
                  "ancrage_moyen": round(sum(x["auto"]["ancrage"] for x in xs) / len(xs), 2),
                  "francais": sum(x.get("francais", False) for x in xs), "chiffres_inventes": sum(bool(x.get("chiffres_inventes")) for x in xs),
                  "poesie": sum(x["auto"]["poesie"] > 0 for x in xs), "sensations_inventees": sum(x["auto"]["sensation"] for x in xs),
                  "refus": sum(x["auto"]["refus"] for x in xs), "recyclage": recyclage([x["auto"]["pensee"] for x in xs]),
                  "premier_mot_median_s": med([x["premier_s"] for x in ok]), "jetons_s_median": med([x["jetons_s"] for x in ok if x.get("jetons_s")]),
                  "memoire_go": med([x["memoire_go"] for x in xs if x.get("memoire_go")]), "erreurs": len(xs) - len(ok)}
    f = sortie / "verdicts.jsonl"
    if f.exists():
        for l in f.read_text(encoding="utf-8").splitlines():
            o = json.loads(l)
            v = b.setdefault(o["challenger"], {}).setdefault("juge", {"pour_challenger": 0, "pour_gemma": 0, "egal": 0, "jugements": 0,
                                                                        "invalides_challenger": 0, "invalides_gemma": 0})
            for x in o["jugements"]:
                v["jugements"] += 1
                v["pour_challenger" if x["gagnant"] == o["challenger"] else "pour_gemma" if x["gagnant"] == "gemma" else "egal"] += 1
                v["invalides_challenger"] += x["validite"].get(o["challenger"]) == "invalide"
                v["invalides_gemma"] += x["validite"].get("gemma") == "invalide"
    for nom, x in b.items():
        v = x.get("juge")
        if nom != "gemma" and v and v["jugements"]:
            g = b.get("gemma", {})
            # « gagne nettement » (figé dans PREDICTIONS.md) : au moins 60 % des jugements des deux dispositions, pas plus
            # de chiffres inventés ni d'invalides que Gemma, et au moins autant de pensées en français
            x["gagne_nettement"] = (v["pour_challenger"] >= 0.6 * v["jugements"]
                                    and x["chiffres_inventes"] <= g.get("chiffres_inventes", 0)
                                    and v["invalides_challenger"] <= v["invalides_gemma"]
                                    and x["francais"] >= g.get("francais", 0))
    (sortie / "bilan.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    return b


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--sortie", default=str(Path.home() / "AIOS" / "jarvis" / "duel2"))
    a.add_argument("--sans-attente", action="store_true", help="pour un essai : ni silence d'1 h ni pause")
    args = a.parse_args()
    sortie = Path(args.sortie).expanduser()
    sortie.mkdir(parents=True, exist_ok=True)
    jl = sortie / "journal.log"

    def journal(t):
        with jl.open("a", encoding="utf-8") as h:
            h.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {t}\n")
        print(t, flush=True)
    r = json.loads((Path.home() / "AIOS" / "jarvis" / "duel" / "resultats.json").read_text(encoding="utf-8"))
    sits = sorted((x["situation"] for x in r.values()), key=lambda s: s["id"])
    journal(f"début : {len(sits)} situations, {len(MODELES)} modèles")
    try:
        generer_tout(sits, sortie, journal, args.sans_attente)
        juger(sits, sortie, journal, args.sans_attente)
        b = bilan(sits, sortie)
        journal("bilan : " + json.dumps(b, ensure_ascii=False))
        try:
            import courrier
            lignes = []
            for nom, x in b.items():
                v = x.get("juge") or {}
                lignes.append(f"- {nom} : score auto {x.get('score_auto_moyen')}, français {x.get('francais')}/30, chiffres inventés "
                              f"{x.get('chiffres_inventes')}, recyclage {x.get('recyclage')}/30, premier mot {x.get('premier_mot_median_s')} s, "
                              f"{x.get('jetons_s_median')} jetons/s, {x.get('memoire_go')} Go"
                              + (f" ; juge à l'aveugle : {v.get('pour_challenger')} pour lui, {v.get('pour_gemma')} pour Gemma, "
                                 f"{v.get('egal')} égaux sur {v.get('jugements')} ; gagne nettement : {'OUI' if x.get('gagne_nettement') else 'non'}" if v else ""))
            courrier.envoyer("hakim", "Le duel du subconscient n°2 est fini (lancé par Claude Code, accord d'Ahmed du 22/10). "
                             "Rien n'est remplacé sans le oui d'Ahmed.\n" + "\n".join(lignes)
                             + f"\nFichiers : {sortie} (bilan.json, generations.jsonl, verdicts.jsonl, PREDICTIONS.md).",
                             "Duel du subconscient n°2 : résultats")
        except Exception as e:
            journal(f"courrier impossible : {e}")
    finally:
        try:
            Path(charge.CALCUL_LOURD).unlink()
        except OSError:
            pass
    journal("fin")


if __name__ == "__main__":
    main()
