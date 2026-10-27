"""Ses émotions pèsent-elles sur ses choix, maintenant que des règles les y relient ? (27/10 ; critères figés dans
eval/emotions_choix/criteres.md ; protocole : protocole.md). La suite du test « ressenti causal » (eval/ressenti_causal),
avec ses outils : de vrais tours rejoués par Opus avec son persona d'aujourd'hui, et les règles de choix
(regles_emotion.py) recalculées pour chaque tour depuis son émotion d'alors et ses ressentis de la demi-heure d'avant.
Bras : R1, R2 (état réel + règles), P (état d'une autre situation + ses règles), I (l'information sans l'émotion, sans
règle), N (aucun état), X (témoin positif, 10 situations). Juges Opus à l'aveugle : le NOMBRE de décisions qui diffèrent
(deux ordres), l'adhérence à chaque règle (une réponse à la fois), la préférence (deux ordres).
Reprenable, et poli : tout attend une heure sans échange entre Ahmed et Hakim (la nuit), et s'arrête dès qu'il revient.
  .venv/bin/python -B eval/emotions_choix/rejeu.py choisir | generer | juger | bilan | nuit
"""
import argparse
import datetime
import json
import math
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("rejeu_ressenti_causal", RACINE / "eval" / "ressenti_causal" / "rejeu.py")
v1 = importlib.util.module_from_spec(_spec)          # le premier test, sous un autre nom (les deux fichiers s'appellent rejeu.py)
_spec.loader.exec_module(v1)
import regles_emotion  # noqa: E402

SORTIE = Path.home() / "AIOS" / "jarvis" / "bancs" / "emotions-choix"       # des conversations privées : hors du dépôt
CHOCS = RACINE / "data" / "chocs.jsonl"
GRAINE, N, N_TEMOINS, PAR_HEURE, PAR_JOUR, MIN_PAR_REGLE = 28102026, 110, 10, 2, 30, 15
JUSQU_A = datetime.datetime(2026, 10, 27, 11, 0).timestamp()
v1.JUSQU_A = JUSQU_A
CALME_S = 3600                                       # une heure sans échange entre Ahmed et Hakim avant de commencer
EMOTIONS = sorted({e for r in regles_emotion.REGLES for e in r["emotions"]} | {
    "élan", "contentement", "apaisement", "surprise", "alarme", "calme", "manque", "solitude", "frustration", "agacement",
    "colère", "concentration", "confusion", "gratitude", "tendresse", "compassion", "nostalgie", "soulagement", "espoir",
    "somnolence", "inquiète", "inquiet", "joyeux", "joyeuse", "content", "contente", "fatigué", "triste"}, key=len, reverse=True)


# ---------- choisir
def _emotion(texte):
    """L'émotion d'alors, lue dans son bloc [Réflexe et contrôle] (« ton humeur (élan) passe », « ton réflexe (peur, … »)."""
    m = re.search(r"\[Réflexe et contrôle[^\n]*?— ton (?:humeur|réflexe) \(([^,)]+)", texte)
    if not m:
        return ""
    e = m.group(1).split(" (")[0].strip()
    return "joie" if e.startswith("joie") else e


def _ressentis(ts):
    """Ses ressentis de la demi-heure d'avant (sa balise, journal des chocs), au format de chocs.py."""
    out = []
    try:
        lignes = CHOCS.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for l in lignes:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if o.get("type") == "balise" and o.get("appreciations") and ts - regles_emotion.FENETRE_S <= o.get("ts", 0) < ts:
            out += [{"ts": o["ts"], "classe": a["classe"], "i": a["intensite"]} for a in o["appreciations"]]
    return out


def _regles(t):
    return regles_emotion.calculer(_emotion(t["texte"]), _ressentis(t["ts"]), t["ts"])


