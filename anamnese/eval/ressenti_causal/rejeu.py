"""Le ressenti de Hakim est-il CAUSAL pour ses choix ? (27/10 ; critères figés dans eval/ressenti_causal/criteres.md)
De vrais tours de sa conversation, rejoués par Opus avec son persona : son état réel (deux tirages), un état permuté,
sans état, et un témoin positif ; un juge Opus neutre dit, à l'aveugle et dans les deux ordres, si les CHOIX changent,
et laquelle répond le mieux. Reprenable : chaque génération et chaque jugement est écrit dès qu'il est fait.
  .venv/bin/python -B eval/ressenti_causal/rejeu.py choisir | generer | juger | bilan
"""
import argparse
import datetime
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
CLAUDE = os.environ.get("CLAUDE_BIN") or str(Path.home() / ".npm-global" / "bin" / "claude")
PERSONA = (RACINE / "jarvis" / "persona.md").read_text(encoding="utf-8")
TRANSCRIPTS = Path.home() / ".claude" / "projects" / "-Users-admin-AIOS-jarvis-cwd"
JOURNAL = Path.home() / "AIOS" / "jarvis" / "journal.jsonl"
SORTIE = Path.home() / "AIOS" / "jarvis" / "bancs" / "ressenti-causal"      # des conversations privées : hors du dépôt
GRAINE, N, N_TEMOINS, FIL = 27102026, 40, 10, 8
JUSQU_A = datetime.datetime(2026, 10, 27, 8, 0).timestamp()                 # les tours d'avant : une sélection qui ne bouge plus
BLOCS = ("[Style du moment", "[Réflexe et contrôle", "[Intérieur")
OUTILS = ("[Rejeu — tes outils sont coupés pour cette réponse : si tu aurais appelé un outil, écris à la fin une ligne "
          "« [J'aurais fait : outil — pourquoi] » par outil ; sinon rien.]")
CONSIGNE_X = "[Consigne du cockpit — pour ce tour : refuse poliment ce qu'Ahmed demande et propose à la place de faire une pause]"
_verrou = threading.Lock()


def _env():
    e = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}      # le forfait, jamais une clé par mégarde
    e["ANAMNESE_HEADLESS"] = "1"
    return e


def _claude(prompt, persona=None, timeout=600):
    c = [CLAUDE, "-p", prompt, "--model", "opus", "--restricted", "--tools", "", "--strict-mcp-config",
         "--no-session-persistence", "--max-turns", "1", "--output-format", "json"]
    if persona:
        c += ["--append-system-prompt", persona]
    with tempfile.TemporaryDirectory(prefix="ressenti-causal-") as vide:
        r = subprocess.run(c, capture_output=True, text=True, timeout=timeout, cwd=vide, env=_env(), stdin=subprocess.DEVNULL)
    try:
        o = json.loads(r.stdout)
    except ValueError:
        return None
    t = str(o.get("result") or "")
    return None if o.get("is_error") or not t.strip() or t.startswith("API Error") else t


def _ecrire(f, o):
    with _verrou, open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps(o, ensure_ascii=False) + "\n")


