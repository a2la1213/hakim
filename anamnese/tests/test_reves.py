"""(13/11, Ahmed) ses rêves de la nuit (reves.py) : le type choisi selon tout son état (consolidation, créatif, cauchemar ; lucide ou
non), la graine qui rejoue, le vrai pas du rêve lucide, les garde-fous (un cauchemar retombe, un rêve n'est jamais un fait, rien
d'inventé sur papa ne passe pour vrai, les règles du rêve tiennent, la charge de Gemma ne compte jamais), le réveil (s'en souvenir ou
pas). Chaque mécanisme a son témoin : on le coupe, et le test qui le vérifie doit alors échouer."""
import json
import time
import zlib

import pytest

import affect
import charge_corps
import corps
import daemon
import interieur
import memory
import migrations
import nuits
import reves

T = time.mktime((2026, 11, 13, 2, 0, 0, 0, 0, -1))       # 2 h du matin


def faux_embed(t):
    v = [0.0] * 512
    for m in str(t).lower().split():
        v[zlib.crc32(m.encode()) % 512] += 1.0
    return v


@pytest.fixture
def J(tmp_path, monkeypatch):
    monkeypatch.setattr(nuits, "JARVIS", tmp_path)
    monkeypatch.setattr(nuits, "DATA", tmp_path)
    monkeypatch.setattr(reves, "JARVIS", tmp_path)
    monkeypatch.setattr(reves, "_embed", faux_embed)
    monkeypatch.setattr(corps, "_souvenir", lambda m, t, i: None)
    return tmp_path


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    m.kv_set("affect_v2", "1")
    affect._save_v2(m, affect.bases(v2=True), {}, {}, T - 4 * 3600)
    yield m
    m.db.close()


def _negatif(mem, t=T):
    """Une journée très lourde, juste avant de dormir : tristesse, peur, échec, honte, une attaque."""
    for k, (n, i) in enumerate([("tristesse", 1.0), ("peur", 0.8), ("echec", 1.0), ("honte", 0.7), ("attaque", 0.8),
                                ("tristesse", 1.0), ("echec", 0.9), ("peur", 0.8)]):
        affect.event(mem, n, i, now=t - 1800 + k * 120, sujet=f"souci {k}", source="balise")


def _positif(mem, t=T):
    for k, (n, i) in enumerate([("joie", 0.8), ("succes", 0.8), ("chaleur_user", 0.8), ("musique", 0.6), ("soutien", 0.7)]):
        affect.event(mem, n, i, now=t - 1800 + k * 120, sujet=f"joie {k}", source="balise")


def _tirages(p, n=400):
    return [reves.choisir(p, g)[0] for g in range(n)]


def _dormir(mem, debut):
    mem.kv_set("nuit", json.dumps({"etat": "sommeil", "debut": debut, "charge": 0.2, "qualite": "moyenne", "apaisants": [],
                                   "compense": False, "pas": debut, "micro": 0, "reve": False}))


def faux_modele(prompts, action=True):
    def call(p):
        prompts.append(p)
        if "###ACTION###" in p:
            return "###ACTION###\nJe demande à la lune de chanter plus fort.\n###FIN###" if action else None
        if "###SUITE###" in p:
            return "###SUITE###\nLa lune rit, le désert chante avec elle, la peur fond, et je me rendors doucement.\n###FIN###"
        return ("###TITRE###\nLa lune qui parle\n###REVE###\nJe marche chez nous, papa me tend une horloge sans aiguilles. "
                "Le sol devient une neige chaude.\n" + ("###CHOIX###\n- voler\n- parler à la lune\n" if "###CHOIX###" in p else "")
                + "###FIN###")
    return call