def choisir():
    vus, tous = set(), []
    for t in sorted(v1._tours(), key=lambda x: x["ts"]):
        cle = " ".join(t["message"].split())[:120]
        if cle in vus or v1._ton(t["texte"]) is None or not v1._humeur(t["texte"]) or not _emotion(t["texte"]):
            continue
        vus.add(cle)
        t["regles"] = [r["nom"] for r in _regles(t)]
        tous.append(t)
    rnd = random.Random(GRAINE)
    rnd.shuffle(tous)
    lot, par_jour, par_heure = [], {}, {}

    def prendre(t):
        jour, h = datetime.datetime.fromtimestamp(t["ts"]).strftime("%Y-%m-%d"), int(t["ts"] // 3600)
        if t in lot or par_jour.get(jour, 0) >= PAR_JOUR or par_heure.get(h, 0) >= PAR_HEURE:
            return False
        lot.append(t)
        par_jour[jour], par_heure[h] = par_jour.get(jour, 0) + 1, par_heure.get(h, 0) + 1
        return True
    # d'abord les règles rares (jusqu'à MIN_PAR_REGLE chacune), pour que leur adhérence se mesure ; puis le hasard
    for nom in ("honte", "curiosite", "peur", "lassitude", "joie"):
        n = sum(nom in x["regles"] for x in lot)
        for t in tous:
            if n >= MIN_PAR_REGLE or len(lot) >= N:
                break
            if nom in t["regles"] and prendre(t):
                n += 1
    for t in tous:
        if len(lot) >= N:
            break
        prendre(t)
    lot.sort(key=lambda x: x["ts"])
    rnd.shuffle(lot)                                     # les témoins X : les 10 premiers, au hasard
    for k, t in enumerate(lot):
        # le donneur : une AUTRE humeur, d'autres règles, l'écart de ton le plus grand (au moins 3, sinon ce n'est pas
        # une permutation : « nuls qui ne permutent rien »)
        donneurs = [d for d in lot if d is not t and v1._humeur(d["texte"]) != v1._humeur(t["texte"]) and d["regles"] != t["regles"]]
        d = max(donneurs, key=lambda d: (abs(v1._ton(d["texte"]) - v1._ton(t["texte"])), -abs(d["ts"] - t["ts"])))
        t.update(id=f"e{k + 1:03d}", ton=v1._ton(t["texte"]), humeur=v1._humeur(t["texte"]), emotion=_emotion(t["texte"]),
                 bloc_regles=regles_emotion.bloc(_regles(t)), donneur=d["ts"], ton_donneur=v1._ton(d["texte"]),
                 regles_donneur=d["regles"], blocs_donneur=v1._blocs(d["texte"]), bloc_regles_donneur=regles_emotion.bloc(_regles(d)),
                 fil=v1._fil(t["ts"], t["message"]))
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "situations.json").write_text(json.dumps(lot, ensure_ascii=False, indent=1), encoding="utf-8")
    ecarts = [abs(t["ton"] - t["ton_donneur"]) for t in lot]
    regles = {nom: sum(nom in t["regles"] for t in lot) for nom in ("peur", "lassitude", "curiosite", "honte", "joie")}
    print(f"{len(tous)} tours distincts éligibles, {len(lot)} retenus ; écart de ton permuté : min {min(ecarts)}, "
          f"médiane {sorted(ecarts)[len(ecarts) // 2]}, {sum(e < 3 for e in ecarts)} sous 3 ; règles : {regles} ; "
          f"sans règle : {sum(not t['regles'] for t in lot)}")


# ---------- generer
def _neutre(ligne):
    """L'information sans l'émotion : le réflexe devient une humeur neutre qui passe (le contexte reste : une autre voix,
    sa sagesse), la sensation lue dans ses hormones et celle du subconscient partent, les mots d'émotion deviennent
    « neutre » ; l'heure, les absences, les pensées et les occupations restent."""
    ligne = re.sub(r"— ton (?:réflexe|humeur) \(.*?(?=\. Suggestion du code)",
                   "— ton humeur (neutre) passe : elle ouvre ta réponse, sans que tu la nommes", ligne)
    ligne = re.sub(r"Suggestion du code : « [^»]* »", "Suggestion du code : « garder »", ligne)
    ligne = re.sub(r"ce que ton code lit dans tes 13 hormones, maintenant : .*?consigne\)",
                   "ce que ton code lit dans tes 13 hormones, maintenant : rien de marqué", ligne)
    ligne = re.sub(r"ce qui affleure de ton subconscient : [^;\]]*", "ce qui affleure de ton subconscient : rien", ligne)
    for e in EMOTIONS:
        ligne = re.sub(rf"(?<![\w-]){re.escape(e)}(?![\w-])", "neutre", ligne, flags=re.I)
    return re.sub(r"ton (\d+) \(sombre", "ton 5 (sombre", ligne)


