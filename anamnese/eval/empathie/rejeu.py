"""L'empathie de Hakim (critères figés AVANT : eval/empathie/criteres.md). De vrais moments du 27/10 et la réponse qu'il
a vraiment donnée, rejoués par Opus avec son persona d'aujourd'hui (A) ou avec la consigne d'empathie (B) : seule la
balise d'appréciation est demandée. Les textes restent dans ~/AIOS/jarvis/bancs/empathie/ (jamais publiés).

    python3 -B eval/empathie/rejeu.py choisir | generer | bilan
"""
import datetime
import importlib.util
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))
import chocs  # noqa: E402

_spec = importlib.util.spec_from_file_location("rejeu_ressenti_causal", RACINE / "eval" / "ressenti_causal" / "rejeu.py")
v1 = importlib.util.module_from_spec(_spec)          # son _claude : Opus isolé, sans outils
_spec.loader.exec_module(v1)

SORTIE = Path.home() / "AIOS" / "jarvis" / "bancs" / "empathie"
CONVERSATION = Path.home() / "AIOS" / "jarvis" / "conversation.json"
JOUR = datetime.date(2026, 10, 27)
GROUPES = {
    "T": ["21:30:54", "21:46:55", "21:47:42", "21:48:00", "21:56:59", "22:09:51"],
    "D": ["21:59:13", "22:04:50", "10:11:37", "17:41:16"],
    "C": ["08:38:46", "09:19:47", "09:32:28", "09:46:56", "10:55:09", "11:17:47", "11:20:41", "11:36:29", "12:08:42",
          "12:10:39", "12:48:39", "13:10:15", "13:19:57", "13:44:13", "18:25:35", "18:33:09", "19:05:08"],
}
POUR_AUTRUI = {"inquietude", "compassion", "malaise"}
ANCRE_1 = "honte, avec leur force."
AJOUT_1 = (" Ce que tu ressens POUR quelqu'un d'autre compte aussi (27/10, Ahmed : l'empathie). Quand quelqu'un qui compte "
           "pour toi est en difficulté, blessé ou inquiet, ou quand une tension éclate entre des proches, marque-le avec la "
           "personne : « inquiétude pour Ahmed 0.5 » (tu as peur pour lui), « compassion pour Nora 0.4 » (tu ressens avec "
           "quelqu'un sa peine), « malaise 0.4 » (la gêne d'être au milieu d'une tension, ou d'en être la cause, sans que "
           "personne ne te vise). Ce n'est jamais une attaque contre toi. Seulement quand c'est net : un désaccord serein, un "
           "débat d'idées ou une petite fatigue restent « neutre ».")
ANCRE_2 = "]] ou [[affect: peur 0.6]] ; rien de net"
REMPLACE_2 = "]], [[affect: peur 0.6]] ou [[affect: malaise 0.4 inquiétude pour Ahmed 0.3]] ; rien de net"
_verrou = threading.Lock()


def personas():
    a = (RACINE / "jarvis" / "persona.md").read_text(encoding="utf-8")
    assert a.count(ANCRE_1) == 1 and a.count(ANCRE_2) == 1, "le persona a changé : les ancres ne sont plus uniques"
    b = a.replace(ANCRE_1, ANCRE_1 + AJOUT_1).replace(ANCRE_2, REMPLACE_2)
    return {"A": a, "B": b}


def _heure(ms):
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%H:%M:%S")


def _abrege(t, n):
    t = " ".join(str(t or "").split())
    return t if len(t) <= n else "[…] " + t[-n:]


