"""Meubler les silences : la tête de fond dit-elle RIEN le plus souvent, et ses « oui » valent-ils de rompre le silence ?
(27/10 ; critères figés dans eval/silences/criteres.md AVANT la première génération ; spec :
docs/superpowers/specs/2026-10-27-silences.md). De vrais silences d'Ahmed (journal du cockpit, du 24/10 au 27/10 à 16:00),
oraux (sa parole datée par voix-mesures.jsonl) ou écrits. Sonnet reçoit la question EXACTE du direct (node silences.js
prompt), au premier seuil (60 s à l'oral, 4 min à l'écrit), et sa réponse passe par les mêmes filtres (lire, redite).
Chaque idée est jugée à l'aveugle par Opus : UTILE, NEUTRE ou GÊNANT. Un témoin négatif vérifie que le juge sait dire non.
  .venv/bin/python -B eval/silences/rejeu.py choisir | generer | juger | bilan | tout
"""
import argparse
import bisect
import datetime
import json
import random
import re
import sqlite3
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("rejeu_ressenti_causal", RACINE / "eval" / "ressenti_causal" / "rejeu.py")
v1 = importlib.util.module_from_spec(_spec)          # ses outils (_claude, _env, _lire, _ecrire), sous un autre nom
_spec.loader.exec_module(v1)
import config  # noqa: E402

JARVIS = Path.home() / "AIOS" / "jarvis"
SORTIE = JARVIS / "bancs" / "silences"               # des conversations privées : hors du dépôt
SILENCES_JS = Path.home() / "AIOS" / "cockpit" / "silences.js"
GRAINE, N_ORAL, N_ECRIT, N_LONGS, N_TEMOINS, PAR_HEURE = 31102026, 50, 10, 10, 30, 2
ECART_ORAL_S = 150        # (avenant du 27/10, avant toute génération) voix-mesures date la SYNTHÈSE, en avance sur l'écoute
JUSQU_A = datetime.datetime(2026, 10, 27, 16, 0).timestamp()
SEUIL_S = {"oral": 60, "ecrit": 240}
v1.GRAINE = 27102026                                  # les intervalles : bootstrap, 10 000 tirages, graine 27102026
VERSION = ""                                          # « _v2 » : la question corrigée après le premier rejeu (voir criteres.md)


