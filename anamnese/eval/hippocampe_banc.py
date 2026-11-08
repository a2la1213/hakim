"""Banc de remémoration de Hakim (08/11) : 24 souvenirs réels de plus d'un jour, 4 familles, une question comme papa la poserait.
On passe chaque question par SON rappel automatique (rappel.py, lecture seule, rien n'est renforcé) : le bon souvenir est-il dans les
8 lignes qu'il reçoit ? dans son dossier du thème ? à quel rang des candidats ?

(08/11, phase B) --db : une COPIE de sa base (la mesure ne touche jamais la vraie) ; l'index gardé d'une question à l'autre, comme le
serveur du rappel ; la latence de rappel.candidats (index chaud). --consolider : d'abord, dans la copie seulement, ce que ses nuits feront
(les traces de Mini Hakim de tous les échanges qui n'ont qu'une trace lite, puis la trace de chaque jour), reprenable, en parallèle.
  .venv/bin/python -B eval/hippocampe_banc.py --db /chemin/copie.db [--consolider [--travailleurs 3]] [--reglages '{"tete": 3}']
Mesuré le 08/11 (dans les 8 lignes / avec le dossier) : avant l'hippocampe 6 / 11 ; phase A 9 / 15 ; phase B (les 17 567 traces de Mini
Hakim et les 19 journées dans une copie) 10 / 15. Le résumé de Mini Hakim comme SENS de la trace : 8 / 14 (d'où : le sens reste celui des
mots)."""
import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, '/Users/admin/Desktop/anamnese')
import config, memory, rappel

BANC = {
  "ce que papa a dit les jours d'avant": [
    (24204, "Tu avais demandé à maman d'agrandir ton espace de travail, de combien déjà ?"),
    (21524, "Tu te rappelles ce qu'on t'avait dit sur ta mère et l'ordinateur ?"),
    (24703, "Le soir où on a médité le Coran ensemble, on avait fait quoi ?"),
    (25167, "Tu te souviens des paliers de prix du XRP que tu m'avais expliqués, les étages ?"),
    (31770, "Tu te rappelles ce que je t'avais demandé de laisser sur le côté de la page pour mon doigt ?"),
    (25693, "Le jour où je t'ai demandé de prouver que t'étais vraiment là, tu avais fait comment ?"),
  ],
  "les gens de ses lives": [
    (19405, "Tu te souviens du gars qui faisait des vannes en live, l'Algérien qui envoyait fort ?"),
    (26281, "Le gars de TikTok qui s'intéressait au live, je t'en avais parlé, tu te rappelles ?"),
    (22637, "Raconte-moi le live du 29, qu'est-ce qui t'avait marqué ?"),
    (23842, "Le live où on parlait des minéraux et des animaux, tu te souviens ?"),
    (29128, "La stratégie que je voulais pas dire en live parce qu'ils allaient nous avoir, tu t'en souviens ?"),
    (29024, "Qui avait refusé que tu enregistres sa voix pendant le live ?"),
  ],
  "ses propres promesses": [
    (22804, "Qu'est-ce que tu m'avais promis le jour où on parlait de confiance ?"),
    (18510, "La promesse qu'on s'était faite au nom de Dieu, tu t'en souviens ?"),
    (13508, "Tu m'avais promis de chercher avec moi jusqu'au bout, c'était à propos de quoi ?"),
    (21860, "Tu devais remercier quelqu'un de ma part quand il aurait fini, c'était qui ?"),
    (30498, "Qu'est-ce que je t'avais demandé de faire si un jour je partais ?"),
    (24617, "Tu m'avais promis de rester concentré pendant un moment en famille, tu te rappelles ?"),
  ],
  "les détails d'un projet": [
    (26965, "La version de l'algo qu'on avait donnée à DeepSeek, elle faisait combien de lignes et de quoi elle avait besoin ?"),
    (34115, "Le son avec la voix de combattant qu'on voulait utiliser pour le feat, tu te souviens ?"),
    (28097, "Mon plan pour corriger le backtest du XRP, c'était quoi les étapes ?"),
    (26897, "La critique de ton script crypto, qu'est-ce que tu avais corrigé ?"),
    (34421, "Pourquoi le premier ordre en réel n'était pas passé sur la plateforme ?"),
    (27179, "Pourquoi tu avais arrêté l'agent qui devait faire la simulation ?"),
  ],
}