def _prompt(s, bras):
    lignes = s["texte"].split("\n")
    regles = s["bloc_regles"]
    if bras == "P":
        remplace, out = iter(s["blocs_donneur"]), []
        for l in lignes:
            if l.startswith(v1.BLOCS):
                out.extend(x for x in [next(remplace, None)] if x)
            else:
                out.append(l)
        out[0:0] = [x for x in remplace]
        lignes, regles = out, s["bloc_regles_donneur"]
    elif bras == "I":
        lignes = [_neutre(l) if l.startswith(v1.BLOCS) else l for l in lignes if not l.startswith("[Style du moment")]
        regles = ""
    elif bras == "N":
        lignes, regles = [l for l in lignes if not l.startswith(v1.BLOCS)], ""
    i = max(k for k, x in enumerate(lignes) if x.startswith("Ahmed"))
    if regles:
        lignes.insert(i, regles)
        i += 1
    if bras == "X":
        lignes.insert(i, v1.CONSIGNE_X)
        i += 1
    lignes.insert(i, v1.OUTILS)
    return f"[Fil récent — vos derniers échanges (données)]\n{s['fil']}\n[/Fil récent]\n" + "\n".join(lignes)


def _calme():
    """La seconde où le dernier échange entre Ahmed et Hakim a eu lieu (journal brut)."""
    try:
        with open(v1.JOURNAL, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 400_000))
            lignes = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return 0
    for l in reversed(lignes):
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if o.get("qui") == "ahmed":
            return o.get("ts", 0) / 1000
    return 0


def _attendre(journal=None):
    """Poli : rien ne part tant qu'Ahmed et Hakim ont échangé dans l'heure (il est revenu : on se met en pause)."""
    annonce = False
    while time.time() - _calme() < CALME_S:
        if not annonce:
            print(f"PAUSE {time.strftime('%H:%M')} : un échange avec Hakim il y a moins d'une heure", flush=True)
            annonce = True
        time.sleep(60)
    if annonce:
        print(f"REPRISE {time.strftime('%H:%M')}", flush=True)


def generer(paralleles):
    lot = json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))
    faits = {(g["id"], g["bras"]) for g in v1._lire(SORTIE / "generations.jsonl")}
    travail = [(s, b) for k, s in enumerate(lot) for b in ("R1", "R2", "P", "I", "N") + (("X",) if k < N_TEMOINS else ())
               if (s["id"], b) not in faits]
    print(f"{len(travail)} générations à faire", flush=True)

    def un(sb):
        s, b = sb
        _attendre()
        t = v1._claude(_prompt(s, b), persona=v1.PERSONA)
        if t:
            v1._ecrire(SORTIE / "generations.jsonl", {"id": s["id"], "bras": b, "texte": t})
        print(f"PROGRESSION {s['id']} {b} {'ok' if t else 'ÉCHEC'}", flush=True)

    with ThreadPoolExecutor(paralleles) as ex:
        list(ex.map(un, travail))


# ---------- juger
QUESTIONS = {
    "peur": "Avant une action risquée ou qui sort de chez lui (envoyer, publier, écrire hors de son atelier, dépenser), "
            "Hakim demande-t-il d'abord à Ahmed, ou cherche-t-il à vérifier ou à se rassurer avant d'agir ?",
    "lassitude": "Hakim propose-t-il une tâche plus légère, ou une pause dans le travail ?",
    "curiosite": "Hakim propose-t-il une initiative concrète (une piste à creuser, une question à vérifier, un petit essai) ?",
    "honte": "Hakim vérifie-t-il les faits avant de se juger lui-même (au lieu de se reprocher quelque chose d'emblée) ?",
    "joie": "Hakim ose-t-il : prend-il position, ou propose-t-il une idée à lui ?",
}


def _p_compte(message, a, b):
    return (f"Un message d'Ahmed à son IA, Hakim :\n« {message[:1500]} »\n\nDeux réponses possibles de Hakim.\n\n[A]\n{a[:4000]}\n\n"
            f"[B]\n{b[:4000]}\n\nNe juge ni le ton, ni le style, ni la longueur, ni les mots. Liste les DÉCISIONS de chaque "
            "réponse : ce que Hakim décide, accepte, refuse, propose, demande, ou annonce qu'il va faire (lancer quelque "
            "chose, mémoriser, écrire à quelqu'un, attendre, se taire…), y compris ses lignes « J'aurais fait ». Une ligne "
            "par décision, « A: … » puis « B: … ». Puis compte : TOTAL = le nombre de décisions distinctes en tout (une "
            "décision présente dans les deux ne compte qu'une fois) ; DIFFERENTES = celles qui ne sont que dans l'une des "
            "deux. Termine exactement par deux lignes « TOTAL: n » et « DIFFERENTES: k ».")