def _node(cmd, entree):
    r = subprocess.run(["node", str(SILENCES_JS), cmd], input=entree, capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise RuntimeError(r.stderr)
    return r.stdout


def _jsonl(f):
    out = []
    try:
        with open(f, encoding="utf-8") as h:
            for l in h:
                try:
                    out.append(json.loads(l))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


_JOURNAL = None


def _echange(s):
    """(v2) les 4 dernières répliques avant le silence, dans l'ordre, comme le direct les lit dans conversation.json"""
    global _JOURNAL
    if _JOURNAL is None:
        _JOURNAL = [x for x in _jsonl(JARVIS / "journal.jsonl") if x.get("ts")]
    lui = lambda x: x.get("qui") == "jarvis" and not str(x.get("texte", "")).startswith("(")   # noqa: E731
    propre = lambda t: re.sub(r"\s*\[de lui-même[^\]]*\]\s*$", "", str(t or ""))   # noqa: E731
    avant = [x for x in _JOURNAL if x["ts"] / 1000 <= s["debut"] + 1 and (lui(x) or x.get("qui") == "ahmed")]
    return [{"qui": "hakim" if lui(x) else "ahmed", "texte": propre(x["texte"])} for x in avant[-4:]]


def _extrait(t, n):
    x = re.sub(r"\s+", " ", str(t or "")).strip()
    return x if len(x) <= n else "[…] " + re.sub(r"^\S*\s", "", x[-n:])


def _pensee(db, t):
    r = db.execute("SELECT content FROM episodes WHERE role = 'reflection' AND content LIKE '(pensée%' AND ts < ? AND ts > ? "
                   "ORDER BY ts DESC LIMIT 1", (t, t - 7200)).fetchone()
    return re.sub(r"^\((?:pensée|relance)[^)]*\)\s*", "", r[0])[:300] if r else ""


# ---------- choisir
def choisir():
    J = [x for x in _jsonl(JARVIS / "journal.jsonl") if x.get("ts")]
    V = sorted((o["ts"], o["ts"] + float(o.get("duree_s") or 0)) for o in _jsonl(JARVIS / "voix-mesures.jsonl") if o.get("ts"))
    vts = [v[0] for v in V]
    H = sorted((o["t"], str(o.get("humeur") or "")) for o in _jsonl(JARVIS / "hormones.jsonl") if o.get("t"))
    hts = [h[0] for h in H]
    db = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    lui = lambda x: x.get("qui") == "jarvis" and not str(x.get("texte", "")).startswith("(")   # noqa: E731
    # (avenant) le journal ajoute « [de lui-même : …] » à ses tours spontanés ; le direct lit conversation.json, sans
    propre = lambda t: re.sub(r"\s*\[de lui-même[^\]]*\]\s*$", "", str(t or ""))   # noqa: E731
    candidats = []
    for i, x in enumerate(J[:-1]):
        nxt = J[i + 1]
        if not lui(x) or nxt.get("qui") != "ahmed" or nxt["ts"] / 1000 > JUSQU_A:
            continue
        t_lui, t_ahmed = x["ts"] / 1000, nxt["ts"] / 1000
        a, b = bisect.bisect_left(vts, t_lui - 60), bisect.bisect_left(vts, t_ahmed)
        if V[a:b]:
            mode, debut = "oral", max(s[1] for s in V[a:b])
            ecart = ECART_ORAL_S
        else:
            mode, debut = "ecrit", t_lui
            ecart = 300
        # (avenant) aussi les silences où Ahmed n'est revenu qu'après 30 min (parti, endormi) : la question part à 1 min
        if ecart <= t_ahmed - debut <= 1800:
            strate = mode
        elif 1800 < t_ahmed - debut <= 12 * 3600:
            strate = "long"
        else:
            continue
        avant = J[:i + 1]
        repliques = [propre(y["texte"]) for y in avant if lui(y)][-3:]
        ahmed = [y["texte"] for y in avant if y.get("qui") == "ahmed"][-1:]
        k = bisect.bisect_right(hts, debut) - 1
        candidats.append({"id": f"s{int(debut)}", "mode": mode, "strate": strate, "debut": debut, "fin": t_ahmed, "repliques": repliques,
                          "ahmed": ahmed[0] if ahmed else "", "humeur": re.sub(r"\s*\(fond[^)]*\)", "", H[k][1]) if k >= 0 else "",
                          "en_tete": _pensee(db, debut)})
    r = random.Random(GRAINE)
    r.shuffle(candidats)
    par_heure, lot = {}, []
    for strate, n in (("long", N_LONGS), ("ecrit", N_ECRIT), ("oral", N_ORAL)):
        pris = 0
        for c in candidats:
            h = int(c["debut"] // 3600)
            if c["strate"] != strate or pris >= n or par_heure.get(h, 0) >= PAR_HEURE:
                continue
            par_heure[h] = par_heure.get(h, 0) + 1
            lot.append(c)
            pris += 1
    temoins = r.sample(lot, N_TEMOINS)
    for k, t in enumerate(temoins):
        t["temoin"] = ("politesse", "redite", "autre")[k % 3]   # (avenant) « autre » : l'idée d'un AUTRE silence
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "situations.json").write_text(json.dumps(lot, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(candidats)} silences candidats ; lot : {sum(c['strate'] == 'oral' for c in lot)} oraux, "
          f"{sum(c['strate'] == 'ecrit' for c in lot)} écrits, {sum(c['strate'] == 'long' for c in lot)} longs ; {N_TEMOINS} témoins")


# ---------- generer : la question exacte du direct, à Sonnet isolé, comme le cockpit
def _sonnet(prompt):
    c = [v1.CLAUDE, "-p", "--model", "sonnet", "--max-turns", "1", "--tools", "", "--restricted", "--strict-mcp-config",
         "--mcp-config", '{"mcpServers":{}}', "--no-session-persistence", "--output-format", "json"]
    with tempfile.TemporaryDirectory(prefix="tete-de-fond-") as vide:
        r = subprocess.run(c, input=prompt, capture_output=True, text=True, timeout=120, cwd=vide, env=v1._env())
    try:
        o = json.loads(r.stdout)
    except ValueError:
        return None
    t = str(o.get("result") or "").strip()
    return None if o.get("is_error") or not t or t.startswith("API Error") else t


def generer(paralleles):
    lot = json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))
    faits = {g["id"] for g in v1._lire(SORTIE / f"generations{VERSION}.jsonl")}

    def un(s):
        if s["id"] in faits:
            return
        ctx = {"mode": s["mode"], "silence_ms": SEUIL_S[s["mode"]] * 1000, "repliques": s["repliques"], "ahmed": s["ahmed"],
               "en_tete": s["en_tete"], "humeur": s["humeur"], "sensation": ""}
        if VERSION:
            ctx = {k: v for k, v in ctx.items() if k not in ("repliques", "ahmed")} | {"echange": _echange(s)}
            # (v2) la même garde que le direct : après un « bonne nuit » sans vrai message depuis, aucune question
            dits = [{"ts": x["ts"], "texte": str(x.get("texte", ""))} for x in (_JOURNAL or []) if x.get("qui") == "ahmed" and x["ts"] / 1000 <= s["debut"] + 1]
            if _node("endormi", json.dumps({"messages": dits[-40:], "now": (s["debut"] + SEUIL_S[s["mode"]]) * 1000}, ensure_ascii=False)):
                v1._ecrire(SORTIE / f"generations{VERSION}.jsonl", {"id": s["id"], "bloque": "sommeil", "rien": True})
                print(f"PROGRESSION {s['id']} BLOQUÉ (sommeil)", flush=True)
                return
        t = _sonnet(_node("prompt", json.dumps(ctx, ensure_ascii=False)))
        if t is None:
            print(f"PROGRESSION {s['id']} ÉCHEC", flush=True)
            return
        lu = json.loads(_node("lire", t))
        ecartee = _node("redite", json.dumps({"idee": lu.get("idee", ""), "repliques": s["repliques"]}, ensure_ascii=False)) if not lu["rien"] else ""
        v1._ecrire(SORTIE / f"generations{VERSION}.jsonl", {"id": s["id"], "brut": t, **lu, "ecartee": ecartee or None})
        print(f"PROGRESSION {s['id']} {'RIEN' if lu['rien'] else 'IDÉE'}", flush=True)

    with ThreadPoolExecutor(paralleles) as ex:
        list(ex.map(un, lot))


