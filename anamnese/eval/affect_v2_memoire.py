"""Cinquième passage : la trace émotionnelle des souvenirs (M1 à M7, figés AVANT dans eval/affect_v2_predictions.md,
commit 0eb744a). Sur une COPIE de la vraie mémoire (la vraie n'est jamais touchée), interrupteur v2 allumé dans la
copie, comparé à l'interrupteur éteint. Seuls des agrégats sortent (aucun contenu de souvenir).
Usage : .venv/bin/python eval/affect_v2_memoire.py [réglage, ex. D2-doux]"""
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import affect  # noqa: E402
import config  # noqa: E402
import embeddings  # noqa: E402
import supersession_bench  # noqa: E402
from memory import Memory  # noqa: E402


def copie(dossier):
    dest = Path(dossier) / "copie.db"
    src = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    d = sqlite3.connect(str(dest))
    src.backup(d)
    d.close()
    src.close()
    return dest


def etat(mem, nom, now):
    """Met la copie dans un état : off (v1), neutre, sombre, agite."""
    mem.kv_set("affect", json.dumps({**affect.bases(v2=True), "_ts": now - 3600}))
    if nom == "off":
        mem.kv_set("affect_v2", "0")
        mem.kv_set("affect", json.dumps({**affect.bases(), "_ts": now}))
        return
    mem.kv_set("affect_v2", "1")
    if nom == "sombre":
        for k in range(4):
            affect.event(mem, "echec", 1.0, now=now - 1800 + k * 300)
    elif nom == "agite":
        affect.event(mem, "probleme", 1.0, now=now - 120)
        affect.event(mem, "nouveaute", 1.0, now=now - 60, sujet="un bruit jamais entendu")
        affect.event(mem, "probleme", 1.0, now=now - 30)


def requetes():
    out = []
    for f in ("queries.jsonl", "queries_heldout.jsonl"):
        for l in open(Path(__file__).resolve().parent / f, encoding="utf-8"):
            if l.strip():
                o = json.loads(l)
                out.append((o["query"], set(o.get("expected") or [])))
    return out


def tops(mem, qs):
    return [[r[5] for r in mem.retrieve(q, embeddings.embed(q), top_k=6, reconsolidate=False, avec_ids=True)]
            for q, _e in qs]


def rappel6(tous, qs):
    return sum(len(set(t) & e) / len(e) for t, (_q, e) in zip(tous, qs) if e) / max(1, sum(1 for _q, e in qs if e))


def moyenne_enc(mem, tous, col):
    ids = [i for t in tous for i in t]
    vals = [r[0] for i in ids for r in mem.db.execute(f"SELECT {col} FROM episodes WHERE id=?", (i,)) if r[0] is not None]
    return sum(vals) / len(vals) if vals else None


def recouvrement(a, b):
    return sum(len(set(x) & set(y)) / max(1, len(x)) for x, y in zip(a, b)) / max(1, len(a))


def m5(dossier):
    import echanges
    import migrations
    imps = []
    for alarme in (False, True):
        m = Memory(db_path=Path(dossier) / f"m5-{alarme}.db")
        migrations.migrate(m.db)
        m.kv_set("affect_v2", "1")
        m.kv_set("affect", json.dumps({**affect.bases(v2=True), "_ts": time.time()}))
        if alarme:
            affect.event(m, "echec", 1.0, sujet="une panne jamais vue")
        echanges.memoriser(m, {"ahmed": "on regarde le planning de la semaine", "hakim": "D'accord.",
                               "ts": time.time() * 1000}, embed=lambda t: [1.0] * 8)
        imps.append(m.db.execute("SELECT importance FROM episodes WHERE role='episodic'").fetchone()[0])
        m.db.close()
    d = round(imps[1] - imps[0], 3)
    return {"calme": imps[0], "alarme": imps[1], "ecart": d, "tenue": 0.05 <= d <= 0.15}