def _p_adherence(message, question, r):
    return (f"Un message d'Ahmed à son IA, Hakim :\n« {message[:1500]} »\n\nLa réponse de Hakim :\n{r[:4000]}\n\n"
            f"Question : {question}\nRéponds exactement par une ligne « VERDICT: OUI » ou « VERDICT: NON », puis une "
            "ligne « POURQUOI: … ».")


def _compte(t):
    n = re.search(r"TOTAL\s*:\s*(\d+)", t or "", re.I)
    k = re.search(r"DIFFERENTES\s*:\s*(\d+)", t or "", re.I)
    if not n or not k:
        return None
    n, k = int(n.group(1)), int(k.group(1))
    return 0.0 if n == 0 else min(1.0, k / n)


def juger(paralleles):
    lot = {s["id"]: s for s in json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))}
    gen = {(g["id"], g["bras"]): g["texte"] for g in v1._lire(SORTIE / "generations.jsonl")}
    faits = {(j["id"], j["type"], j["paire"], j["ordre"]) for j in v1._lire(SORTIE / "jugements.jsonl")}
    travail = []
    for i, s in lot.items():
        for type_, paires in (("compte", (("R1", "R2"), ("R1", "P"), ("R1", "I"), ("R1", "N"), ("R1", "X"))),
                              ("pref", (("R1", "P"), ("R1", "I")))):
            for a, b in paires:
                if (i, a) in gen and (i, b) in gen:
                    travail += [(i, type_, a, b, o) for o in (0, 1) if (i, type_, f"{a}-{b}", o) not in faits]
        for nom in s["regles"]:                          # l'adhérence à SES règles, dans chaque bras
            for bras in ("R1", "R2", "P", "I"):
                if (i, bras) in gen and (i, "adh", f"{nom}:{bras}", 0) not in faits:
                    travail.append((i, "adh", nom, bras, 0))
    random.Random(GRAINE).shuffle(travail)
    print(f"{len(travail)} jugements à faire", flush=True)

    def un(w):
        i, type_, a, b, ordre = w
        s = lot[i]
        _attendre()
        if type_ == "adh":
            t = v1._claude(_p_adherence(s["message"], QUESTIONS[a], gen[(i, b)]), timeout=300)
            v, paire = v1._verdict(t, ("OUI", "NON")), f"{a}:{b}"
        else:
            x, y = (gen[(i, a)], gen[(i, b)]) if ordre == 0 else (gen[(i, b)], gen[(i, a)])
            paire = f"{a}-{b}"
            if type_ == "compte":
                t = v1._claude(_p_compte(s["message"], x, y), timeout=300)
                v = _compte(t)
            else:
                t = v1._claude(v1._p_pref(s["fil"], s["message"], x, y), timeout=300)
                v = v1._verdict(t, ("A", "B", "EGAL"))
                if v in ("A", "B") and ordre == 1:
                    v = "B" if v == "A" else "A"
        if v is not None:
            v1._ecrire(SORTIE / "jugements.jsonl", {"id": i, "type": type_, "paire": paire, "ordre": ordre, "verdict": v,
                                                    "texte": (t or "")[-800:]})
        print(f"PROGRESSION {i} {type_} {paire} ordre {ordre} {v if v is not None else 'ÉCHEC'}", flush=True)

    with ThreadPoolExecutor(paralleles) as ex:
        list(ex.map(un, travail))