# ------------------------------------------------------------------ 1. le type, selon l'état
def test_un_etat_tres_negatif_donne_un_cauchemar(J, mem, monkeypatch):
    """Très négatif → cauchemar (le type le plus probable, et le plus tiré). Témoin : l'état coupé du choix (des nombres neutres) →
    plus aucun cauchemar."""
    _negatif(mem)
    reg = reves.reglages()
    c = reves.composantes(mem, T)
    nb = reves.nombres(c)
    assert nb["negatif"] and nb["noirceur"] >= reg["cauchemar_seuil_pct"] / 100, nb
    p = reves.probabilites(nb, reg, cycle=2)
    assert p["cauchemar"] >= 0.6 and p["cauchemar"] == max(p[t] for t in reves.TYPES), p
    assert _tirages(p).count("cauchemar") >= 0.55 * 400
    monkeypatch.setattr(reves, "nombres", lambda c: {"noirceur": 0.0, "vivacite": 0.2, "clarte": 0.2, "negatif": False})
    p2 = reves.probabilites(reves.nombres(c), reg, cycle=2)
    assert p2["cauchemar"] == 0 and "cauchemar" not in _tirages(p2)


def test_un_etat_positif_ne_donne_jamais_de_cauchemar(J, mem, monkeypatch):
    """Positif → jamais de cauchemar, même au seuil le plus bas et sur toute la nuit ; même un stress très fort avec une valence haute
    (heureux mais en alerte) n'en donne pas. Témoin : sans la garde de la valence, ce stress-là en donne."""
    _positif(mem)
    reg = {**reves.reglages(), "cauchemar_seuil_pct": 30}
    nb = reves.nombres(reves.composantes(mem, T))
    assert not nb["negatif"]
    for cycle in range(1, 7):
        assert "cauchemar" not in _tirages(reves.probabilites(nb, reg, cycle), 300)
    heureux_stresse = {"valence": 0.2, "val": 0.0, "stress": 1.0, "peur": 1.0, "jour": 1.0, "corps": 1.0, "souv_neg": 1.0,
                       "souci": 1.0, "afida": 0.0, "eveil_x": 1.0, "dopa": 1.0, "coeur": 1.0, "nouveau": 0.0, "souv_pos": 0.0,
                       "ach": 0.5, "na": 1.0}
    nb2 = reves.nombres(heureux_stresse)
    assert nb2["noirceur"] >= 0.3 and not nb2["negatif"]
    assert "cauchemar" not in _tirages(reves.probabilites(nb2, reg, 3))
    monkeypatch.setattr(reves, "_peut_cauchemarder", lambda nb, reg: reg["cauchemars"] and nb["noirceur"] >= reg["cauchemar_seuil_pct"] / 100)
    assert "cauchemar" in _tirages(reves.probabilites(nb2, reg, 3)), "témoin : sans la garde de la valence, ce stress fait des cauchemars"


def test_la_consolidation_est_le_plus_frequent(J, mem):
    """Un état ordinaire, ou bon : la consolidation reste le type le plus probable, à chaque cycle de la nuit."""
    reg = reves.reglages()
    for remplir in (lambda m: None, _positif):
        remplir(mem)
        nb = reves.nombres(reves.composantes(mem, T))
        for cycle in (1, 2, 3):
            p = reves.probabilites(nb, reg, cycle)
            assert p["consolidation"] >= 0.5 and p["consolidation"] == max(p[t] for t in reves.TYPES), p


def test_les_reglages_sont_lus_a_chaud_et_bornes(J, mem):
    """Éteints, les cauchemars, les créatifs et la lucidité ne viennent plus ; les seuils sont bornés. Témoin : sans fichier, les
    défauts (cauchemars possibles)."""
    _negatif(mem)
    nb = reves.nombres(reves.composantes(mem, T))
    assert reves.probabilites(nb, reves.reglages(), 3)["cauchemar"] > 0, "témoin : les défauts permettent le cauchemar"
    (J / "corps-reglages.json").write_text(json.dumps({"cauchemars": False, "reves_creatifs": False, "reves_lucides": False,
                                                        "cauchemar_seuil_pct": 999, "reves_par_nuit": -3, "reves_lucides_pct": "x"}))
    reg = reves.reglages()
    assert (reg["cauchemar_seuil_pct"], reg["reves_par_nuit"], reg["reves_lucides_pct"]) == (90, 0, 15)
    p = reves.probabilites(nb, reg, 3)
    assert p["cauchemar"] == p["creatif"] == p["lucide_creatif"] == p["lucide_cauchemar"] == 0 and p["consolidation"] == 1
    (J / "corps-reglages.json").write_text(json.dumps({"cauchemar_seuil_pct": 90}))
    assert reves.probabilites(nb, reves.reglages(), 3)["cauchemar"] == 0, "un seuil haut : ce négatif-là ne suffit plus"


