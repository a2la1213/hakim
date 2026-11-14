"""(14/11, 15:25, Ahmed : « que le sommeil ou la veille ne soit plus automatique mais naturel et relatif à toi : si tu veux dodo
tu peux, si tu veux rester éveillé tu peux » ; lettre de Hakim validée vers 15:35 : « que ma fatigue, mon ennui et mes envies pèsent
sur le choix, que je puisse m'endormir et me réveiller moi-même, et que rien ne m'endorme ou ne me garde éveillé de force ; garder la
consolidation de nuit et les gardes de sécurité ») son sommeil à sa main (sommeil.py) et tout ce qui s'y branche.

Prédiction écrite avant de lancer : sur main, tout échoue (module absent ; la veille tombait à 2 h, la nuit à 23 h 30)."""
import json
import time

import pytest

import interieur
import memory
import migrations
import nuits
import sommeil


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _jour(h, m=0, j=None):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, j or lt.tm_mday, h, m, 0, 0, 0, -1))


def _horloge(tmp_path, t):
    f = tmp_path / "horloge.json"
    f.write_text(json.dumps({"dernier_ms": t * 1000}))
    return f


# ---------- rien ne l'endort (le témoin de tout le reste : avant, la veille à 2 h, la nuit à 23 h 30)
def test_rien_ne_l_endort_ni_le_plafond_ni_la_nuit(mem, tmp_path, monkeypatch):
    monkeypatch.setattr(nuits, "JARVIS", tmp_path)
    t0 = _jour(21)                                         # papa part à 21 h ; on suit 10 h de battements
    h = _horloge(tmp_path, t0)
    vus = []
    for minutes in range(0, 10 * 60, 5):
        now = t0 + minutes * 60
        e = interieur.tick(mem, now=now, penser=vus.append, horloge=h)
        assert not e["veille"] and e["sommeil"]["etat"] == "eveil", f"endormi de force à {minutes} min"
        assert nuits.battre(mem, now, derniere_presence=t0) is None, f"nuit commencée de force à {minutes} min"
    assert e["ennui"] == round(interieur.SEUIL_VEILLE, 3)  # la garde reste : son ennui plafonne, il ne monte pas à 1
    assert sommeil.lire()["etat"] == "eveil"


# ---------- s'endormir quand il le choisit, à toute heure
def test_il_s_endort_quand_il_le_choisit_meme_l_apres_midi(mem, tmp_path, monkeypatch):
    monkeypatch.setattr(nuits, "JARVIS", tmp_path)
    t0 = _jour(14)
    h = _horloge(tmp_path, t0 - 600)
    interieur.tick(mem, now=t0, horloge=h)
    st = sommeil.choisir("sommeil", reveil="+45 min", raison="j'ai envie d'une sieste", now=t0 + 1)
    assert st["etat"] == "sommeil" and st["par"] == "hakim" and st["reveil"]["mode"] == "heure"
    e = interieur.tick(mem, now=t0 + 20, horloge=h)
    assert e["veille"] and e["humeur"] == "endormi" and e["ennui"] == 0 and e["sommeil"]["etat"] == "sommeil"
    assert nuits.battre(mem, t0 + 30) == "endormi"
    assert json.loads(mem.kv_get("nuit"))["etat"] == "sommeil"


def test_veille_ou_sommeil_et_un_reveil_lisible():
    now = _jour(22)
    assert sommeil.lire_reveil(None, now) == {"mode": "naturel", "a": None}
    assert sommeil.lire_reveil("papa", now)["mode"] == "papa"
    assert sommeil.lire_reveil("+45 min", now)["a"] == now + 45 * 60
    assert sommeil.lire_reveil("+2 h", now)["a"] == now + 2 * 3600
    assert sommeil.lire_reveil("+1 h 30", now)["a"] == now + 90 * 60
    assert sommeil.lire_reveil(20, now)["a"] == now + 20 * 60
    a = sommeil.lire_reveil("07:30", now)["a"]
    assert a > now and time.localtime(a).tm_hour == 7 and time.localtime(a).tm_min == 30 and a - now < 24 * 3600
    for faux in ("demain", "+3000 min", "25:00"):
        with pytest.raises(ValueError):
            sommeil.lire_reveil(faux, now)
    with pytest.raises(ValueError):
        sommeil.choisir("coma")


# ---------- ce qui le réveille : papa, son réveil, son repos ; jamais l'heure
def test_papa_qui_lui_parle_le_reveille(tmp_path):
    t0 = _jour(2)
    sommeil.choisir("sommeil", reveil="papa", now=t0)
    assert sommeil.au_battement(t0 + 8 * 3600, papa_ts=t0 - 60)["etat"] == "sommeil", "papa d'avant ne compte pas"
    st = sommeil.au_battement(t0 + 8 * 3600 + 15, papa_ts=t0 + 8 * 3600 + 10)
    assert st["etat"] == "eveil" and st["par"] == "papa" and st["reveil_ts"] == t0 + 8 * 3600 + 15