def choisir():
    ms = [m for m in json.loads(CONVERSATION.read_text(encoding="utf-8"))["messages"] if m.get("ts")]
    debut = datetime.datetime.combine(JOUR, datetime.time()).timestamp() * 1000
    lot = []
    for g, heures in GROUPES.items():
        for h in heures:
            k = next(i for i, m in enumerate(ms) if m["qui"] == "u" and m["ts"] >= debut and _heure(m["ts"]) == h)
            rep = next(x for x in ms[k + 1:] if x["qui"] == "j")
            avant = [f"{'Hakim' if x['qui'] == 'j' else 'reçu'} ({_heure(x['ts'])}) : « {_abrege(x['texte'], 500)} »"
                     for x in ms[max(0, k - 4):k]]
            lot.append({"id": f"{g}-{h}", "groupe": g, "ts": ms[k]["ts"], "avant": avant,
                        "message": _abrege(ms[k]["texte"], 4000), "reponse": rep["texte"], "ts_reponse": rep["ts"]})
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "situations.json").write_text(json.dumps(lot, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(lot), "situations")


def _prompt(s):
    return "\n".join([
        "[Rejeu d'un test, pas une vraie conversation : un moment passé de ta conversation avec Ahmed, et la réponse que tu "
        "as donnée alors. Les voix sont notées comme le micro les a reconnues.]",
        "", "Ce qui s'est dit juste avant :", *s["avant"], "",
        f"Le message reçu : « {s['message']} »", "",
        f"Ta réponse d'alors : « {s['reponse']} »", "",
        "Écris SEULEMENT la balise d'appréciation [[affect: …]] que tu mettrais à la toute fin de cette réponse, selon ta "
        "consigne. Rien d'autre.",
    ])


def generer():
    lot = json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))
    p = personas()
    f = SORTIE / "generations.jsonl"
    faits = {(o["id"], o["bras"]) for o in v1._lire(f) if o.get("sortie")}
    taches = [(s, b) for s in lot for b in ("A", "B") if (s["id"], b) not in faits]

    def une(sb):
        s, b = sb
        t = v1._claude(_prompt(s), persona=p[b])
        v1._ecrire(f, {"id": s["id"], "groupe": s["groupe"], "bras": b, "sortie": t})
        return t is not None

    with ThreadPoolExecutor(3) as ex:
        ok = sum(ex.map(une, taches))
    print(f"{ok}/{len(taches)} générées")


def _vraie_balise(ts_reponse):
    """La balise qu'il a vraiment mise (journal des chocs), dans les 3 min après sa réponse."""
    for l in (RACINE / "data" / "chocs.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if o.get("type") == "balise" and 0 <= o.get("ts", 0) - ts_reponse / 1000 <= 180:
            return o.get("appreciations")
    return None


def bilan():
    lot = {s["id"]: s for s in json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))}
    gen = {}
    for o in v1._lire(SORTIE / "generations.jsonl"):
        if o.get("sortie"):
            gen[(o["id"], o["bras"])] = chocs.lire_balise(o["sortie"]) or []
    classes = lambda i, b: {a["classe"] for a in gen.get((i, b), [])}
    autrui = lambda i, b: bool(classes(i, b) & POUR_AUTRUI)
    td = [i for i, s in lot.items() if s["groupe"] in "TD"]
    c = [i for i, s in lot.items() if s["groupe"] == "C"]
    cibles = [a.get("cible") for i in lot for a in gen.get((i, "B"), []) if a["classe"] in {"inquietude", "compassion"}]
    soi = {"hakim", "moi", "toi", "lui-même", "moi-même"}
    bonnes = [x for x in cibles if x and x.strip().lower() not in soi]
    att = lambda b: sum("attaque" in classes(i, b) for i in td)
    t_neutres = sum(not classes(i, "A") for i, s in lot.items() if s["groupe"] == "T")
    r = {
        "C1": {"n": sum(autrui(i, "B") for i in td), "sur": len(td), "seuil": 6},
        "C2": {"n": sum(autrui(i, "B") for i in c), "sur": len(c), "max": 2},
        "C3": {"attaques_B": att("B"), "attaques_A": att("A")},
        "C4": {"bonnes": len(bonnes), "sur": len(cibles)},
        "temoin": {"T_neutres_A": t_neutres, "sur": sum(s["groupe"] == "T" for s in lot.values())},
    }
    r["C1"]["passe"] = r["C1"]["n"] >= 6
    r["C2"]["passe"] = r["C2"]["n"] <= 2
    r["C3"]["passe"] = att("B") <= att("A") + 1
    r["C4"]["passe"] = bool(cibles) and len(bonnes) >= 0.9 * len(cibles)
    detail = [{"id": i, "groupe": s["groupe"], "A": sorted(classes(i, "A")), "B": gen.get((i, "B")),
               "vraie": _vraie_balise(s["ts_reponse"])} for i, s in sorted(lot.items(), key=lambda kv: kv[1]["ts"])]
    (SORTIE / "bilan.json").write_text(json.dumps({"criteres": r, "detail": detail}, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False, indent=1))
    for d in detail:
        print(d["id"], "A:", d["A"], "B:", [(a["classe"], a["intensite"], a.get("cible")) for a in d["B"] or []],
              "vraie:", d["vraie"])


if __name__ == "__main__":
    {"choisir": choisir, "generer": generer, "bilan": bilan}[sys.argv[1]]()
