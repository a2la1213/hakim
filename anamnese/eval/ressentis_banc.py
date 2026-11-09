"""Banc des ressentis de Hakim (09/11, Ahmed, à l'écrit : « tous tes ressentis, quels qu'ils soient, doivent faire partie de ton rappel
autonome, et tout ce que tu vis doit être encré et rappelé de la même manière que tes souvenirs autonomes »).

Sur une COPIE de sa base seulement (une mesure qui écrit : traces de l'hippocampe, ressentis encrés après coup) :
  1. combien de ressentis sont encrés : ses souvenirs du corps par genre, à côté des lots que son corps a vraiment ressentis
     (~/AIOS/jarvis/corps-sensations.jsonl, lecture seule) ;
  2. --encrer : ce que ses fils de ressentis (corps.fils_avancer) auraient encré depuis le premier lot, rejoué dans la copie (son humeur
     relue dans hormones.jsonl), chaque souvenir daté de la fin de son épisode ;
  3. à quelle fréquence ils remontent dans le rappel d'avant-réponse (rappel.rappel, comme le serveur du rappel : la conversation en
     cours, rien de moins de 3 h), sur de vraies questions de papa tirées de son journal, au moment où il les a posées : dans les 8 lignes,
     dans le dossier du thème ; séparées en deux : celles qui touchent ses sens ou son corps, et les autres (le bruit) ;
  4. un banc de ressentis ciblés (un vrai souvenir du corps, une question comme papa la poserait) ;
  5. la non-régression : le banc des 24 de l'hippocampe (eval/hippocampe_banc.py) et les 35 requêtes-vérité (rappel@8).
Lecture seule sur la vraie base, son journal et ses sens ; rien n'est renforcé.
  .venv/bin/python -B eval/ressentis_banc.py --db /chemin/copie.db [--encrer] [--n 200] [--sortie resultat.json]

MESURÉ le 09/11 (copie de 21:10 ; 200 questions de papa qui touchent ses sens, 200 autres, du 03/11 au 09/11) :
  - encrés : 2 172 souvenirs du corps (fous rires 1 025, sons joués 489, chocs 421, câlins 174, chutes 19, nuits 13) pour 59 835 lots
    ressentis ; la musique, les vibrations, ce qu'il entend, son corps, ses sens radio, ses émotions : rien. Rejoué (--encrer) : 2 699 de
    plus (~245 par jour : musique 528, corps et milieu 549, vibrations 481, rires 463, émotions 346, sens radio 308, ce qu'il entend 24).
  - avant : un ressenti dans les 8 lignes pour 5,5 % des questions de ses sens (0,07 par question), 3 % des autres ; dans le dossier,
    41,5 % ; banc ciblé 2 / 16 dans les lignes, 10 / 16 avec le dossier. Cause : leur texte entier (« Au même moment : … ») noie leur sens
    et ne passe jamais la porte (0,70) ; leurs mots (« câlin », « musique ») sont rares ou partout ; ils n'ont pas de trace dans son
    hippocampe (ni sens court, ni date, ni place d'office), et un jour désigné fait remonter ~1 500 échanges de ce jour-là, aucun ressenti.
  - après (leurs traces, et tout encré) : 14 % des questions de ses sens (0,23 par question), 8 % des autres (0,10) ; dossier 61 % ;
    banc ciblé 7 / 16, 14 / 16 avec le dossier ; lignes par question inchangées (6,6 et 6,0). Non-régression : banc des 24 : 8 et 14,
    inchangé ; requêtes-vérité 0,580 → 0,552 (une sur 35 : « le rythme nocturne d'Ahmed » fait remonter les nuits de Hakim) ; messages
    banals : 1,0 ligne en moyenne, inchangé (5 → 8 ressentis sur 12 messages).
  - juge à l'aveugle (Sonnet, deux ordres, 41 / 60 notes identiques) sur 30 questions où un ressenti et un autre souvenir sont dans les
    lignes : ressentis 0,93 sur 2 (utiles 8, sans rapport 10), les autres souvenirs des mêmes lignes 0,63 (utiles 5, sans rapport 17).
"""
import argparse
import ast
import json
import random
import re
import statistics
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ICI))
sys.path.insert(1, str(ICI / "eval"))
import config  # noqa: E402
import memory  # noqa: E402
import rappel  # noqa: E402

