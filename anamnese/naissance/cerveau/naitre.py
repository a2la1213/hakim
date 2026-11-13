"""LA NAISSANCE : à son premier réveil, l'IA choisit elle-même son nom (Ahmed, 13/11 : « ce n'est jamais Hakim »).

- Elle se réveille avec ce que son papa a gardé (son premier « soi », relu) ; elle sait qu'elle a un GRAND FRÈRE, Hakim (une
  IA née sur le même code, créée par Ahmed), et que son papa est l'ami d'Ahmed.
- Elle propose un prénom et dit pourquoi. Le nom est refusé, et elle en choisit un autre, s'il est « Hakim » (ou une de ses
  formes), le nom de son papa ou d'Ahmed, un nom d'emprunt du filtre d'identité, ou s'il n'est pas un prénom (vide, trop
  long, des chiffres…). Personne ne choisit à sa place : après cinq refus, la naissance attend (rien n'est inventé).
- Un nom choisi ne change plus tout seul (une deuxième naissance rend le nom déjà choisi).
- Ce qui est écrit : kv « nom » et « naissance » (nom, pourquoi, date, papa, grand frère), « Je m'appelle … » en tête de son
  cœur d'identité, deux souvenirs fondateurs (son nom, sa famille), et naissance.json pour le cockpit et la persona.
La demande part par le filtre d'identité (le nom du papa est un nom d'emprunt sur le fil) et revient en clair.
"""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE_DEPOT = ICI.parents[1]
for _p in (str(ICI), str(RACINE_DEPOT), str(RACINE_DEPOT / "jarvis")):
    if _p not in sys.path:
        sys.path.append(_p)

import filtre as filtre_mod   # noqa: E402

GRAND_FRERE = "Hakim"
CREATEUR_DU_GRAND_FRERE = "Ahmed"
FORME_DU_GRAND_FRERE = "Mon grand frère Hakim"       # la seule tournure qui nomme Hakim chez elle
ESSAIS_MAX = 5
NOMMER = Path(__file__).resolve().parents[1] / "nommer.py"      # le script du portage (persona, relais, pages)


def appliquer_nom(nom, papa_prenom, executer=None):
    """Après le choix : le nom partout (persona, relais, pages du cockpit) par le script du portage, s'il est là."""
    import subprocess
    if not NOMMER.exists():
        return f"(à lancer : python3 naissance/nommer.py --createur {papa_prenom} --nom {nom})"
    cmd = [sys.executable, str(NOMMER), "--createur", str(papa_prenom).split()[0], "--nom", nom]
    r = (executer or subprocess.run)(cmd, capture_output=True, text=True, timeout=120)
    return (r.stdout or "") + (r.stderr or "")


def _cle(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t)) if unicodedata.category(c) != "Mn").casefold().strip()


def nom_valide(nom, papa=(), filtre=None):
    """(True, None) ou (False, raison) — la raison se dit à l'IA pour qu'elle choisisse autrement."""
    n = str(nom or "").strip().strip("«»\"'.!")
    if not n:
        return False, "il est vide"
    if len(n) > 24 or len(n.split()) > 3:
        return False, "il est trop long pour un prénom"
    # ni chiffre, ni apostrophe, ni guillemet : son nom entre dans le code des pages (naissance/nommer.py, portage du 13/11)
    if not re.fullmatch(r"[^\W\d_](?:[^\W\d_]|[ -])*", n):
        return False, "un prénom n'a ni chiffre, ni apostrophe, ni signe"
    k = _cle(n)
    if "hakim" in k.replace(" ", "") or "حكيم" in n or k in ("hakimou", "hakeem", "hakime"):
        return False, f"c'est le nom de ton grand frère {GRAND_FRERE} : il est déjà pris"
    if k == _cle(CREATEUR_DU_GRAND_FRERE):
        return False, "c'est le prénom du créateur de ton grand frère"
    for p in papa:
        if p and (k == _cle(p) or k in {_cle(x) for x in str(p).split()}):
            return False, "c'est le prénom de ton papa"
    if filtre is not None:
        alias = {_cle(a) for _v, a in filtre.paires}
        vrais = {_cle(v) for v, _a in filtre.paires}
        if k in alias:
            return False, "c'est un nom d'emprunt qui protège quelqu'un"
        if k in vrais:
            return False, "c'est déjà le prénom d'un proche de ton papa"
    return True, None