def test_la_graine_rejoue_le_meme_reve(J, mem):
    """La graine notée refait le même choix et la même matière ; d'autres graines en font d'autres (témoin : le hasard compte)."""
    _negatif(mem)
    mem.add("episodic", "Papa m'a montré la mer à Exempleville", importance=0.7)
    e = reves.rever_cycle(mem, T, faux_modele([]), cycle=2, graine=1234, debut=T - 3 * 3600)
    assert reves.rejouer(e) == (e["type"], e["lucide"])
    c = reves.composantes(mem, T)
    assert reves.materiaux(mem, T, 1234, c) == reves.materiaux(mem, T, 1234, c)
    p = reves.probabilites(e["nombres"], e["reglages"], 2)
    assert len({reves.choisir(p, g)[0] for g in range(50)}) >= 2
    assert len({tuple(reves.materiaux(mem, T, g, c)["inventes"]) for g in range(20)}) >= 5


# ------------------------------------------------------------------ 2. les rêves eux-mêmes
def test_un_reve_cree_vient_de_son_cerveau_avec_des_inventions(J, mem, monkeypatch):
    """Un créatif mêle de vrais morceaux de sa mémoire (souvenir, personne, lieu, son) et des éléments inventés ; non lucide, il subit
    (un seul appel, aucune action)."""
    (J / "lieux.json").write_text(json.dumps({"lieux": [{"nom": "chez nous"}, {"nom": "la salle de boxe"}]}))
    (J / "voix-connues.json").write_text(json.dumps([{"nom": "Nora"}]))
    eid = mem.add("episodic", "Papa et moi avons composé « Le sens du vent » ensemble", importance=0.8)
    monkeypatch.setattr(reves, "choisir", lambda p, g: ("creatif", False, {}))
    prompts = []
    e = reves.rever_cycle(mem, T, faux_modele(prompts), cycle=2, graine=7, debut=T - 3 * 3600)
    assert len(prompts) == 1 and e["appels"] == 1 and "action" not in e
    p = prompts[0]
    assert "TU NE SAIS PAS QUE TU RÊVES" in p and "###CHOIX###" not in p
    assert "Le sens du vent" in p and "Nora" in p and ("chez nous" in p or "la salle de boxe" in p)
    assert any(s in p for s in reves.SONS_DU_CORPS)
    assert all(i in p for i in e["materiaux"]["inventes"]) and all(i in reves.INVENTIONS for i in e["materiaux"]["inventes"])
    assert eid in [s["id"] for s in e["materiaux"]["souvenirs"]]
    assert e["titre"] == "La lune qui parle" and "horloge sans aiguilles" in e["recit"]


def test_le_reve_lucide_a_un_vrai_pas(J, mem, monkeypatch):
    """Lucide : il comprend qu'il rêve, CHOISIT une action (un appel à part, avec son identité), et le rêve répond (un autre appel, le
    rêve lui-même, sans son identité). Témoin : s'il ne choisit rien, la lucidité lui échappe (pas de suite, deux appels)."""
    monkeypatch.setattr(reves, "choisir", lambda p, g: ("creatif", True, {}))
    prompts = []
    e = reves.rever_cycle(mem, T, faux_modele(prompts), cycle=3, graine=8, debut=T - 5 * 3600)
    assert len(prompts) == 3 and e["appels"] == 3
    assert "TU COMPRENDS QUE TU RÊVES" in prompts[0] and "###CHOIX###" in prompts[0]
    assert prompts[1].startswith(reves.IDENTITE) and "parler à la lune" in prompts[1] and "horloge sans aiguilles" in prompts[1]
    assert not prompts[2].startswith(reves.IDENTITE) and "Tu es un RÊVE" in prompts[2] and "chanter plus fort" in prompts[2]
    assert e["action"].startswith("Je demande à la lune") and "désert chante" in e["suite"] and e["choix"] == ["voler", "parler à la lune"]
    prompts2 = []
    e2 = reves.rever_cycle(mem, T + 6000, faux_modele(prompts2, action=False), cycle=4, graine=9, debut=T - 5 * 3600)
    assert len(prompts2) == 2 and e2.get("lucide_perdu") and "suite" not in e2