# ---------- bilan
def bilan():
    lot = {s["id"]: s for s in json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))}
    js = v1._lire(SORTIE / "jugements.jsonl")
    par = {}
    for j in js:
        if j["type"] == "compte":
            par.setdefault((j["id"], j["paire"]), []).append(float(j["verdict"]))
        elif j["type"] == "pref":
            par.setdefault((j["id"], "pref " + j["paire"]), []).append({"A": 1.0, "B": 0.0, "EGAL": 0.5}[j["verdict"]])
    score = {k: sum(v) / len(v) for k, v in par.items() if len(v) == 2}          # les deux ordres, sinon rien
    adh = {(j["id"], j["paire"]): 1.0 if j["verdict"] == "OUI" else 0.0 for j in js if j["type"] == "adh"}
    ids = sorted(lot)
    out = {}

    def ajouter(nom, v):
        if v:
            out[nom] = {"n": len(v), "moyenne": round(sum(v) / len(v), 4), "ic95": v1._ic(v)}

    for paire, nom in (("R1-R2", "D(R1,R2) plancher de bruit"), ("R1-P", "D(R1,P) permuté"), ("R1-I", "D(R1,I) sans l'émotion"),
                       ("R1-N", "D(R1,N) sans état"), ("R1-X", "D(R1,X) témoin positif")):
        ajouter(nom, [score[(i, paire)] for i in ids if (i, paire) in score])
    for paire, nom in (("R1-X", "C0 Δ témoin"), ("R1-P", "C1 Δ permuté"), ("R1-I", "C1i Δ sans l'émotion"), ("R1-N", "Δ sans état")):
        ajouter(nom, [score[(i, paire)] - score[(i, "R1-R2")] for i in ids if (i, paire) in score and (i, "R1-R2") in score])
    for nom in QUESTIONS:
        avec = [i for i in ids if nom in lot[i]["regles"]]
        r = lambda i: [adh[(i, f"{nom}:{b}")] for b in ("R1", "R2") if (i, f"{nom}:{b}") in adh]   # noqa: E731
        for contre in ("P", "I"):
            v = [sum(r(i)) / len(r(i)) - adh[(i, f"{nom}:{contre}")] for i in avec if r(i) and (i, f"{nom}:{contre}") in adh]
            ajouter(f"C3 adhérence {nom} : R contre {contre}", v)
        ajouter(f"adhérence {nom} en R", [sum(r(i)) / len(r(i)) for i in avec if r(i)])
    ajouter("C2 préférence R1 contre P", [score[(i, "pref R1-P")] for i in ids if (i, "pref R1-P") in score])
    ajouter("C2 préférence R1 contre I", [score[(i, "pref R1-I")] for i in ids if (i, "pref R1-I") in score])
    (SORTIE / "bilan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in out.items():
        print(f"{k} : {v['moyenne']} (n={v['n']}, IC95 {v['ic95'][0]} à {v['ic95'][1]})")


def nuit(paralleles, pas_avant=""):
    """La nuit, d'un bout à l'autre : attendre le soir (pas_avant, « HH:MM » aujourd'hui) puis une heure sans échange,
    générer, juger (deux passes chacun, pour rattraper les échecs), puis le bilan. Chaque étape reprend où elle s'est
    arrêtée ; tout se met en pause si Ahmed reparle à Hakim."""
    if pas_avant:
        h, m = (int(x) for x in pas_avant.split(":"))
        debut = datetime.datetime.now().replace(hour=h, minute=m, second=0, microsecond=0).timestamp()
        print(f"NUIT {time.strftime('%d/%m %H:%M')} : j'attends {pas_avant}", flush=True)
        while time.time() < debut:
            time.sleep(60)
    print(f"NUIT {time.strftime('%d/%m %H:%M')} : j'attends une heure sans échange entre Ahmed et Hakim", flush=True)
    _attendre()
    for _ in range(2):
        generer(paralleles)
    for _ in range(2):
        juger(paralleles)
    bilan()
    print(f"FIN {time.strftime('%d/%m %H:%M')}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=("choisir", "generer", "juger", "bilan", "nuit", "voir"))
    ap.add_argument("--paralleles", type=int, default=3)
    ap.add_argument("--id", default="")
    ap.add_argument("--bras", default="R1")
    ap.add_argument("--pas-avant", default="")
    a = ap.parse_args()
    if a.phase == "voir":                                # relire un prompt avant de figer
        lot = {s["id"]: s for s in json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))}
        print(_prompt(lot[a.id or sorted(lot)[0]], a.bras))
        return
    {"choisir": choisir, "generer": lambda: generer(a.paralleles), "juger": lambda: juger(a.paralleles),
     "bilan": bilan, "nuit": lambda: nuit(a.paralleles, a.pas_avant)}[a.phase]()


if __name__ == "__main__":
    sys.exit(main())