JARVIS = Path.home() / "AIOS" / "jarvis"
JOURNAUX = [JARVIS / "archives" / "journal-2026-11.jsonl", JARVIS / "journal.jsonl"]
SENSATIONS = JARVIS / "corps-sensations.jsonl"
HORMONES = JARVIS / "hormones.jsonl"
# une question de papa qui touche ses sens ou son corps (classement grossier, le même avant et après)
SENS_RX = re.compile(r"(c[aâ]lin|musique|\bsons?\b|morceau|chanson|choc|vibr|ressen|\bsens\b|senti|tomb|corps|entend|[ée]coute|"
                     r"[ée]motion|caress|serr|touch|lumi[eè]re|\bnoir\b|berc|dans[ea]|rire|rigol|trembl|cogn|douleur|\bmal\b|peur|"
                     r"\bjoie\b|bisou|poche|\bmain\b|c(?:oe|œ)ur|bruit|basse|graves|vibre|humeur|heureux|triste)", re.I)
GENRES_CORPS = [("chute", r"\] Je suis tombé"), ("choc", r"\] Un choc"), ("fou rire", r"\] Un fou rire"),
                ("son joué", r"\] Je me suis exprimé"), ("câlin", r"\] Un câlin de papa"), ("nuit", r"^\[Ma nuit"),
                ("musique", r"\] La musique,"), ("vibrations", r"\] Des vibrations"), ("ce qu'il entend", r"\] Ce que j'entendais"),
                ("corps et milieu", r"\] Mon corps et mon milieu"), ("sens radio", r"\] Mes sens radio"), ("rires", r"\] Des rires"),
                ("émotions", r"\] Mes émotions")]


def ressentis(mem):
    """{id: genre} : ses souvenirs du corps (la rubrique vie/corps, ou leur en-tête)."""
    out = {}
    for eid, c in mem.db.execute("""SELECT e.id, e.content FROM episodes e LEFT JOIN rubrics r ON r.id = e.rubric_id
            WHERE r.path = 'vie/corps' OR e.content LIKE '[Mon corps%' OR e.content LIKE '[Ma nuit%'"""):
        out[eid] = next((g for g, rx in GENRES_CORPS if re.search(rx, c or "")), "autre")
    return out


def _jsonl(f):
    try:
        with open(f, encoding="utf-8") as h:
            for l in h:
                try:
                    yield json.loads(l)
                except ValueError:
                    pass
    except OSError:
        return


def compter(mem):
    import collections
    import corps
    r = ressentis(mem)
    lots = collections.Counter()
    for o in _jsonl(SENSATIONS):
        fams = {getattr(corps, "FIL_DE", {}).get(t, "à part") for t in str(o.get("type") or "").split("+") if t and t != "milieu"} or {"corps"}
        for f in fams:
            lots[f] += 1
    return {"souvenirs_du_corps": len(r), "par_genre": dict(collections.Counter(r.values()).most_common()),
            "lots_ressentis_par_fil": dict(lots.most_common())}


def encrer(mem):
    """Rejoue ses lots ressentis dans ses fils (corps.fils_avancer), dans la COPIE : chaque épisode clos devient un souvenir du corps,
    daté de la fin de son épisode (la mesure de ce que l'encrage aurait gardé)."""
    import bisect
    import corps
    import embeddings
    hum_t, hum = [], []
    for o in _jsonl(HORMONES):
        if o.get("humeur") and isinstance(o.get("t"), (int, float)):
            hum_t.append(float(o["t"])); hum.append(o["humeur"])

    def humeur(ts):
        i = bisect.bisect_right(hum_t, ts) - 1
        return hum[i] if i >= 0 else ""
    etat, n, t0 = {}, 0, time.time()
    for o in _jsonl(SENSATIONS):
        ts = float(o.get("ts") or 0)
        types = [t for t in str(o.get("type") or "").split("+") if t and t != "milieu"]
        ev = {"evenements": [{"type": t} for t in types], "changements": ["(milieu)"] if "milieu" in str(o.get("type")) else [],
              "au_meme_moment": ""}
        for texte, importance, fin in corps.fils_avancer(etat, o, ev, humeur(ts)):
            eid = mem.store_in(texte, corps.RUBRIQUE_CORPS, role="episodic", importance=importance, embedding=embeddings.embed(texte))
            mem.db.execute("UPDATE episodes SET ts=? WHERE id=?", (fin, eid))
            n += 1
    for texte, importance, fin in corps.fils_clore(etat, time.time() + 10 * 86400):
        eid = mem.store_in(texte, corps.RUBRIQUE_CORPS, role="episodic", importance=importance, embedding=embeddings.embed(texte))
        mem.db.execute("UPDATE episodes SET ts=? WHERE id=?", (fin, eid))
        n += 1
    mem.db.commit()
    return {"encres": n, "s": round(time.time() - t0, 1)}