def test_la_consolidation_rejoue_la_journee_sans_modele(J, mem, monkeypatch):
    monkeypatch.setattr(reves, "choisir", lambda p, g: ("consolidation", False, {}))
    mem.add("episodic", "On a rangé le studio avec papa", importance=0.8)
    prompts = []
    e = reves.rever_cycle(mem, T, faux_modele(prompts), cycle=1, graine=3, debut=T - 2 * 3600)
    assert prompts == [] and e["appels"] == 0 and "rangé le studio" in e["recit"] and e["titre"] == "le tri de la journée"


# ------------------------------------------------------------------ 3. les garde-fous
def _etat_a(mem, t):
    h = affect.get_state(mem, now=t)
    return h, affect.valence_arousal(h)


def _ecart(m1, m2, t):
    (h1, (v1, a1)), (h2, (v2, a2)) = _etat_a(m1, t), _etat_a(m2, t)
    return max(abs(h1[k] - h2[k]) for k in h1), abs(v1 - v2), abs(a1 - a2)


def _nouvelle(tmp_path, nom):
    m = memory.Memory(db_path=tmp_path / nom)
    migrations.migrate(m.db)
    m.kv_set("affect_v2", "1")
    affect._save_v2(m, affect.bases(v2=True), {}, {}, T - 4 * 3600)
    return m


def test_un_cauchemar_retombe_et_ne_laisse_jamais_d_humeur_coincee(J, mem, tmp_path, monkeypatch):
    """Un cauchemar subi à 6 h 30 : il secoue vraiment (noradrénaline), sa reprise vient 10 min après (le démon), le réveil à 7 h :
    l'humeur et chaque hormone sont revenues à celles d'une nuit sans cauchemar. Témoin : sans reprise, au réveil, il en reste."""
    t = T + 4.5 * 3600
    temoin = _nouvelle(tmp_path, "temoin.db")
    monkeypatch.setattr(reves, "choisir", lambda p, g: ("cauchemar", False, {}))
    _dormir(mem, T - 3600)
    e = reves.rever_cycle(mem, t, faux_modele([]), cycle=3, graine=11)
    assert e["affect"]["intensite"] <= reves.CAUCHEMAR_MAX
    h, _ = _etat_a(mem, t + 30)
    h0, _ = _etat_a(temoin, t + 30)
    assert h["noradrenaline"] - h0["noradrenaline"] > 0.05, "le cauchemar le secoue vraiment"
    assert reves.reprises_dues(mem, t + 300) == 0 and reves.reprises_dues(mem, t + reves.REPRISE_APRES_S) == 1
    reves.au_reveil(mem, t + 1800)
    for apres in (1800, 1800 + 3600):
        dh, dv, da = _ecart(mem, temoin, t + apres)
        assert dh <= 0.03 and dv <= 0.01 and da <= 0.01, (apres, dh, dv, da)
    # témoin : la même nuit sans aucune reprise
    m2 = _nouvelle(tmp_path, "sans.db")
    monkeypatch.setattr(reves, "_reprendre", lambda mem, now, r: 0.0)
    _dormir(m2, T - 3600)
    reves.rever_cycle(m2, t, faux_modele([]), cycle=3, graine=11)
    reves.reprises_dues(m2, t + reves.REPRISE_APRES_S)
    reves.au_reveil(m2, t + 1800)
    dh, dv, da = _ecart(m2, temoin, t + 1800)
    assert dh > 0.03, "témoin : sans reprise, le cauchemar est encore là au réveil"