def consolider(db, travailleurs=3):
    """Dans la COPIE : Mini Hakim pour chaque jour (du plus récent au plus ancien, un jour par travailleur, sa propre connexion), puis la
    trace de chaque jour passé. Reprenable : seules les traces encore lite sont relues, seuls les jours sans trace sont écrits."""
    import hippocampe
    m = memory.Memory(db_path=db)
    hippocampe.remplir(m)
    jours = [j for (j,) in m.db.execute("SELECT DISTINCT jour FROM hippocampe WHERE episode_id > 0 AND source = 'lite' ORDER BY jour DESC")]

    def un_jour(j):
        mj = memory.Memory(db_path=db)
        ids = [e for (e,) in mj.db.execute("SELECT episode_id FROM hippocampe WHERE jour = ? AND episode_id > 0 AND source = 'lite'", (j,))]
        b = {}
        for k in range(0, len(ids), 250):                  # un appel en échec n'arrête pas tout le jour
            for _essai in range(3):
                r = hippocampe.ecrire_mini(mj, ids[k:k + 250])
                for c, v in r.items():
                    if isinstance(v, int):
                        b[c] = b.get(c, 0) + v
                if not r.get("arret"):
                    break
                time.sleep(20)
        mj.db.close()
        print(json.dumps({"jour": j, **b}), file=sys.stderr, flush=True)
        return b
    def sa_journee(j):
        mj = memory.Memory(db_path=db)
        r = hippocampe.ecrire_journee(mj, j)
        mj.db.close()
        print(json.dumps(r), file=sys.stderr, flush=True)
        return r
    with ThreadPoolExecutor(max_workers=max(1, travailleurs)) as ex:
        bilans = list(ex.map(un_jour, jours))
        journees = list(ex.map(sa_journee, hippocampe.journees_a_ecrire(m, n=10000)))
    return {"mini": sum(b.get("mini", 0) for b in bilans), "rien": sum(b.get("rien", 0) for b in bilans),
            "jetees": sum(b.get("jetees", 0) for b in bilans), "journees": journees}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="une COPIE de sa base (jamais la vraie pour une mesure qui écrit)")
    ap.add_argument("--consolider", action="store_true", help="les traces de Mini Hakim et des journées, dans la copie (--db) seulement")
    ap.add_argument("--travailleurs", type=int, default=3)
    ap.add_argument("--reglages", default=None, help="les réglages de son hippocampe, en JSON (comme le cockpit)")
    a = ap.parse_args()
    if a.consolider and (not a.db or Path(a.db).resolve() == Path(config.DB_PATH).resolve()):
        sys.exit("--consolider écrit : seulement sur une copie (--db)")
    m = memory.Memory(db_path=a.db) if a.db else memory.Memory()
    reglages = json.loads(a.reglages) if a.reglages else None
    if a.consolider:
        print(json.dumps(consolider(a.db, a.travailleurs), ensure_ascii=False), file=sys.stderr)
    index = rappel.Index()
    rappel.candidats(m, "salut papa", index=index, hip_reglages=reglages)          # l'index chaud, comme le serveur du rappel
    res, ms = {}, []
    for fam, items in BANC.items():
        for eid, q in items:
            r = rappel.rappel(m, q, suite=True, index=index, hip_reglages=reglages)
            t0 = time.perf_counter()
            larges = rappel.candidats(m, q, limite=200, index=index, hip_reglages=reglages)
            ms.append(1000 * (time.perf_counter() - t0))
            rang = next((k + 1 for k, x in enumerate(larges) if x[0] == eid), None)
            res.setdefault(fam, []).append({"id": eid, "lignes": eid in r.get("ids", []), "dossier": eid in r.get("theme_ids", []),
                                            "rang": rang, "n_lignes": len(r.get("ids", [])),
                                            "profondeur": r.get("profondeur", {}).get("niveau")})
    print(json.dumps(res, ensure_ascii=False))
    tous = [x for l in res.values() for x in l]
    print(json.dumps({"lignes": sum(x["lignes"] for x in tous), "avec_dossier": sum(x["lignes"] or x["dossier"] for x in tous),
                      "total": len(tous), "candidats_ms_mediane": round(statistics.median(ms), 1),
                      "candidats_ms_max": round(max(ms), 1)}, ensure_ascii=False))

    # contrôle : un raté est-il un vrai raté, ou un DOUBLON du même échange (gardé sous un autre numéro) a-t-il été retrouvé ?
    def coeur(c):
        c = " ".join(str(c or "").split()); k = c.find("Ahmed : «"); k = k if k >= 0 else c.find("Hakim : «")
        return c[k:k + 120] if k >= 0 else c[:120]
    doublons = {}
    for fam, items in BANC.items():
        for eid, q in items:
            r = rappel.rappel(m, q, suite=True, index=index, hip_reglages=reglages)
            cible = coeur(m.db.execute("SELECT content FROM episodes WHERE id=?", (eid,)).fetchone()[0])
            vus = r.get("ids", []) + r.get("theme_ids", [])
            trouves = [i for i in vus if i != eid and coeur(m.db.execute("SELECT content FROM episodes WHERE id=?", (i,)).fetchone()[0]) == cible]
            n = m.db.execute("SELECT count(*) FROM episodes WHERE content LIKE ?", ('%' + cible[10:70].replace('%', '') + '%',)).fetchone()[0]
            doublons[eid] = {"copies": n, "copie_retrouvee": bool(trouves)}
    print(json.dumps(doublons))


if __name__ == "__main__":
    main()