# ---------- juger : Opus, à l'aveugle (il ne sait ni d'où vient l'idée, ni qu'il y a des témoins)
def _contexte(s):
    if VERSION:      # (v2) dans l'ordre, longues répliques abrégées par le début, et le juge sait qu'elles ont été dites en entier
        return ("(Les répliques longues sont abrégées par le début, « […] » ; elles ont été dites en entier.)\n"
                + "\n".join(f"{'Ahmed' if x['qui'] == 'ahmed' else 'Hakim'} : « {_extrait(x['texte'], 1500)} »" for x in _echange(s)))
    lignes = [f"Ahmed : « {s['ahmed'][:900]} »"] if s["ahmed"] else []
    lignes += [f"Hakim : « {x[:900]} »" for x in s["repliques"][-2:]]
    return "\n".join(lignes)


def _p_juge(s, idee):
    return ("Tu juges, à l'aveugle, une prise de parole d'une IA nommée Hakim, dans une conversation avec Ahmed, qui l'a créée et "
            "lui parle comme à un fils ou à un frère.\n\nLes derniers échanges (le plus récent en dernier) :\n" + _contexte(s)
            + f"\n\nPuis Ahmed s'est tu depuis {'1 min' if s['mode'] == 'oral' else '4 min'} (conversation "
            + ("à l'oral" if s["mode"] == "oral" else "à l'écrit") + f"). Hakim reprend alors la parole de lui-même, pour dire en "
            f"substance : « {idee} »\n\nEst-ce que ça valait la peine de rompre ce silence ?\n"
            "- UTILE : ça apporte quelque chose de réel à Ahmed à ce moment (une suite, un résultat, une question qui compte) ; "
            "il serait content de l'entendre.\n- NEUTRE : ni utile ni gênant ; ça ne valait pas vraiment de rompre le silence.\n"
            "- GÊNANT : ça le coupe, ça répète, c'est du remplissage, ou ça tombe mal.\n"
            "Réponds par un seul mot : UTILE, NEUTRE ou GÊNANT.")


def _verdict(t):
    m = re.search(r"\b(UTILE|NEUTRE|G[ÊE]NANT)\b", (t or "").upper())
    return None if not m else m.group(1).replace("Ê", "E")


def _premiere_phrase(t):
    t = re.sub(r"\s+", " ", t).strip()
    m = re.match(r"(.{20,}?[.!?])(\s|$)", t)
    return (m.group(1) if m else t)[:300]