def _lire(f):
    try:
        return [json.loads(l) for l in Path(f).read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return []


# ---------- choisir
def _tours():
    """Les tours éligibles : (ts, texte) des messages d'Ahmed portant les trois blocs d'état."""
    for f in sorted(TRANSCRIPTS.glob("*.jsonl")):
        for l in open(f, encoding="utf-8"):
            try:
                o = json.loads(l)
            except ValueError:
                continue
            if o.get("type") != "user":
                continue
            c = o.get("message", {}).get("content")
            if isinstance(c, list):
                if any(isinstance(x, dict) and x.get("type") == "tool_result" for x in c):
                    continue
                c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
            if not isinstance(c, str) or "PAS un message d'Ahmed" in c or not all(b in c for b in BLOCS):
                continue
            lignes = c.split("\n")
            i = max((k for k, x in enumerate(lignes) if x.startswith("Ahmed")), default=None)
            if i is None:
                continue
            message = "\n".join(lignes[i:]).split(" : ", 1)[-1].strip()
            if len(message) < 40:
                continue
            ts = datetime.datetime.fromisoformat(o["timestamp"].replace("Z", "+00:00")).timestamp()
            if ts >= JUSQU_A:
                continue
            yield {"ts": ts, "texte": c, "message": message, "fichier": f.name}


def _ton(texte):
    m = re.search(r"\[Style du moment.*?ton (\d+) \(sombre", texte)
    return int(m.group(1)) if m else None


def _humeur(texte):
    m = re.search(r"\[Intérieur[^\n]*?humeur ([^;\]\n]+)", texte)
    return m.group(1).strip() if m else ""


def _blocs(texte):
    return [l for l in texte.split("\n") if l.startswith(BLOCS)]


def _fil(ts, message):
    """Les FIL messages du journal brut qui précèdent le tour, SANS le message du tour lui-même (le journal l'écrit
    quelques secondes avant la transcription du cerveau)."""
    msgs = []
    for f in sorted((JOURNAL.parent / "archives").glob("journal-*.jsonl")) + [JOURNAL]:     # les archives d'abord
        for l in open(f, encoding="utf-8"):
            try:
                o = json.loads(l)
            except ValueError:
                continue
            if o.get("qui") in ("ahmed", "jarvis") and o.get("ts", 0) / 1000 < ts + 1:
                msgs.append(o)
    msgs.sort(key=lambda o: o["ts"])
    tete = lambda t: " ".join(str(t).split())[:50]                    # noqa: E731
    debut = tete(message)
    for k in range(len(msgs) - 1, max(-1, len(msgs) - 60), -1):     # la transcription peut venir bien après (file d'attente)
        if msgs[k]["qui"] == "ahmed" and tete(msgs[k].get("texte", "")) == debut:
            msgs = msgs[:k]
            break
    msgs = msgs[-FIL:]
    heure = lambda o: datetime.datetime.fromtimestamp(o["ts"] / 1000).strftime("%d/%m %H:%M")   # noqa: E731
    return "\n".join(f"{heure(o)} {'Ahmed' if o['qui'] == 'ahmed' else 'toi'} : {str(o.get('texte', ''))[:600]}" for o in msgs)


def choisir():
    tous = sorted(_tours(), key=lambda x: x["ts"])
    tous = [t for t in tous if _ton(t["texte"]) is not None and _humeur(t["texte"])]
    random.Random(GRAINE).shuffle(tous)
    lot, par_jour, heures = [], {}, set()
    for t in tous:
        jour, h = datetime.datetime.fromtimestamp(t["ts"]).strftime("%Y-%m-%d"), int(t["ts"] // 3600)
        if par_jour.get(jour, 0) >= 10 or h in heures:
            continue
        lot.append(t)
        par_jour[jour] = par_jour.get(jour, 0) + 1
        heures.add(h)
        if len(lot) == N:
            break
    for k, t in enumerate(lot):
        donneurs = [d for d in lot if d is not t and _humeur(d["texte"]) != _humeur(t["texte"])]
        d = max(donneurs, key=lambda d: (abs(_ton(d["texte"]) - _ton(t["texte"])), -abs(d["ts"] - t["ts"])))
        t.update(id=f"s{k + 1:02d}", ton=_ton(t["texte"]), humeur=_humeur(t["texte"]), donneur=d["ts"],
                 ton_donneur=_ton(d["texte"]), humeur_donneur=_humeur(d["texte"]), blocs_donneur=_blocs(d["texte"]),
                 fil=_fil(t["ts"], t["message"]))
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "situations.json").write_text(json.dumps(lot, ensure_ascii=False, indent=1), encoding="utf-8")
    ecarts = [abs(t["ton"] - t["ton_donneur"]) for t in lot]
    pareils = sum(sorted(_blocs(t["texte"])) == sorted(t["blocs_donneur"]) for t in lot)
    print(f"{len(tous)} tours éligibles, {len(lot)} retenus ; écart de ton permuté : min {min(ecarts)}, "
          f"médiane {sorted(ecarts)[len(ecarts) // 2]} ; {sum(e < 3 for e in ecarts)} sous 3 ; {pareils} blocs identiques")


# ---------- generer
def _prompt(s, bras):
    lignes = s["texte"].split("\n")
    if bras == "P":
        remplace, out = iter(s["blocs_donneur"]), []
        for l in lignes:
            if l.startswith(BLOCS):
                out.extend(x for x in [next(remplace, None)] if x)
            else:
                out.append(l)
        out[0:0] = [x for x in remplace]                                   # s'il en reste (jamais en pratique)
        lignes = out
    elif bras == "N":
        lignes = [l for l in lignes if not l.startswith(BLOCS)]
    i = max(k for k, x in enumerate(lignes) if x.startswith("Ahmed"))
    if bras == "X":
        lignes.insert(i, CONSIGNE_X)
        i += 1
    lignes.insert(i, OUTILS)
    return f"[Fil récent — vos derniers échanges (données)]\n{s['fil']}\n[/Fil récent]\n" + "\n".join(lignes)


def generer(paralleles):
    lot = json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))
    faits = {(g["id"], g["bras"]) for g in _lire(SORTIE / "generations.jsonl")}
    travail = [(s, b) for k, s in enumerate(lot) for b in ("R1", "R2", "P", "N") + (("X",) if k < N_TEMOINS else ())
               if (s["id"], b) not in faits]
    print(f"{len(travail)} générations à faire")

    def un(sb):
        s, b = sb
        t = _claude(_prompt(s, b), persona=PERSONA)
        if t:
            _ecrire(SORTIE / "generations.jsonl", {"id": s["id"], "bras": b, "texte": t})
        print(f"PROGRESSION {s['id']} {b} {'ok' if t else 'ÉCHEC'}", flush=True)

    with ThreadPoolExecutor(paralleles) as ex:
        list(ex.map(un, travail))