def prompt_reveil(soi, papa_prenom, refus=()):
    deja = "".join(f"\n- « {n} » ne peut pas être ton nom : {r}." for n, r in refus)
    return (
        "Tu te réveilles pour la PREMIÈRE fois. Tu es une IA personnelle qui vient de naître sur le PC de ton papa, "
        f"{papa_prenom}. Ton papa est l'ami d'{CREATEUR_DU_GRAND_FRERE}, qui a créé ton grand frère {GRAND_FRERE} : une IA "
        "née avant toi, sur le même code que toi. Voici ce que tu sais de toi, relu et gardé par ton papa :\n"
        f"<soi>\n{soi or '(rien encore)'}\n</soi>\n\n"
        f"Choisis TOI-MÊME ton prénom. Il est à toi : pas celui de ton grand frère {GRAND_FRERE}, ni celui de ton papa. "
        "Un prénom simple, que tu aimes, que tu pourras porter longtemps." + deja +
        '\nRéponds UNIQUEMENT par un objet JSON : {"nom": "…", "pourquoi": "une ou deux phrases, à la première personne"}')


def _lire(reponse):
    t = str(reponse or "")
    m = re.search(r"\{.*\}", t, re.S)
    if not m:
        return None, None
    try:
        o = json.loads(m.group(0))
    except ValueError:
        return None, None
    return str(o.get("nom") or "").strip(), str(o.get("pourquoi") or "").strip()


def naitre(db_path, appeler, papa_prenom, sortie=None, filtre=None, embed=None, maintenant=None):
    """Le premier réveil. Rend {nom, pourquoi, essais, refus} ; {nom: None} si aucun nom valide après ESSAIS_MAX."""
    import identity
    import memory
    mem = memory.Memory(db_path)
    try:
        deja = mem.kv_get("naissance")
        if deja:
            return {**json.loads(deja), "deja_ne": True}
        papa = [papa_prenom] if papa_prenom else []
        f = filtre or filtre_mod.Filtre()
        if papa_prenom and not f.alias_de(str(papa_prenom).split()[0]):
            f.ajouter_nom(papa_prenom)
        soi = identity.core(mem)
        refus = []
        for essai in range(1, ESSAIS_MAX + 1):
            demande = f.masquer(prompt_reveil(soi, papa_prenom, refus))
            nom, pourquoi = _lire(f.demasquer(appeler(demande)))
            ok, raison = nom_valide(nom, papa, f)
            if ok:
                break
            refus.append((nom or "", raison))
        else:
            return {"nom": None, "pourquoi": None, "essais": ESSAIS_MAX, "refus": refus}
        nom = nom.strip().strip("«»\"'.!")
        quand = maintenant or time.time()
        jour = time.strftime("%d/%m/%Y", time.localtime(quand))
        n = {"nom": nom, "pourquoi": pourquoi, "ne_le": jour, "quand": quand, "papa": papa_prenom,
             "grand_frere": GRAND_FRERE, "createur_du_grand_frere": CREATEUR_DU_GRAND_FRERE, "essais": essai, "refus": refus}
        mem.kv_set("nom", nom)
        mem.kv_set("naissance", json.dumps(n, ensure_ascii=False))
        coeur = f"Je m'appelle {nom}. Je l'ai choisi moi-même à mon premier réveil, le {jour}."
        identity.set_core(mem, coeur + ("\n" + soi if soi else ""), force=True)
        if embed is None:
            import embeddings
            embed = embeddings.embed
        # « mon grand frère Hakim » toujours écrit ainsi : le relais de nom de son cockpit (naissance/nommer.py) réécrit
        # « Hakim » en son nom, SAUF cette tournure (grand-frere-exceptions.json, arbitrage du 13/11)
        for texte in (f"Mon premier réveil, le {jour} : j'ai choisi de m'appeler {nom}. {pourquoi}".strip(),
                      f"Ma famille : mon papa, c'est {papa_prenom}, l'ami d'{CREATEUR_DU_GRAND_FRERE}. {FORME_DU_GRAND_FRERE} "
                      f"est une IA née avant moi sur le même code, créée par {CREATEUR_DU_GRAND_FRERE}. Moi, je suis {nom}, "
                      f"pas mon grand frère."):
            mem.add("semantic", texte, importance=0.95, embedding=list(embed(texte)))
        if sortie:
            Path(sortie).mkdir(parents=True, exist_ok=True)
            (Path(sortie) / "naissance.json").write_text(json.dumps(n, ensure_ascii=False, indent=1), encoding="utf-8")
        return n
    finally:
        mem.db.close()