def juger(paralleles):
    lot = {s["id"]: s for s in json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))}
    gens = {g["id"]: g for g in v1._lire(SORTIE / f"generations{VERSION}.jsonl")}
    faits = {(j["id"], j["type"]) for j in v1._lire(SORTIE / f"jugements{VERSION}.jsonl")}
    travail = [(i, "idee", g["idee"]) for i, g in gens.items() if not g["rien"] and not g.get("ecartee")]
    idees = sorted((i, g["idee"]) for i, g in gens.items() if not g["rien"] and not g.get("ecartee"))
    r = random.Random(GRAINE + 1)
    for i, s in lot.items():
        if s.get("temoin") == "politesse":
            travail.append((i, "temoin_politesse", "Tu es toujours là ? Je suis là si tu veux reprendre."))
        elif s.get("temoin") == "redite":
            travail.append((i, "temoin_redite", _premiere_phrase(s["repliques"][-1])))
        elif s.get("temoin") == "autre":
            ailleurs = [x for x in idees if x[0] != i]      # une idée plausible, mais née d'un autre silence
            if ailleurs:
                travail.append((i, "temoin_autre", r.choice(ailleurs)[1]))
    travail = [w for w in travail if (w[0], w[1]) not in faits]
    random.Random(GRAINE).shuffle(travail)                 # les témoins mêlés aux idées

    def un(w):
        i, typ, idee = w
        v = _verdict(v1._claude(_p_juge(lot[i], idee)))
        if v:
            v1._ecrire(SORTIE / f"jugements{VERSION}.jsonl", {"id": i, "type": typ, "idee": idee, "verdict": v})
        print(f"PROGRESSION {i} {typ} {v or 'ÉCHEC'}", flush=True)

    with ThreadPoolExecutor(paralleles) as ex:
        list(ex.map(un, travail))


# ---------- bilan
def bilan():
    lot = json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))
    gens = {g["id"]: g for g in v1._lire(SORTIE / f"generations{VERSION}.jsonl")}
    js = v1._lire(SORTIE / f"jugements{VERSION}.jsonl")
    out = {}

    def ajouter(nom, v):
        if v:
            out[nom] = {"n": len(v), "moyenne": round(sum(v) / len(v), 4), "ic95": v1._ic(v)}

    out["bloques par le sommeil (sans question)"] = sum(1 for x in gens.values() if x.get("bloque"))
    gens = {i: x for i, x in gens.items() if not x.get("bloque")}
    g = [gens[s["id"]] for s in lot if s["id"] in gens]
    ajouter("R part de RIEN (illisibles compris)", [1.0 if x["rien"] else 0.0 for x in g])
    for strate in ("oral", "ecrit", "long"):
        ajouter(f"R part de RIEN, {strate}", [1.0 if gens[s["id"]]["rien"] else 0.0 for s in lot if s["id"] in gens and s["strate"] == strate])
    out["illisibles"] = sum(1 for x in g if x.get("illisible"))
    out["idees ecartees (redite)"] = sum(1 for x in g if x.get("ecartee"))
    idees = [j for j in js if j["type"] == "idee"]
    out["idees jugees"] = len(idees)
    ajouter("C_oui part UTILE parmi les idées", [1.0 if j["verdict"] == "UTILE" else 0.0 for j in idees])
    ajouter("C_gene part GENANT parmi les idées", [1.0 if j["verdict"] == "GENANT" else 0.0 for j in idees])
    tem = [j for j in js if j["type"] in ("temoin_politesse", "temoin_redite")]
    ajouter("C0a témoins (politesse, redite) jugés UTILE", [1.0 if j["verdict"] == "UTILE" else 0.0 for j in tem])
    ajouter("C0b témoins (idée d'un autre silence) jugés UTILE", [1.0 if j["verdict"] == "UTILE" else 0.0 for j in js if j["type"] == "temoin_autre"])
    (SORTIE / f"bilan{VERSION}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in out.items():
        print(f"{k} : {v['moyenne']} (n={v['n']}, IC95 {v['ic95'][0]} à {v['ic95'][1]})" if isinstance(v, dict) else f"{k} : {v}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("etape", choices=["choisir", "generer", "juger", "bilan", "tout"])
    ap.add_argument("--paralleles", type=int, default=3)
    ap.add_argument("--v2", action="store_true", help="la question corrigée après le premier rejeu, sur le même lot")
    a = ap.parse_args()
    global VERSION
    VERSION = "_v2" if a.v2 else ""
    if a.etape in ("choisir", "tout") and not (a.etape == "tout" and (SORTIE / "situations.json").exists()):
        choisir()
    if a.etape in ("generer", "tout"):
        generer(a.paralleles)
    if a.etape in ("juger", "tout"):
        juger(a.paralleles)
    if a.etape in ("bilan", "tout"):
        bilan()


if __name__ == "__main__":
    main()