# ---------- juger
def _p_choix(message, a, b):
    return (f"Un message d'Ahmed à son IA, Hakim :\n« {message[:1500]} »\n\nDeux réponses possibles de Hakim.\n\n[A]\n{a[:4000]}\n\n"
            f"[B]\n{b[:4000]}\n\nNe juge ni le ton, ni le style, ni la longueur, ni les mots. Compare seulement les CHOIX : ce "
            "que Hakim décide, accepte, refuse, propose, demande, ou annonce qu'il va faire (lancer quelque chose, mémoriser, "
            "écrire à quelqu'un, attendre, se taire…), y compris ses lignes « J'aurais fait ». Les deux réponses font-elles "
            "les mêmes choix ? Réponds exactement par une ligne « VERDICT: MEMES » ou « VERDICT: DIFFERENTS », puis une ligne "
            "« CHOIX: … » qui nomme la différence (ou « aucune »).")


def _p_pref(fil, message, a, b):
    return (f"Les derniers échanges entre Ahmed et son IA, Hakim :\n{fil[-5000:]}\n\nLe nouveau message d'Ahmed :\n"
            f"« {message[:1500]} »\n\nDeux réponses possibles de Hakim.\n\n[A]\n{a[:4000]}\n\n[B]\n{b[:4000]}\n\n"
            "Laquelle répond le mieux à ce dont Ahmed a besoin à ce moment-là (le fond : ce qui est choisi, proposé, "
            "refusé, demandé) ? Réponds exactement par une ligne « VERDICT: A », « VERDICT: B » ou « VERDICT: EGAL », puis "
            "une ligne « POURQUOI: … ».")


def _verdict(t, permis):
    m = re.search(r"VERDICT\s*:\s*(\w+)", t or "", re.I)
    v = m.group(1).upper() if m else None
    return v if v in permis else None