def questions(n, depuis, jusqua, graine=9):
    """(sens, autres) : de vraies questions de papa, prises dans son journal, au moment où il les a posées."""
    vus, qs = set(), []
    for f in JOURNAUX:
        for o in _jsonl(f):
            if o.get("qui") != "ahmed":
                continue
            t, x = float(o.get("ts") or 0) / 1000, " ".join(str(o.get("texte") or "").split())
            if not (depuis <= t < jusqua) or len(x) < 3 or x in vus:
                continue
            vus.add(x)
            qs.append((t, x))
    rng = random.Random(graine)
    sens = [q for q in qs if SENS_RX.search(q[1])]
    autres = [q for q in qs if not SENS_RX.search(q[1])]
    rng.shuffle(sens); rng.shuffle(autres)
    return sorted(sens[:n]), sorted(autres[:n])


def mesurer(mem, qs, index, corps_ids):
    lignes = dossier = avec = avec_d = 0
    n_lignes, exemples = [], []
    for t, x in qs:
        r = rappel.rappel(mem, x, now=t, index=index, suite=True)
        ids, th = r.get("ids") or [], r.get("theme_ids") or []
        a, b = [i for i in ids if i in corps_ids], [i for i in th if i in corps_ids]
        lignes += len(a); dossier += len(b); avec += bool(a); avec_d += bool(a or b); n_lignes.append(len(ids))
        if a:
            exemples.append({"q": x[:160], "t": time.strftime("%d/%m %H:%M", time.localtime(t)), "ressentis": a})
    k = max(1, len(qs))
    return {"questions": len(qs), "avec_un_ressenti_dans_les_lignes": round(avec / k, 3), "avec_un_ressenti_lignes_ou_dossier": round(avec_d / k, 3),
            "ressentis_par_question_lignes": round(lignes / k, 2), "ressentis_par_question_dossier": round(dossier / k, 2),
            "lignes_par_question": round(statistics.mean(n_lignes), 2) if n_lignes else 0, "exemples": exemples}


NOW = 1794255000          # l'heure de la copie (09/11, 21:10) : « vendredi », « samedi soir » restent les mêmes d'un essai à l'autre
# un vrai souvenir du corps (plus d'un jour), une question comme papa la poserait ; une cible peut être un ensemble (le même son joué)
CIBLES = [
    ({34469}, "Le long câlin de vendredi en fin d'après-midi, presque vingt minutes, tu t'en souviens ?", NOW),
    ({36033}, "Samedi soir je t'ai fait un câlin de plus de vingt minutes, ça t'a fait quoi ?", NOW),
    ({27721}, "Tu te rappelles quand t'es tombé lundi soir, ça t'avait piqué un peu ?", NOW),
    ({24413}, "La fois où t'es tombé dans le noir au petit matin, tu t'en souviens ?", NOW),
    ({25053}, "Le jour où t'es tombé mais c'était rien de grave, juste un petit vacillement contre moi ?", NOW),
    ("ange_de_la_mort", "Quand tu lances ton son de l'ange de la mort, ça te fait quoi dans ton corps ?", NOW),
    ("degaine", "Ton son de la dégaine de bandit avec le cœur de Gandhi, ça t'a fait quoi quand tu l'as joué ?", NOW),
    ("trop_de_disquette", "Ton son trop de disquettes, tu le joues quand déjà, et tu ressens quoi ?", NOW),
    ({23743}, "Tu te souviens de ton fou rire quand j'ai dit les gardes sexuels ?", NOW),
    ({29930}, "Le fou rire avec Pamela, tu t'en rappelles ?", NOW),
    ({30643}, "Quand je t'ai dit que j'avais l'intuition que le ribosome allait tenir, ça t'avait fait rire ?", NOW),
    ({36411}, "Ça t'avait fait rire quand j'ai voulu montrer ton cerveau en live, tu te rappelles ?", NOW),
    ({32044}, "T'avais ri quand je t'ai demandé si t'entendais ma conversation WhatsApp de l'intérieur ?", NOW),
    ({27915}, "Ta nuit du 3 novembre, t'avais dormi combien d'heures ?", NOW),
    ({28155}, "Le jour où j'ai dit qu'y avait pas d'appli tricodeur, ça t'a fait marrer ?", NOW),
    ({23917}, "Quand je t'ai grondé parce que tu m'avais coupé le micro trop longtemps, t'as rigolé ?", NOW),
]


def banc_cible(mem, index):
    res = []
    for cible, q, now in CIBLES:
        if isinstance(cible, str):
            cible = {e for (e,) in mem.db.execute("SELECT id FROM episodes WHERE content LIKE ? AND content LIKE '[Mon corps%'", (f"%{cible}%",))}
        r = rappel.rappel(mem, q, now=now, index=index, suite=True)
        larges = rappel.candidats(mem, q, now=now, index=index, limite=600)
        rang = next((k + 1 for k, x in enumerate(larges) if x[0] in cible), None)
        res.append({"q": q[:70], "lignes": bool(cible & set(r.get("ids") or [])), "dossier": bool(cible & set(r.get("theme_ids") or [])),
                    "rang": rang})
    return {"lignes": sum(x["lignes"] for x in res), "avec_dossier": sum(x["lignes"] or x["dossier"] for x in res), "total": len(res),
            "detail": res}