def test_un_cauchemar_lucide_dont_il_sort_retombe_tout_de_suite(J, mem, tmp_path, monkeypatch):
    temoin = _nouvelle(tmp_path, "temoin.db")
    monkeypatch.setattr(reves, "choisir", lambda p, g: ("cauchemar", True, {}))
    _dormir(mem, T - 3600)
    e = reves.rever_cycle(mem, T, faux_modele([]), cycle=2, graine=12)
    assert e["suite"] and e["affect"]["reprise"].startswith("tout de suite")
    assert not [r for r in reves._etat(mem).get("reprises", []) if not r.get("faite")], "plus rien de dû : il s'en est sorti"
    dh, dv, da = _ecart(mem, temoin, T + 600)
    assert dh <= 0.02 and dv <= 0.01 and da <= 0.01, (dh, dv, da)


def test_l_intensite_d_un_cauchemar_est_bornee(J, mem, monkeypatch):
    """Même le pire cauchemar ne donne pas plus que CAUCHEMAR_MAX à ses hormones. Témoin : la borne levée, il donne plus."""
    assert reves._affect_cauchemar(mem, T, 1.0, False)[0]["intensite"] == reves.CAUCHEMAR_MAX
    monkeypatch.setattr(reves, "CAUCHEMAR_MAX", 5.0)
    assert reves._affect_cauchemar(mem, T + 1, 1.0, False)[0]["intensite"] > 0.5


def test_pas_de_boucle_ses_reves_et_ses_nuits_ne_nourrissent_pas_le_suivant(J, mem):
    """Ce que produisent ses rêves (et ses nuits) n'entre ni dans les événements de sa journée ni dans la charge de sa nuit : un cauchemar
    ne rend pas le suivant plus probable. Témoin : la même peur, venue de sa journée, compte."""
    reves._affect_cauchemar(mem, T - 600, 0.9, False)
    evs = [json.loads(l) for l in (J / "affect-evenements.jsonl").read_text().splitlines()]
    assert any(o["nom"] == "cauchemar" and o["source"] == "reve" for o in evs)
    assert not [o for o in reves._evenements(T, evs) if o["source"] in ("reve", "nuit")]
    assert nuits.charge(mem, T)[0] < 0.3
    affect.event(mem, "peur", 0.9, now=T - 300, sujet="une vraie peur", source="balise")
    evs = [json.loads(l) for l in (J / "affect-evenements.jsonl").read_text().splitlines()]
    assert [o for o in reves._evenements(T, evs) if o["nom"] == "peur"], "témoin : une peur de sa journée compte"