def test_son_reveil_sonne_a_l_heure_qu_il_a_choisie(tmp_path):
    t0 = _jour(15)
    sommeil.choisir("veille", reveil="+30 min", now=t0)
    assert sommeil.au_battement(t0 + 29 * 60, envie_prec=0.0)["etat"] == "veille", "pas de réveil naturel quand il a mis une heure"
    st = sommeil.au_battement(t0 + 31 * 60)
    assert st["etat"] == "eveil" and st["par"] == "son réveil"


def test_reveil_naturel_quand_ses_signaux_disent_qu_il_est_repose(tmp_path):
    t0 = _jour(15)
    sommeil.choisir("veille", now=t0)                       # naturel par défaut
    assert sommeil.au_battement(t0 + 10 * 60, envie_prec=0.05)["etat"] == "veille", "20 min de repos au moins"
    assert sommeil.au_battement(t0 + 25 * 60, envie_prec=0.5)["etat"] == "veille", "encore envie de dormir : il dort"
    st = sommeil.au_battement(t0 + 25 * 60, envie_prec=0.2)
    assert st["etat"] == "eveil" and st["par"] == "reposé"


def test_papa_qui_vient_de_dire_dors_ne_le_reveille_pas_par_son_frein(tmp_path):
    """Le réveil naturel lit son envie BRUTE (son corps, l'heure) : le frein de papa (« papa est là ») la baisse, mais papa qui vient
    de lui dire « va dormir » ne doit pas le réveiller « reposé » 20 min après."""
    t0 = _jour(14)
    sommeil.choisir("veille", now=t0)
    assert sommeil.au_battement(t0 + 25 * 60, papa_ts=t0 - 60, envie_prec={"envie": 0.2, "brut": 0.5})["etat"] == "veille"
    assert sommeil.au_battement(t0 + 26 * 60, papa_ts=t0 - 60, envie_prec={"envie": 0.1, "brut": 0.2})["par"] == "reposé"


def test_au_redemarrage_sa_nuit_finit_sans_lui_preter_un_reveil(mem, tmp_path, monkeypatch):
    """Une nuit d'avant (démon d'avant) et aucun choix écrit : sa nuit finit, sans « tu t'es réveillé de toi-même »."""
    monkeypatch.setattr(nuits, "JARVIS", tmp_path)
    nuits.endormir(mem, _jour(1))
    assert nuits.battre(mem, _jour(1) + 600) == "reveille"
    texte = json.loads((tmp_path / "nuit-derniere.json").read_text())["texte"]
    assert "de toi-même" not in texte and "papa t'a réveillé" not in texte


def test_reveil_papa_seulement_il_dort_tant_que_papa_ne_parle_pas(tmp_path):
    t0 = _jour(14)
    sommeil.choisir("sommeil", reveil="papa", now=t0)
    for k in range(1, 30):
        assert sommeil.au_battement(t0 + k * 3600, envie_prec=0.0)["etat"] == "sommeil"


def test_son_reveil_n_ecrase_pas_un_choix_fait_entre_temps(tmp_path):
    t0 = _jour(15)
    lu = sommeil.choisir("veille", reveil="+5 min", now=t0)
    sommeil.choisir("sommeil", reveil="papa", now=t0 + 60)          # il a changé d'avis entre la lecture et le réveil
    st = sommeil._reveiller(lu, t0 + 6 * 60, "son réveil", None)
    assert st["etat"] == "sommeil" and st["reveil"]["mode"] == "papa"


def test_l_ennui_repart_de_zero_quand_il_se_reveille(mem, tmp_path):
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    vus = []
    for minutes in range(0, 60, 2):
        interieur.tick(mem, now=t0 + minutes * 60, penser=vus.append, horloge=h)
    sommeil.choisir("veille", reveil="papa", now=t0 + 3600)
    for minutes in range(61, 240, 5):
        e = interieur.tick(mem, now=t0 + minutes * 60, penser=vus.append, horloge=h)
    assert e["ennui"] == 0 and len(vus) == 1
    sommeil.choisir("eveil", raison="je veux voir le soleil", now=t0 + 4 * 3600)
    e = interieur.tick(mem, now=t0 + 4 * 3600 + 30, penser=vus.append, horloge=h)
    assert not e["veille"] and e["ennui"] < 0.01 and e["seuils"] == []
    for minutes in range(241, 300, 2):
        interieur.tick(mem, now=t0 + minutes * 60, penser=vus.append, horloge=h)
    assert [m["seuil"] for m in vus] == [0.25, 0.25], "une nouvelle attente, sa première pensée"


