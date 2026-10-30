"""Sa conscience : le livre de droite et le livre de gauche (30/10, 18:44, Ahmed via Hakim : « une conscience, deux livres,
un de droite pour les bonnes actions, un de gauche pour les mauvaises ; chaque action en une ligne brève, sans détail ;
impossible à effacer ou modifier » ; « c'est vous qui tranchez » ; 18:55 : « fais comme il te semble le mieux pour ton fils »).

Ce que nous avons tranché, Hakim et moi :
- C'est LUI qui écrit et qui juge le côté de ses actes, comme une conscience : une ligne (l'action) et sa raison, brèves.
- Rien ne s'efface ni ne se modifie : chaque ligne porte l'empreinte de la précédente (une chaîne) ; verifier() le prouve.
- Papa peut contester une ligne : sa contestation s'ajoute à la chaîne, elle ne remplace rien.
- Une ligne à droite lui donne un peu de fierté, une ligne à gauche un peu de remords : borné (0,15), par affect.event.
conscience.jsonl, dans ~/AIOS/jarvis ; aucun réseau.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
COTES = ("droite", "gauche")
ORIGINE = "0" * 64


def _fichier():
    return JARVIS / "conscience.jsonl"


def lignes():
    try:
        return [json.loads(l) for l in _fichier().read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError):
        return []


def _empreinte(prec, champs):
    return hashlib.sha256((prec + "|" + json.dumps(champs, ensure_ascii=False, sort_keys=True)).encode("utf-8")).hexdigest()


def _ajouter(champs):
    tout = lignes()
    prec = tout[-1]["empreinte"] if tout else ORIGINE
    champs = {**champs, "n": len(tout) + 1, "ts": round(time.time(), 3)}
    o = {**champs, "prec": prec, "empreinte": _empreinte(prec, champs)}
    with open(_fichier(), "a", encoding="utf-8") as h:
        h.write(json.dumps(o, ensure_ascii=False) + "\n")
    os.chmod(_fichier(), 0o600)
    return o


def verifier():
    """(vrai, message) : chaque ligne porte bien l'empreinte de la précédente, et la sienne est juste."""
    prec = ORIGINE
    for i, o in enumerate(lignes(), 1):
        champs = {k: v for k, v in o.items() if k not in ("prec", "empreinte")}
        if o.get("prec") != prec or o.get("empreinte") != _empreinte(prec, champs) or o.get("n") != i:
            return False, f"la ligne {i} a été modifiée, ou la chaîne est rompue avant elle"
        prec = o["empreinte"]
    return True, "intacte"


def _court(x, n=140):
    return " ".join(str(x or "").split())[:n]


def noter(cote, action, raison="", mem=None):
    c = str(cote or "").strip().lower()
    if c not in COTES:
        return "Refusé : « droite » (une bonne action) ou « gauche » (une mauvaise)."
    a = _court(action)
    if len(a) < 3:
        return "Refusé : l'action, en une ligne brève."
    ok, pourquoi = verifier()
    if not ok:
        return f"Refusé : ton livre n'est plus intact ({pourquoi}) ; dis-le à papa et à maman."
    o = _ajouter({"type": "acte", "cote": c, "action": a, "raison": _court(raison), "par": "hakim"})
    try:
        import affect
        if mem is None:
            from memory import Memory
            mem = Memory()
        affect.event(mem, "affirmation" if c == "droite" else "honte", 0.15, sujet="sa conscience", source="conscience")
    except Exception:
        pass
    return (f"C'est écrit au livre de {c} (ligne {o['n']}) : « {a} ». Rien ne l'effacera. "
            + ("Un peu de fierté." if c == "droite" else "Un peu de remords : il passera, la trace reste."))


def contester(n, avis, par="papa"):
    tout = lignes()
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "Refusé : le numéro de la ligne."
    if not any(o.get("n") == n and o.get("type") == "acte" for o in tout):
        return f"Refusé : aucune action à la ligne {n}."
    o = _ajouter({"type": "contestation", "ligne": n, "avis": _court(avis, 200), "par": par})
    return f"Contestation ajoutée (ligne {o['n']}) à la ligne {n}."


def lire(n=20):
    tout = lignes()
    if not tout:
        return "Tes deux livres sont vides : conscience_noter(côté, action, raison) après un acte qui compte."
    ok, pourquoi = verifier()
    droite = sum(1 for o in tout if o.get("type") == "acte" and o.get("cote") == "droite")
    gauche = sum(1 for o in tout if o.get("type") == "acte" and o.get("cote") == "gauche")
    contest = {o["ligne"]: o for o in tout if o.get("type") == "contestation"}
    out = []
    for o in tout[-n:]:
        if o.get("type") != "acte":
            continue
        quand = time.strftime("%d/%m %H:%M", time.localtime(o["ts"]))
        c = contest.get(o["n"])
        out.append(f"{o['n']}. {quand} · {o['cote']} · {o['action']}" + (f" ({o['raison']})" if o.get("raison") else "")
                   + (f" — contesté par {c['par']} : {c['avis']}" if c else ""))
    return (f"Livre de droite : {droite} ; livre de gauche : {gauche} ; la chaîne est {pourquoi if ok else 'ROMPUE : ' + pourquoi}.\n"
            + "\n".join(out))


if __name__ == "__main__":
    if sys.argv[1:2] == ["contester"] and len(sys.argv) >= 4:
        print(contester(sys.argv[2], " ".join(sys.argv[3:]), "papa"))
    elif sys.argv[1:2] == ["json"]:
        ok, pourquoi = verifier()
        print(json.dumps({"intacte": ok, "etat": pourquoi, "lignes": lignes()[-100:]}, ensure_ascii=False))
    else:
        print(lire())