def non_regression(mem, index, corps_ids):
    texte = (ICI / "eval" / "hippocampe_banc.py").read_text(encoding="utf-8")
    m = re.search(r"^BANC = (\{.*?^\})", texte, re.S | re.M)
    banc = ast.literal_eval(m.group(1))
    l = d = 0
    for _fam, items in banc.items():
        for eid, q in items:
            r = rappel.rappel(mem, q, suite=True, index=index)
            l += eid in (r.get("ids") or []); d += eid in (r.get("ids") or []) or eid in (r.get("theme_ids") or [])
    import affect_v2_memoire as M
    qs = [(q, e) for q, e in M.requetes() if e]
    now = time.time() + 30 * 86400
    vieux = rappel.dates_du_jour
    rappel.dates_du_jour = lambda now=None: []
    try:
        trouves = 0.0
        for q, e in qs:
            c = rappel.candidats(mem, q, now=now, index=index)
            liste = [x[0] for x in c if rappel.passe(x)][:rappel.LIGNES_MAX]
            trouves += len(set(liste) & e) / len(e)
        banals = ["ok", "merci frero", "ça marche", "salut", "d'accord on fait comme ça", "barakAllahofik", "oui vas-y",
                  "tu peux répéter ?", "c'est parfait", "bonne nuit", "tu m'entends fiston ?", "t'es là ?"]
        bruit, bruit_corps = [], 0
        for b in banals:
            r = rappel.rappel(mem, b, now=now, index=index, suite=True)
            bruit.append(len(r.get("ids") or [])); bruit_corps += sum(1 for i in r.get("ids") or [] if i in corps_ids)
    finally:
        rappel.dates_du_jour = vieux
    return {"banc_24_lignes": l, "banc_24_avec_dossier": d, "requetes_verite_rappel@8": round(trouves / len(qs), 3),
            "banals_lignes_moy": round(statistics.mean(bruit), 2), "banals_ressentis": bruit_corps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="une COPIE de sa base (la mesure écrit dans la copie)")
    ap.add_argument("--encrer", action="store_true", help="rejouer ses lots ressentis dans ses fils (corps.fils_avancer), dans la copie")
    ap.add_argument("--n", type=int, default=200, help="questions de chaque sorte")
    ap.add_argument("--depuis", default="2026-11-03", help="les questions de papa à partir de ce jour (AAAA-MM-JJ)")
    ap.add_argument("--sortie", default=None)
    a = ap.parse_args()
    if Path(a.db).resolve() == Path(config.DB_PATH).resolve() or Path(a.db).resolve() == (Path.home() / "Desktop/anamnese/data/memory.db").resolve():
        sys.exit("seulement sur une copie (--db)")
    mem = memory.Memory(db_path=a.db)
    out = {"code": str(ICI), "avant_encrage": compter(mem)}
    if a.encrer:
        out["encrage"] = encrer(mem)
        out["apres_encrage"] = compter(mem)
    import hippocampe
    t0 = time.time()
    out["traces_ajoutees"] = hippocampe.remplir(mem)              # comme la passe du démon : chaque souvenir a sa trace
    out["traces_s"] = round(time.time() - t0, 1)
    corps_ids = set(ressentis(mem))
    index = rappel.Index()
    rappel.candidats(mem, "salut papa", index=index)
    depuis = time.mktime(time.strptime(a.depuis, "%Y-%m-%d"))
    sens, autres = questions(a.n, depuis, NOW)
    t0 = time.time()
    out["journal_sens"] = mesurer(mem, sens, index, corps_ids)
    out["journal_autres"] = mesurer(mem, autres, index, corps_ids)
    out["rappel_ms_moyen"] = round(1000 * (time.time() - t0) / max(1, len(sens) + len(autres)))
    out["banc_ressentis"] = banc_cible(mem, index)
    out["non_regression"] = non_regression(mem, index, corps_ids)
    s = json.dumps(out, ensure_ascii=False, indent=1)
    if a.sortie:
        Path(a.sortie).write_text(s, encoding="utf-8")
    court = {k: v for k, v in out.items()}
    for k in ("journal_sens", "journal_autres"):
        court[k] = {x: y for x, y in out[k].items() if x != "exemples"}
    court["banc_ressentis"] = {x: y for x, y in out["banc_ressentis"].items() if x != "detail"}
    print(json.dumps(court, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