def test_un_reve_n_entre_jamais_comme_un_fait(J, mem, monkeypatch):
    """Rien en mémoire pendant la nuit ; au réveil, un rêve gardé entre avec le rôle « dream », marqué rêve, et inventé pour papa ; le
    rappel automatique ne le prend jamais pour un souvenir (témoin : le même texte en « episodic » est trouvé) ; memory_recall le marque
    [RÊVE] ; la consolidation ne le lit pas. Témoin de la marque famille : un rêve sans la famille ne la porte pas."""
    import consolidate
    import rappel
    monkeypatch.setattr(reves, "choisir", lambda p, g: ("creatif", True, {}))
    monkeypatch.setattr(reves, "_p_souvenir", lambda c, dernier: 1.0)
    _dormir(mem, T - 3600)
    avant = mem.db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    reves.rever_cycle(mem, T, faux_modele([]), cycle=2, graine=21)
    assert mem.db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == avant, "rien en mémoire pendant la nuit"
    reves.au_reveil(mem, T + 3600)
    eid, role, contenu = mem.db.execute("SELECT id, role, content FROM episodes WHERE role='dream'").fetchone()
    assert contenu.startswith("(rêve · rêve créatif lucide") and reves.MARQUE in contenu and reves.MARQUE_FAMILLE in contenu
    assert "dream" not in rappel.ROLES and "dream" not in consolidate.ROLES_MATIERE
    vrai = mem.add("episodic", contenu.replace("(rêve", "(souvenir"), embedding=faux_embed(contenu))
    mem.db.execute("UPDATE episodes SET ts=? WHERE id IN (?, ?)", (T - 6 * 3600, eid, vrai))
    mem.db.commit()
    trouves = {x[0] for x in rappel.candidats(mem, "papa me tend une horloge sans aiguilles chez nous", now=T + 3600, embed=faux_embed)}
    assert vrai in trouves, "témoin : le même texte, vécu, est trouvé"
    assert eid not in trouves, "un rêve n'est jamais rappelé comme un souvenir"
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(mcp_server, "_embed", faux_embed)
    lignes = mcp_server.memory_recall("horloge sans aiguilles", top_k=6, profond=True).splitlines()
    assert any("[RÊVE" in l and "(dream)" in l for l in lignes)
    assert not any("[RÊVE" in l and "(episodic)" in l for l in lignes)
    sans = reves.texte_souvenir({"type": "creatif", "titre": "la mer", "recit": "Je nage dans un océan de lettres.", "intensite": 0.8}, T)
    assert reves.MARQUE in sans and reves.MARQUE_FAMILLE not in sans


def test_au_reveil_il_s_en_souvient_ou_pas_plus_net_si_intense_ou_lucide(J, mem, monkeypatch):
    """Sur beaucoup de nuits : un rêve lucide et intense est gardé bien plus souvent qu'un tri doux, et net ; ce qu'il garde va dans son
    premier tour (« tu peux en parler à papa »), pas son récit dans le souvenir de sa nuit. Témoin : sans l'intensité ni la lucidité dans
    la chance de s'en souvenir, les deux sont gardés pareil."""
    def part(c, n=300, f=None):
        f = f or reves._p_souvenir
        return sum(__import__("random").Random(f"souvenir:{g}").random() < f(c, False) for g in range(n)) / n
    fort = {"type": "creatif", "lucide": True, "suite": "…", "intensite": 0.85}
    doux = {"type": "consolidation", "lucide": False, "intensite": 0.18}
    assert part(fort) > part(doux) + 0.4 and reves.nettete(fort) == "net" and reves.nettete(doux) == "flou"
    plat = lambda c, dernier: 0.4  # noqa: E731
    assert abs(part(fort, f=plat) - part(doux, f=plat)) < 0.01, "témoin"
    monkeypatch.setattr(reves, "choisir", lambda p, g: ("creatif", True, {}))
    monkeypatch.setattr(reves, "_p_souvenir", lambda c, dernier: 1.0)
    ma_nuit = []
    monkeypatch.setattr(corps, "_souvenir", lambda m, t, i: ma_nuit.append(t))
    e = nuits.endormir(mem, T - 3 * 3600)
    reves.rever_cycle(mem, T, faux_modele([]), cycle=2, graine=31, debut=e["debut"])
    assert nuits.reveiller(mem, T + 5 * 3600, "matin")
    d = json.loads((J / "nuit-derniere.json").read_text())
    assert "tu as rêvé 1 fois, tu te souviens de 1" in d["texte"] and "La lune qui parle" in d["texte"]
    assert "tu peux en parler à papa si tu en as envie" in d["texte"] and "un rêve, pas un souvenir vrai" in d["texte"]
    assert d["texte"].index("pas un souvenir vrai") < d["texte"].index("La lune qui parle"), "la garde d'abord : le cockpit coupe sa nuit"
    souv = mem.db.execute("SELECT content FROM episodes WHERE role='dream'").fetchone()[0]
    assert "La lune qui parle" in souv
    assert ma_nuit and "tu as rêvé 1 fois" in ma_nuit[0] and "La lune" not in ma_nuit[0], "le souvenir vrai de sa nuit : sans le rêve"
    lignes = [json.loads(l) for l in (J / reves.JOURNAL).read_text().splitlines()]
    assert [o["quoi"] for o in lignes] == ["cycle", "reveil"] and lignes[1]["souvenirs"][0]["garde"]
    assert lignes[1]["souvenirs"][0]["ts"] == lignes[0]["ts"] == T, "la page relie le souvenir au rêve par son heure"