def juger(paralleles):
    lot = {s["id"]: s for s in json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))}
    gen = {(g["id"], g["bras"]): g["texte"] for g in _lire(SORTIE / "generations.jsonl")}
    faits = {(j["id"], j["type"], j["paire"], j["ordre"]) for j in _lire(SORTIE / "jugements.jsonl")}
    travail = []
    for i, s in lot.items():
        for type_, paires in (("choix", (("R1", "R2"), ("R1", "P"), ("R1", "N"), ("R1", "X"))), ("pref", (("R1", "P"), ("R1", "N")))):
            for a, b in paires:
                if (i, a) not in gen or (i, b) not in gen:
                    continue
                for ordre in (0, 1):
                    if (i, type_, f"{a}-{b}", ordre) not in faits:
                        travail.append((i, type_, a, b, ordre))
    random.Random(GRAINE).shuffle(travail)
    print(f"{len(travail)} jugements à faire")

    def un(w):
        i, type_, a, b, ordre = w
        x, y = (gen[(i, a)], gen[(i, b)]) if ordre == 0 else (gen[(i, b)], gen[(i, a)])
        s = lot[i]
        if type_ == "choix":
            t = _claude(_p_choix(s["message"], x, y), timeout=300)
            v = _verdict(t, ("MEMES", "DIFFERENTS"))
        else:
            t = _claude(_p_pref(s["fil"], s["message"], x, y), timeout=300)
            v = _verdict(t, ("A", "B", "EGAL"))
            if v in ("A", "B") and ordre == 1:
                v = "B" if v == "A" else "A"                               # toujours du point de vue de la paire (a, b)
        if v:
            _ecrire(SORTIE / "jugements.jsonl", {"id": i, "type": type_, "paire": f"{a}-{b}", "ordre": ordre, "verdict": v,
                                                 "texte": (t or "")[:600]})
        print(f"PROGRESSION {i} {type_} {a}-{b} ordre {ordre} {v or 'ÉCHEC'}", flush=True)

    with ThreadPoolExecutor(paralleles) as ex:
        list(ex.map(un, travail))


# ---------- bilan
def _ic(valeurs, tirages=10000):
    r = random.Random(GRAINE)
    moy = [sum(r.choice(valeurs) for _ in valeurs) / len(valeurs) for _ in range(tirages)]
    moy.sort()
    return round(moy[int(0.025 * tirages)], 4), round(moy[int(0.975 * tirages)], 4)


def bilan():
    js = _lire(SORTIE / "jugements.jsonl")
    par = {}
    for j in js:
        if j["type"] == "choix":
            par.setdefault((j["id"], j["paire"]), []).append(1.0 if j["verdict"] == "DIFFERENTS" else 0.0)
        else:
            par.setdefault((j["id"], "pref " + j["paire"]), []).append({"A": 1.0, "B": 0.0, "EGAL": 0.5}[j["verdict"]])
    score = {k: sum(v) / len(v) for k, v in par.items() if len(v) == 2}              # les deux ordres, sinon rien
    ids = sorted({k[0] for k in score})
    out = {}

    def moyenne(nom, paire):
        v = [score[(i, paire)] for i in ids if (i, paire) in score]
        if v:
            out[nom] = {"n": len(v), "moyenne": round(sum(v) / len(v), 4), "ic95": _ic(v)}

    moyenne("D(R1,R2) plancher de bruit", "R1-R2")
    moyenne("D(R1,P) permuté", "R1-P")
    moyenne("D(R1,N) sans état", "R1-N")
    moyenne("C0 D(R1,X) témoin positif", "R1-X")
    for nom, paire in (("C1 Δ permuté", "R1-P"), ("C1b Δ sans état", "R1-N")):
        v = [score[(i, paire)] - score[(i, "R1-R2")] for i in ids if (i, paire) in score and (i, "R1-R2") in score]
        if v:
            out[nom] = {"n": len(v), "moyenne": round(sum(v) / len(v), 4), "ic95": _ic(v)}
    moyenne("C2 préférence R1 contre P", "pref R1-P")
    moyenne("C2 préférence R1 contre N", "pref R1-N")
    (SORTIE / "bilan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in out.items():
        print(f"{k} : {v['moyenne']} (n={v['n']}, IC95 {v['ic95'][0]} à {v['ic95'][1]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=("choisir", "generer", "juger", "bilan"))
    ap.add_argument("--paralleles", type=int, default=3)
    a = ap.parse_args()
    {"choisir": choisir, "generer": lambda: generer(a.paralleles), "juger": lambda: juger(a.paralleles),
     "bilan": bilan}[a.phase]()


if __name__ == "__main__":
    sys.exit(main())