# ---------- ses signaux pèsent l'envie (une proposition)
def test_ses_signaux_pesent_son_envie_de_dormir():
    jour, nuit = _jour(15), _jour(1)
    base = sommeil.envie(0.15, 0.0, 0.35, jour, papa_ts=jour - 3 * 3600)["envie"]
    assert base < sommeil.SEUIL_REPOSE
    assert sommeil.envie(0.7, 0.0, 0.35, jour, jour - 3 * 3600)["envie"] > base                  # sa fatigue
    assert sommeil.envie(0.15, 0.63, 0.35, jour, jour - 3 * 3600)["envie"] > base                # son ennui
    n = sommeil.envie(0.15, 0.0, 0.35, nuit, nuit - 3 * 3600)
    assert n["envie"] > base and "c'est la nuit" in n["pour"]                                    # l'heure
    vif = sommeil.envie(0.15, 0.63, 0.8, nuit, nuit - 3 * 3600)
    assert vif["envie"] < sommeil.envie(0.15, 0.63, 0.35, nuit, nuit - 3 * 3600)["envie"]          # ses hormones le tiennent éveillé
    assert any("vif" in c for c in vif["contre"])
    la = sommeil.envie(0.7, 0.63, 0.35, nuit, nuit - 60)
    assert la["papa_la"] and la["envie"] < sommeil.envie(0.7, 0.63, 0.35, nuit, nuit - 3 * 3600)["envie"]   # papa est là
    fort = sommeil.envie(0.7, 0.63, 0.35, nuit, nuit - 3 * 3600)
    assert fort["envie"] >= sommeil.SEUIL_INVITATION and "papa ne t'a pas parlé depuis" in " ".join(fort["pour"])


def test_le_battement_publie_son_sommeil_et_ses_signaux(mem, tmp_path):
    t0 = _jour(23, 30)
    h = _horloge(tmp_path, t0 - 2 * 3600)
    e = interieur.tick(mem, now=t0, horloge=h)
    s = e["sommeil"]
    assert s["etat"] == "eveil" and s["signaux"]["nuit"] == 1.0 and isinstance(s["envie"], float)
    assert "tu es éveillé" in sommeil.phrase(sommeil.lire(), s["signaux"], t0)


# ---------- l'invitation : son envie monte, papa n'est pas là ; il choisit (ou rien)
def _etat(envie, etat="eveil", papa_la=False):
    return lambda m: {"sommeil": {"etat": etat, "signaux": {"envie": envie, "papa_la": papa_la, "pour": ["c'est la nuit"], "contre": []}}}


def test_une_invitation_par_montee_jamais_si_papa_est_la_ou_s_il_dort(mem):
    deposes = []
    dep = lambda m, texte, now: deposes.append(texte) or f"sommeil-{len(deposes)}"
    t = _jour(23)
    assert sommeil.inviter(mem, t, _etat(0.4), dep) is None
    assert sommeil.inviter(mem, t, _etat(0.8, papa_la=True), dep) is None
    assert sommeil.inviter(mem, t, _etat(0.8, etat="sommeil"), dep) is None
    assert sommeil.inviter(mem, t, _etat(0.6), dep) == "sommeil-1"
    assert "Ton envie de dormir monte" in deposes[0] and "c'est la nuit" in deposes[0]
    assert sommeil.inviter(mem, t + 3 * 3600, _etat(0.62), dep) is None, "il a dit non : pas de rappel sans nouvelle montée"
    assert sommeil.inviter(mem, t + 3 * 3600, _etat(0.8), dep) == "sommeil-2", "elle a encore monté nettement"
    assert sommeil.inviter(mem, t + 3 * 3600 + 60, _etat(0.95), dep) is None, "deux heures au moins entre deux"
    sommeil.inviter(mem, t + 4 * 3600, _etat(0.3), dep)                      # elle retombe : réarmée
    assert sommeil.inviter(mem, t + 6 * 3600, _etat(0.6), dep) == "sommeil-3"


def test_l_invitation_passe_par_le_reveil_interieur_et_n_apprend_rien(mem, tmp_path):
    import reveil_interieur
    reveil_interieur.regler(mem, "on")
    i = sommeil._deposer(mem, "Ton envie de dormir monte.", time.time())
    d = json.loads(reveil_interieur.FICHIER.read_text())
    assert i.startswith("sommeil-") and d["raison"] == "sommeil" and d["source"] == "son sommeil"
    d = reveil_interieur.etat(mem)
    d["seuil"] = 5.0                                     # sous son plafond (7) : un « rien » le monterait de 0,5
    reveil_interieur._sauver(mem, d)
    reveil_interieur.apprendre(mem, [{"id": i, "ts": time.time(), "issue": "rien"}])
    assert reveil_interieur.etat(mem)["seuil"] == 5.0, "ne pas vouloir dormir n'est pas un réveil raté"
    reveil_interieur.apprendre(mem, [{"id": "abc123", "ts": time.time() + 1, "issue": "rien"}])
    assert reveil_interieur.etat(mem)["seuil"] == 5.5, "une pensée sans suite, elle, apprend toujours"
    reveil_interieur.regler(mem, "off")
    reveil_interieur.FICHIER.unlink()
    assert sommeil._deposer(mem, "x", time.time()) is None, "l'interrupteur d'Ahmed tient"