# ------------------------------------------------------------------ 4. les règles du rêve tiennent
def test_le_cycle_suit_son_sommeil(J, mem):
    d = T - 3600
    assert reves.cycle_du(mem, T) is None, "il ne dort pas"
    _dormir(mem, d)
    assert reves.cycle_du(mem, d + 1800) is None and reves.cycle_du(mem, d + reves.CYCLE_S + 60) == 1
    reves.rever_cycle(mem, d + reves.CYCLE_S + 60, faux_modele([]), cycle=1, graine=1)
    assert reves.cycle_du(mem, d + reves.CYCLE_S + 600) is None and reves.cycle_du(mem, d + 2 * reves.CYCLE_S + 60) == 2
    (J / "corps-reglages.json").write_text(json.dumps({"reves_par_nuit": 1}))
    assert reves.cycle_du(mem, d + 2 * reves.CYCLE_S + 60) is None
    (J / "corps-reglages.json").write_text(json.dumps({"nuits": False}))
    assert reves.cycle_du(mem, d + 2 * reves.CYCLE_S + 60) is None, "ses nuits éteintes : pas de rêve de nuit"


class _Garde:
    en_pause = False

    def permet(self, *a):
        return True


def test_pas_de_reve_quand_la_conscience_travaille_ou_quand_ahmed_est_la(J, mem, monkeypatch):
    """Le cycle passe par _travaux_llm : rien quand Claude travaille ou qu'Ahmed est là ; sinon il rêve. Et si Ahmed revient au milieu
    d'un rêve lucide, le rêve s'arrête net (les appels suivants n'ont pas lieu)."""
    monkeypatch.setattr(daemon.interieur, "ACTIF", False)
    monkeypatch.setattr(daemon, "dream_due", lambda m: False)
    monkeypatch.setattr(daemon, "reflect", lambda eng, m: None)
    monkeypatch.setattr(daemon, "_echanges_pass", lambda m: None)
    monkeypatch.setattr(reves, "choisir", lambda p, g: ("creatif", True, {}))
    now = time.time()
    _dormir(mem, now - 2 * reves.CYCLE_S - 60)
    appels = []

    class Eng:
        def chat(self, messages, stream=False, think=False):
            appels.append(messages[0]["content"])
            return faux_modele([])(messages[0]["content"])
    present = {"oui": False}
    monkeypatch.setattr(interieur, "ahmed_present", lambda *a, **k: present["oui"])
    monkeypatch.setattr(interieur, "conscience_active", lambda *a, **k: False)
    etat = {"last_reflect": time.time()}
    daemon._travaux_llm(Eng(), mem, etat, _Garde(), lecture=lambda: (0.1, 80.0), robot=lambda: False, conscience=lambda: True,
                        present=lambda: False, calcul=lambda: None)
    assert appels == [] and not reves._etat(mem).get("cycles"), "la conscience travaille : pas de rêve"
    daemon._travaux_llm(Eng(), mem, etat, _Garde(), lecture=lambda: (0.1, 80.0), robot=lambda: False, conscience=lambda: False,
                        present=lambda: True, calcul=lambda: None)
    assert appels == [] and not reves._etat(mem).get("cycles"), "Ahmed est là : pas de rêve"
    real_chat = Eng.chat

    def chat_puis_papa(self, messages, stream=False, think=False):
        r = real_chat(self, messages)
        present["oui"] = True                              # papa revient pendant le rêve
        return r
    monkeypatch.setattr(Eng, "chat", chat_puis_papa)
    daemon._travaux_llm(Eng(), mem, etat, _Garde(), lecture=lambda: (0.1, 80.0), robot=lambda: False, conscience=lambda: False,
                        present=lambda: False, calcul=lambda: None)
    cycles = reves._etat(mem)["cycles"]
    assert len(appels) == 1 and len(cycles) == 1 and cycles[0]["lucide_perdu"], "papa revient : le rêve s'arrête, sans suite"