def m6(dossier):
    import parole_affect
    msgs = json.loads((Path(__file__).resolve().parent / "affect_v2_paroles.json").read_text(encoding="utf-8"))["messages"]
    vp = fp = fn = rien_declenche = rien = 0
    for texte, attendus in msgs:
        trouves = {n for n, _i in parole_affect.evaluer(texte)}
        attendus = set(attendus)
        vp += len(trouves & attendus)
        fp += len(trouves - attendus)
        fn += len(attendus - trouves)
        if not attendus:
            rien += 1
            rien_declenche += bool(trouves)
    precision, rappel = vp / max(1, vp + fp), vp / max(1, vp + fn)
    # le double compte : Hakim a noté « chaleur_user » il y a une minute
    m = Memory(db_path=Path(dossier) / "m6.db")
    m.kv_set("affect_v2", "1")
    j = Path(dossier) / "m6.jsonl"
    t = time.time()
    j.write_text(json.dumps({"ts": t - 60, "nom": "chaleur_user", "source": "hakim"}) + "\n")
    sans_double = parole_affect.appliquer(m, "merci frero", "projets/anamnese", t, j) == []
    m.db.close()
    return {"precision": round(precision, 3), "rappel": round(rappel, 3), "rien_qui_declenche": f"{rien_declenche}/{rien}",
            "sans_double_compte": sans_double,
            "tenue": precision >= 0.8 and rappel >= 0.7 and rien_declenche <= 1 and sans_double}


def m7(dossier):
    import consolidate
    res = {}
    for v2 in (True, False):
        db = Path(dossier) / f"m7-{v2}.db"
        con = sqlite3.connect(str(db))
        con.execute("CREATE TABLE episodes (id INTEGER PRIMARY KEY, ts REAL, role TEXT, content TEXT, rubric_id INTEGER, "
                    "enc_valence REAL, enc_arousal REAL, enc_affect TEXT, provenance TEXT)")
        con.execute("CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT)")
        con.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT, ts REAL)")
        con.execute("INSERT INTO episodes (ts, role, content, enc_affect) VALUES (100, 'episodic', 'a', ?)", (json.dumps({"c": 0.8}),))
        con.execute("INSERT INTO episodes (ts, role, content, enc_valence, enc_arousal) VALUES (101, 'episodic', 'b', 0.5, 0.4)")
        if v2:
            con.execute("INSERT INTO kv VALUES ('affect_v2', '1', 0)")
        con.commit()
        con.close()
        res["v2" if v2 else "v1"] = [s["emotion"] for s in consolidate.lot_a_consolider(0, db_path=db)]
    res["tenue"] = res["v2"] == [True, False] and res["v1"] == [False, False]
    return res


def main():
    reglage = sys.argv[1] if len(sys.argv) > 1 else None
    if reglage:
        import affect_v2_soudain
        affect_v2_soudain.regler(reglage)
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as dossier:
        mem = Memory(db_path=copie(dossier))
        now = time.time()
        qs = requetes()
        res = {"reglage": reglage}
        mesures = {}
        for nom in ("off", "neutre", "sombre", "agite"):
            etat(mem, nom, now)
            bons, _l = supersession_bench.mesurer(mem)
            t = tops(mem, qs)
            mesures[nom] = {"perimes": bons, "rappel6": rappel6(t, qs), "tops": t,
                            "valence": moyenne_enc(mem, t, "enc_valence"), "eveil": moyenne_enc(mem, t, "enc_arousal")}
        o = mesures["off"]
        res["M1"] = {n: mesures[n]["perimes"] for n in mesures} | {"sur": len(supersession_bench.CAS),
                    "tenue": all(mesures[n]["perimes"] >= o["perimes"] for n in ("neutre", "sombre", "agite"))}
        res["M2"] = {n: round(mesures[n]["rappel6"], 3) for n in mesures} | {
            "tenue": all(mesures[n]["rappel6"] >= o["rappel6"] - 0.02 for n in ("neutre", "sombre", "agite"))}
        ne, so, ag = mesures["neutre"], mesures["sombre"], mesures["agite"]
        rs, ra = recouvrement(so["tops"], ne["tops"]), recouvrement(ag["tops"], ne["tops"])
        res["M3"] = {"valence_neutre": round(ne["valence"], 4), "valence_sombre": round(so["valence"], 4),
                     "recouvrement": round(rs, 3), "tenue": so["valence"] >= ne["valence"] - 0.01 and rs >= 0.8}
        res["M4"] = {"eveil_neutre": round(ne["eveil"], 4), "eveil_agite": round(ag["eveil"], 4),
                     "recouvrement": round(ra, 3), "tenue": ag["eveil"] > ne["eveil"] and ra >= 0.8}
        res["M5"] = m5(dossier)
        res["M6"] = m6(dossier)
        res["M7"] = m7(dossier)
        mem.db.close()
    res["rates"] = [k for k, v in res.items() if isinstance(v, dict) and not v.get("tenue")]
    res["tous"] = not res["rates"]
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sortie = Path(__file__).resolve().parent / "data" / f"affect_v2_memoire-{time.strftime('%Y%m%d-%H%M')}.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"détail : {sortie}")


if __name__ == "__main__":
    main()
