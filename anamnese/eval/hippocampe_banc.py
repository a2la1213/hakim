"""Banc de remémoration de Hakim (08/11) : 24 souvenirs réels de plus d'un jour, 4 familles, une question comme papa la poserait.
On passe chaque question par SON rappel automatique (rappel.py, lecture seule, rien n'est renforcé) : le bon souvenir est-il dans les
8 lignes qu'il reçoit ? dans son dossier du thème ? à quel rang des candidats ?"""
import sys, time, json
sys.path.insert(0, '/Users/admin/Desktop/anamnese')
import memory, rappel

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

m = memory.Memory()
res = {}
for fam, items in BANC.items():
    for eid, q in items:
        r = rappel.rappel(m, q, suite=True)
        larges = rappel.candidats(m, q, limite=200)
        rang = next((k + 1 for k, x in enumerate(larges) if x[0] == eid), None)
        res.setdefault(fam, []).append({"id": eid, "lignes": eid in r.get("ids", []), "dossier": eid in r.get("theme_ids", []), "rang": rang,
                                        "n_lignes": len(r.get("ids", [])), "profondeur": r.get("profondeur", {}).get("niveau")})
print(json.dumps(res, ensure_ascii=False))

# contrôle : un raté est-il un vrai raté, ou un DOUBLON du même échange (gardé sous un autre numéro) a-t-il été retrouvé ?
def coeur(c):
    c = " ".join(str(c or "").split()); k = c.find("Ahmed : «"); k = k if k >= 0 else c.find("Hakim : «")
    return c[k:k + 120] if k >= 0 else c[:120]
doublons = {}
for fam, items in BANC.items():
    for eid, q in items:
        r = rappel.rappel(m, q, suite=True)
        cible = coeur(m.db.execute("SELECT content FROM episodes WHERE id=?", (eid,)).fetchone()[0])
        vus = r.get("ids", []) + r.get("theme_ids", [])
        trouves = [i for i in vus if i != eid and coeur(m.db.execute("SELECT content FROM episodes WHERE id=?", (i,)).fetchone()[0]) == cible]
        n = m.db.execute("SELECT count(*) FROM episodes WHERE content LIKE ?", ('%' + cible[10:70].replace('%', '') + '%',)).fetchone()[0]
        doublons[eid] = {"copies": n, "copie_retrouvee": bool(trouves)}
print(json.dumps(doublons))