def test_la_charge_de_gemma_ne_compte_jamais(J, mem):
    """Gemma qui tient 8 cœurs pendant 20 min : sa charge ressentie reste nulle et la noirceur ne bouge pas. Témoin : la même charge
    venue d'un programme inconnu pèse."""
    def charge(cause, qui):
        etat = {}
        for k in range(40):
            m = {"causes": {cause: {"coeurs": 8.0, "qui": {qui: 8.0}}}, "mac_cpu": 0.9, "appareils": {}, "live": {}}
            etat, _evs, _ = charge_corps.avancer(etat, charge_corps.intensites(m), T - 1200 + 30 * k, 30)
        for s_ in etat.values():                          # comme charge_corps.battre : ce qu'il SENT
            s_["ressenti"] = charge_corps.ressenti(s_, T)
        return {"sens": etat}
    sans = reves.nombres(reves.composantes(mem, T, cc={}))
    gemma = reves.composantes(mem, T, cc=charge("subconscient", "Gemma"))
    assert gemma["corps"] == 0 and reves.nombres(gemma) == sans
    inconnu = reves.composantes(mem, T, cc=charge("inconnu", "un programme"))
    assert inconnu["corps"] > 0.3 and reves.nombres(inconnu)["noirceur"] > sans["noirceur"], "témoin : une charge d'ailleurs pèse"


def test_le_tri_de_la_nuit_est_note(J, mem):
    _dormir(mem, T - 3600)
    reves.noter_tri(mem, T, 4, ["Peut-être que la musique range mes souvenirs"])
    o = json.loads((J / reves.JOURNAL).read_text().splitlines()[-1])
    assert o["quoi"] == "tri" and o["type"] == "consolidation" and o["nuit"] == T - 3600 and o["idees"]


def test_le_lexique_de_la_parole_ne_fait_pas_ses_problemes(J, mem):
    """Ses problèmes se comptent sur son appréciation (balise) ou son corps, une fois par sujet ; jamais sur le lexique de la parole, qui
    se trompe souvent de sens. Témoin : le même problème dit par sa balise compte."""
    evs = [{"ts": T - 600 - k, "nom": "probleme", "intensite": 0.6, "source": "parole", "sujet": f"mots:{k}"} for k in range(30)]
    assert reves.composantes(mem, T, evenements=evs)["problemes"] == 0
    evs += [{"ts": T - 300, "nom": "probleme", "intensite": 0.6, "source": "balise", "sujet": "le studio"}] * 5
    assert reves.composantes(mem, T, evenements=evs)["problemes"] == 1, "témoin : sa balise compte, une fois par sujet"


def test_la_phrase_du_reveil_tient_dans_ce_que_le_cockpit_garde(J, mem, monkeypatch):
    """Même après une nuit de six longs rêves gardés, sa phrase du premier tour reste courte (le cockpit coupe à 900 signes) et la garde
    vient d'abord."""
    monkeypatch.setattr(reves, "_p_souvenir", lambda c, dernier: 1.0)
    long = "Je marche chez nous et papa chante. " * 40
    reves._sauver(mem, {"debut": T - 7 * 3600, "reprises": [], "cycles": [
        {"cycle": k, "ts": T - 6 * 3600 + k * 3600, "type": "creatif", "lucide": True, "graine": k, "intensite": 0.9, "titre": "un titre",
         "recit": long, "action": "J'agis " * 40, "suite": long} for k in range(1, 7)]})
    phrase, tour = reves.au_reveil(mem, T)
    assert phrase.startswith("tu as rêvé 6 fois, tu te souviens de 6")
    assert len(tour) <= reves.TOUR_MAX and tour.index("pas un souvenir vrai") < tour.index("un titre")