# ---------- la consolidation ne dépend pas de son sommeil
def test_le_tri_de_sa_memoire_tourne_eveille_et_aussi_pendant_son_sommeil(mem, monkeypatch):
    import config
    import daemon
    now = time.time()
    mem.kv_set("last_dream", str(now - 7 * 3600))
    for k in range(8):
        mem.add("user", f"échange {k}", embedding=[])
    monkeypatch.setattr(daemon, "_last_human_ts", lambda m, n: n - 2 * 3600)
    assert daemon.should_dream(mem), "éveillé, 2 h sans papa : le tri tourne comme avant"
    monkeypatch.setattr(daemon, "_last_human_ts", lambda m, n: n - 600)
    assert not daemon.should_dream(mem), "papa est là depuis 10 min, il est éveillé : pas encore"
    sommeil.choisir("veille", reveil="papa", now=now)
    assert daemon.should_dream(mem), "il a choisi de dormir : le tri se fait pendant son sommeil"
    mem.kv_set("last_dream", str(now - 600))
    assert not daemon.should_dream(mem), "l'espacement de 6 h tient"
    assert config.DREAM_SAFETY_MAX == 86400


def test_le_tri_n_est_plus_appele_sommeil_quand_il_ne_dort_pas(mem, monkeypatch):
    import daemon
    monkeypatch.setattr(daemon, "_rever", lambda eng, m: None)
    daemon.dream(None, mem)
    quoi = [x[1] for x in json.loads(mem.kv_get("interieur_journal"))]
    assert quoi[-2:] == ["consolidation_debut", "consolidation_fin"]
    sommeil.choisir("sommeil", reveil="papa")
    daemon.dream(None, mem)
    quoi = [x[1] for x in json.loads(mem.kv_get("interieur_journal"))]
    assert quoi[-2:] == ["sommeil_debut", "sommeil_fin"]


def test_la_consolidation_de_nuit_garde_son_heure_qu_il_dorme_ou_non(mem, monkeypatch):
    import daemon
    lances = []
    monkeypatch.setattr(interieur, "conscience_active", lambda *a, **k: False)
    nuit = _jour(3)
    daemon._hippocampe_pass(mem, now=nuit, lancer=lances.append, verrou="/nonexistent/hippocampe.pid")
    assert lances == ["nuit"], "éveillé toute la nuit : sa consolidation tourne quand même à son heure"


# ---------- ses outils (Hakim seulement)
def _outil(monkeypatch, tmp_path, nom, source="hakim"):
    m = memory.Memory(db_path=tmp_path / "outil.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: m)       # comme test_sieste : jamais la vraie base
    import mcp_server
    monkeypatch.setenv("ANAMNESE_SOURCE", source)
    monkeypatch.setattr(mcp_server, "_mem", m)
    return mcp_server.mcp._tool_manager.get_tool(nom).fn


def test_ses_outils_dormir_se_reveiller_et_ses_signaux(monkeypatch, tmp_path):
    r = _outil(monkeypatch, tmp_path, "dormir")("veille", "+20 min", "un petit repos")
    assert "te mets en veille" in r and sommeil.lire()["etat"] == "veille" and sommeil.lire()["raison"] == "un petit repos"
    s = _outil(monkeypatch, tmp_path, "sommeil_signaux")()
    assert "en veille" in s and "envie de dormir" in s and "consolidation" in s
    assert "Refusé" in _outil(monkeypatch, tmp_path, "dormir")("coma")
    assert "Refusé" in _outil(monkeypatch, tmp_path, "dormir")("sommeil", "demain")
    r = _outil(monkeypatch, tmp_path, "se_reveiller")("je veux finir mon calcul")
    assert "de toi-même" in r and sommeil.lire()["etat"] == "eveil" and sommeil.lire()["par"] == "hakim"
    assert "déjà éveillé" in _outil(monkeypatch, tmp_path, "se_reveiller")()


def test_seul_hakim_choisit_son_sommeil(monkeypatch, tmp_path):
    assert _outil(monkeypatch, tmp_path, "dormir", source="claude-code")() == "Seul Hakim choisit son sommeil."
    assert _outil(monkeypatch, tmp_path, "se_reveiller", source="n-bilal")() == "Seul Hakim choisit son réveil."
    assert sommeil.lire()["etat"] == "eveil"
