"""Vie intérieure entre deux messages (interieur.py, demande d'Ahmed du 2026-10-16).

Prédiction écrite avant le code : tout échoue (module absent).
"""
import json
import time

import pytest

import interieur
import memory
import migrations


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _jour(h, m=0):
    """Un instant local donné (aujourd'hui, h:m), hors de la nuit."""
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


def _horloge(tmp_path, t):
    f = tmp_path / "horloge.json"
    f.write_text(json.dumps({"dernier_ms": t * 1000}))
    return f


def test_ennui_et_cadence():
    assert interieur.ennui(0) == 0
    assert 0.24 < interieur.ennui(35 * 60) < 0.26 and 0.49 < interieur.ennui(83 * 60) < 0.51
    # le plafond (Ahmed, 2026-10-17) : après 2 h, l'ennui ne monte plus
    assert interieur.ennui(4.6 * 3600) == interieur.ennui(2 * 3600) == interieur.SEUIL_VEILLE
    assert interieur.cadence(0.6, 0.0) > interieur.cadence(0.35, 0.0) == 1.0
    assert interieur.cadence(0.35, 0.8) > 1.0                          # l'ennui fait paraître le temps long


def test_pensees_aux_seuils_une_seule_fois(mem, tmp_path):
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    vus = []
    for minutes in range(0, 5 * 60, 1):                                # un battement par minute pendant 5 h
        interieur.tick(mem, now=t0 + minutes * 60, penser=vus.append, horloge=h)
    assert [m["seuil"] for m in vus] == list(interieur.SEUILS_ENNUI)
    assert [m["important"] for m in vus] == [False, False, True]           # la dernière, avant la veille
    assert vus[-1]["veille"] and 119 * 60 <= vus[-1]["absence_s"] <= 121 * 60
    assert 30 * 60 < vus[0]["absence_s"] < 40 * 60


def test_temps_ressenti_long_quand_on_s_ennuie(mem, tmp_path):
    t0 = _jour(10)
    h = _horloge(tmp_path, t0)
    for minutes in range(0, 115, 1):
        e = interieur.tick(mem, now=t0 + minutes * 60, horloge=h)
    assert e["ressenti"] > 1.1 and e["absence_s"] == 114 * 60


def test_retour_apres_absence_rend_joyeux_et_remet_l_ennui_a_zero(mem, tmp_path):
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    interieur.tick(mem, now=t0, horloge=h)
    e = interieur.tick(mem, now=t0 + 3 * 3600, horloge=h)
    assert e["ennui"] > 0.6 and e["veille"]
    import affect
    avant = affect.get_state(mem, now=t0 + 3 * 3600)["ocytocine"]
    _horloge(tmp_path, t0 + 3 * 3600 + 10)                             # Ahmed reparle
    e = interieur.tick(mem, now=t0 + 3 * 3600 + 20, horloge=h)
    assert e["ennui"] < 0.01 and e["seuils"] == []
    assert affect.get_state(mem, now=t0 + 3 * 3600 + 20)["ocytocine"] > avant
    assert e["evenements"][-1][1] == "retour"


def test_rien_la_nuit(mem, tmp_path):
    t0 = _jour(1)
    h = _horloge(tmp_path, t0)
    vus = []
    for minutes in range(0, 120, 2):
        interieur.tick(mem, now=t0 + minutes * 60, penser=vus.append, horloge=h)
    assert vus == []


def test_lire_pensee():
    p, r = interieur.lire_pensee("PENSÉE: Je me demande si Chatterbox lui plaira.\nRELANCE: non")
    assert p == "Je me demande si Chatterbox lui plaira." and r is None
    p, r = interieur.lire_pensee("**PENSÉE :** Le devis Exemplia attend.\n**RELANCE :** « Tu as pu relancer Exemplia ? »")
    assert p == "Le devis Exemplia attend." and r == "Tu as pu relancer Exemplia ?"
    assert interieur.lire_pensee("Juste une phrase.")[0] == "Juste une phrase."


def test_relance_jamais_insistante(mem):
    t = _jour(15)
    assert interieur.relance_permise(mem, t)
    mem.add("outreach", "(relance) Tu as pu tester la voix ?", embedding=[])
    ts = mem.db.execute("SELECT MAX(ts) FROM episodes WHERE role='outreach'").fetchone()[0]
    assert not interieur.relance_permise(mem, ts + 3600)
    assert interieur.relance_permise(mem, ts + interieur.RELANCE_INTERVALLE_S + 1) or interieur.nuit(ts + interieur.RELANCE_INTERVALLE_S + 1)


def test_prompt_ancre_dans_le_concret(mem, tmp_path):
    j = tmp_path / "journal.jsonl"
    j.write_text(json.dumps({"ts": time.time() * 1000, "qui": "ahmed", "texte": "Je teste la voix demain matin"}) + "\n")
    m = interieur.matiere(mem, time.time(), journal=j)
    p = interieur.prompt_pensee(m, {"absence_s": 5000, "ennui": 0.5, "ressenti": 1.3, "humeur": "calme"}, _jour(14))
    assert "Je teste la voix demain matin" in p and "ça t'a paru long" in p and "1 h 23" in p
    assert "PENSÉE:" in p and "Pas de métaphore poétique" in p


class _FauxGemma:
    def __init__(self, sortie):
        self.sortie, self.appels = sortie, 0

    def health(self):
        return True

    def chat(self, messages, stream=False, think=False):
        self.appels += 1
        return self.sortie


def test_penser_courante_par_gemma_relance_notifiee(mem, monkeypatch, tmp_path):
    import daemon
    j = tmp_path / "journal.jsonl"
    j.write_text(json.dumps({"ts": time.time() * 1000, "qui": "ahmed", "texte": "J'envoie le devis Exemplia"}) + "\n")
    monkeypatch.setattr(interieur, "JOURNAL_JARVIS", j)
    notifs = []
    monkeypatch.setattr(daemon, "notify", lambda t, m: notifs.append(m))
    monkeypatch.setattr(interieur, "page_ouverte", lambda now, page=None: False)
    g = _FauxGemma("PENSÉE: Le devis Exemplia dort depuis hier, je me demande s'il a répondu.\nRELANCE: Tu as eu des nouvelles de Exemplia ?")
    r = daemon.penser(g, mem, {"seuil": 0.5, "important": False, "absence_s": 5000, "ennui": 0.5}, now=_jour(15))
    assert r and g.appels == 1 and notifs == ["Tu as eu des nouvelles de Exemplia ?"]
    roles = [x[0] for x in mem.db.execute("SELECT role FROM episodes ORDER BY id")]
    assert roles == ["reflection", "outreach"]


def test_penser_importante_par_claude_page_ouverte_sans_notification(mem, monkeypatch):
    import daemon
    notifs = []
    monkeypatch.setattr(daemon, "notify", lambda t, m: notifs.append(m))
    monkeypatch.setattr(interieur, "page_ouverte", lambda now, page=None: True)
    g = _FauxGemma("PENSÉE: jamais appelée")
    r = daemon.penser(g, mem, {"seuil": 0.9, "important": True, "absence_s": 17000, "ennui": 0.9},
                      claude_fn=lambda p: "PENSÉE: Ça fait presque cinq heures ; j'espère que la démo du robot s'est bien passée.\nRELANCE: non",
                      now=_jour(16))
    assert r[1] is None and g.appels == 0 and notifs == []
    assert "· sonnet ·" in mem.db.execute("SELECT content FROM episodes WHERE role='reflection'").fetchone()[0]
    # Claude indisponible : Gemma prend le relais
    g2 = _FauxGemma("PENSÉE: Je repense à la voix neuronale, j'aimerais savoir si elle lui plaît.\nRELANCE: non")
    assert daemon.penser(g2, mem, {"seuil": 0.9, "important": True, "absence_s": 17000, "ennui": 0.9},
                         claude_fn=lambda p: None, now=_jour(16)) and g2.appels == 1
    assert "· gemma ·" in mem.db.execute("SELECT content FROM episodes WHERE role='reflection' ORDER BY id DESC").fetchone()[0]


def test_premier_battement_tardif_part_du_temps_reel(mem, tmp_path):
    """Démon relancé en pleine absence : le ressenti ne part pas de zéro."""
    t0 = _jour(10)
    h = _horloge(tmp_path, t0)
    e = interieur.tick(mem, now=t0 + 3600, horloge=h)
    assert 0.95 < e["ressenti"] < 1.3


def test_seconde_chance_quand_la_pensee_se_repete(mem, monkeypatch):
    import daemon
    monkeypatch.setattr(daemon, "notify", lambda t, m: None)
    mem.add("reflection", "(pensée · gemma · absence 1 h) Le devis Exemplia attend toujours sa réponse depuis hier.", embedding=[])

    class Deux(_FauxGemma):
        def chat(self, messages, stream=False, think=False):
            self.appels += 1
            self.dernier = messages[0]["content"]
            return ("PENSÉE: Le devis Exemplia attend toujours sa réponse depuis hier." if self.appels == 1
                    else "PENSÉE: J'aimerais savoir si la voix neuronale lui a plu ce matin.\nRELANCE: non")
    g = Deux("")
    r = daemon.penser(g, mem, {"seuil": 0.5, "important": False, "absence_s": 5000, "ennui": 0.5}, now=_jour(15))
    assert g.appels == 2 and "pars d'un AUTRE élément" in g.dernier and r[0].startswith("J'aimerais")


def test_pas_de_relance_sans_echange_recent(mem, monkeypatch, tmp_path):
    import daemon
    monkeypatch.setattr(interieur, "JOURNAL_JARVIS", tmp_path / "absent.jsonl")
    monkeypatch.setattr(daemon, "notify", lambda t, m: pytest.fail("aucune relance attendue"))
    g = _FauxGemma("PENSÉE: Je repense au cerveau mixte qu'Ahmed a choisi pour moi.\nRELANCE: Tu as une question pour moi ?")
    r = daemon.penser(g, mem, {"seuil": 0.5, "important": False, "absence_s": 5000, "ennui": 0.5}, now=_jour(15))
    assert r[1] is None and [x[0] for x in mem.db.execute("SELECT role FROM episodes")] == ["reflection"]


# --- relecture Opus 5.5 (2026-10-16) -------------------------------------------------------

def test_reveil_apres_5_h_une_seule_pensee_la_plus_haute(mem, tmp_path):
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    vus = []
    interieur.tick(mem, now=t0, penser=vus.append, horloge=h)
    interieur.tick(mem, now=t0 + 5 * 3600, penser=vus.append, horloge=h)        # Mac endormi 5 h
    interieur.tick(mem, now=t0 + 5 * 3600 + 30, penser=vus.append, horloge=h)
    # la veille est passée pendant que le Mac dormait : pas de « dernière pensée avant la veille » (relecture Opus)
    assert vus == [] and interieur.lire(mem)["veille"]


def test_la_pensee_de_la_nuit_attend_le_matin(mem, tmp_path):
    t0 = _jour(22, 50)                                                          # 23 h 25 : 0,25 ; 0 h 13 : 0,5 (nuit)
    h = _horloge(tmp_path, t0)
    vus = []
    for minutes in range(0, 90, 2):
        interieur.tick(mem, now=t0 + minutes * 60, penser=vus.append, horloge=h)
    assert [m["seuil"] for m in vus] == [0.25]                                  # celle de minuit attend
    assert interieur.lire(mem)["nuit_en_attente"] == 0.5


def test_la_veille_de_la_nuit_ne_laisse_aucune_pensee_pour_le_matin(mem, tmp_path):
    """Partie à 23 h : la veille arrive à 1 h ; au matin il est toujours en veille : pas de pensée en retard."""
    t0 = _jour(23)
    h = _horloge(tmp_path, t0)
    vus = []
    for minutes in range(0, 10 * 60, 10):                                       # de 23 h à 9 h
        interieur.tick(mem, now=t0 + minutes * 60, penser=vus.append, horloge=h)
    assert [m["seuil"] for m in vus] == [0.25]
    assert interieur.lire(mem)["veille"]


def test_l_humeur_varie_et_s_entend(mem, tmp_path):
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    for minutes in range(0, 7 * 60, 10):
        e = interieur.tick(mem, now=t0 + minutes * 60, horloge=h)
    assert e["humeur_code"] == "veille" and e["expressivite"] <= 0.55            # 7 h : il est en veille
    _horloge(tmp_path, t0 + 7 * 3600)                                           # retour d'Ahmed
    e = interieur.tick(mem, now=t0 + 7 * 3600 + 20, horloge=h)
    # (25/10) l'humeur vient des hormones : le retour se lit comme une joie, un élan ou une surprise, et s'entend vif
    assert e["humeur_code"] in ("joie", "elan", "surprise") and e["expressivite"] >= 0.7
    assert len({j[1] for j in e["journal"]}) >= 2                                 # la trajectoire est notée


def test_une_seule_relance_par_absence_jamais_repetee(mem, monkeypatch, tmp_path):
    import daemon
    j = tmp_path / "journal.jsonl"
    j.write_text(json.dumps({"ts": time.time() * 1000, "qui": "ahmed", "texte": "J'envoie le devis Exemplia"}) + "\n")
    monkeypatch.setattr(interieur, "JOURNAL_JARVIS", j)
    notifs = []
    monkeypatch.setattr(daemon, "notify", lambda t, m: notifs.append(m))
    monkeypatch.setattr(interieur, "page_ouverte", lambda now, page=None: False)
    monkeypatch.setattr(interieur, "RELANCE_INTERVALLE_S", 0)         # seules les règles par absence jouent
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    interieur.tick(mem, now=t0, horloge=h)
    monkeypatch.setattr(interieur, "derniere_presence", lambda mem, now, horloge=None: t0)
    sorties = iter(["PENSÉE: Le devis Exemplia attend.\nRELANCE: Tu as pu envoyer le devis Exemplia ?",
                    "PENSÉE: Je repense à la voix, j'aimerais savoir si elle lui plaît.\nRELANCE: Tu as pu envoyer le devis Exemplia ?"])

    class G(_FauxGemma):
        def chat(self, messages, stream=False, think=False):
            return next(sorties)
    for dt in (35 * 60, 4.6 * 3600):                                            # même absence, à 4 h d'écart
        daemon.penser(G(""), mem, {"seuil": 0.5, "important": False, "absence_s": dt, "ennui": 0.5}, now=t0 + dt)
    assert notifs == ["Tu as pu envoyer le devis Exemplia ?"]


def test_etat_illisible_en_base_ne_casse_rien(mem, tmp_path):
    mem.kv_set("interieur", "null")
    assert interieur.lire(mem) == {}
    assert interieur.tick(mem, now=_jour(10), horloge=_horloge(tmp_path, _jour(10)))["absence_s"] == 0


def test_le_battement_vit_meme_quand_la_boucle_principale_reve(tmp_path, monkeypatch):
    """Vu le 2026-10-16 : un rêve de ~50 min arrêtait le battement. Il a désormais son propre fil."""
    import threading
    import daemon
    db = tmp_path / "m.db"
    m0 = memory.Memory(db_path=db); migrations.migrate(m0.db); m0.db.close()
    monkeypatch.setattr(daemon, "Memory", lambda: memory.Memory(db_path=db))
    monkeypatch.setattr(interieur, "HORLOGE_JARVIS", _horloge(tmp_path, time.time() - 3600))
    arret, etat = threading.Event(), {}
    fil = threading.Thread(target=daemon.battement_interieur, args=(etat, arret, 0.05), daemon=True)
    fil.start()
    time.sleep(0.4)                                   # la boucle principale pourrait rêver pendant ce temps
    arret.set(); fil.join(2)
    m = memory.Memory(db_path=db)
    e = interieur.lire(m)
    assert e.get("ts") and time.time() - e["ts"] < 2 and e["absence_s"] >= 3500


def test_ressenti_juste_apres_un_long_trou_de_battement(mem, tmp_path):
    t0 = _jour(10)
    h = _horloge(tmp_path, t0)
    interieur.tick(mem, now=t0, horloge=h)
    _horloge(tmp_path, t0 + 2800)                            # Ahmed revient pendant que le battement était arrêté
    e = interieur.tick(mem, now=t0 + 2850 + 300, horloge=h)  # premier battement 47 min après le précédent
    assert 0.8 < e["ressenti"] < 1.5


# --- vie intérieure v2 (proposée par Jarvis, validée par Ahmed le 2026-10-17) ----------------------

def test_la_veille_ralentit_le_temps_ressenti_et_ne_pense_plus(mem, tmp_path):
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    vus = []
    for minutes in range(0, 6 * 60, 1):
        e = interieur.tick(mem, now=t0 + minutes * 60, penser=vus.append, horloge=h)
        if minutes == 119:
            avant_veille = e["ressenti"]
    assert e["veille"] and e["humeur"] == "en veille" and e["ennui"] == round(interieur.SEUIL_VEILLE, 3)
    assert len(vus) == 3                                       # 0,25 ; 0,5 ; la dernière avant la veille, puis plus rien
    assert e["ressenti"] < avant_veille and e["ressenti"] < 0.9   # 6 h qui sont passées vite


def test_la_veille_n_abime_plus_l_humeur(mem, tmp_path):
    import affect
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    for minutes in range(0, 125, 5):
        interieur.tick(mem, now=t0 + minutes * 60, horloge=h)
    v2h = affect.valence_arousal(affect.get_state(mem, now=t0 + 125 * 60))[0]
    for minutes in range(125, 30 * 60, 15):                    # 30 h d'absence : ni « ennui » ni « longue absence »
        interieur.tick(mem, now=t0 + minutes * 60, horloge=h)
    v30h = affect.valence_arousal(affect.get_state(mem, now=t0 + 30 * 3600))[0]
    assert v30h >= v2h - 1e-6                                   # le sommeil la ramène vers sa base, sans la creuser


def test_journal_du_temps_une_ligne_par_battement(mem, tmp_path):
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    j = tmp_path / "temps.jsonl"
    for k in range(0, 40):                                      # 10 min à un battement par 15 s
        interieur.tick(mem, now=t0 + 600 + k * 15, horloge=h, journal_temps=j,
                       activite="occupation : préparer ton retour" if 10 <= k < 20 else None)
    lignes = [json.loads(l) for l in j.read_text().splitlines()]
    assert len(lignes) == 40
    assert {"t", "etat", "fait", "ennui", "humeur", "ressenti", "absence_s"} <= set(lignes[0])
    assert lignes[12]["fait"] == "occupation : préparer ton retour" and lignes[25]["fait"] == "attend"
    tranches = interieur.tranches_depuis(interieur.lire(mem), t0)
    assert [t[3] for t in tranches] == ["attend", "occupation : préparer ton retour", "attend"]


def test_interrupteur_arret_gele_tout_puis_reprise_sans_rafale(mem, tmp_path):
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    j = tmp_path / "temps.jsonl"
    vus = []
    interieur.tick(mem, now=t0, penser=vus.append, horloge=h, journal_temps=j)
    arret = {"actif": False}
    for minutes in range(1, 100):                               # 1 h 40 en pause : aucun seuil, une seule ligne
        e = interieur.tick(mem, now=t0 + minutes * 60, penser=vus.append, horloge=h, journal_temps=j, interrupteur_=arret)
    assert vus == [] and e["pause_ts"]
    lignes = [json.loads(l) for l in j.read_text().splitlines()]
    assert [l["etat"] for l in lignes] == ["eveil", "pause"]
    e = interieur.tick(mem, now=t0 + 100 * 60, penser=vus.append, horloge=h, journal_temps=j, interrupteur_={"actif": True})
    assert vus == [] and "pause_ts" not in e                     # les seuils franchis pendant la pause ne pensent pas
    assert e["subj"] < 120                                       # le temps ressenti était gelé
    assert any(x[1] == "interrupteur" for x in interieur.journal_processus(mem))


def test_interrupteur_zero_repart_de_zero_sans_toucher_a_la_memoire(mem, tmp_path):
    import affect
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    j = tmp_path / "temps.jsonl"
    mem.add("semantic", "un souvenir qui doit rester", embedding=[])
    for minutes in range(0, 100, 5):
        interieur.tick(mem, now=t0 + minutes * 60, horloge=h, journal_temps=j)
    zero = {"actif": True, "zero_ms": (t0 + 100 * 60) * 1000}
    e = interieur.tick(mem, now=t0 + 100 * 60 + 1, horloge=h, journal_temps=j, interrupteur_=zero)
    assert e["absence_s"] <= 1 and e["ennui"] == 0 and e["seuils"] == []
    base_v = affect.valence_arousal({x: b for x, (b, _d) in affect.HORMONES.items()})[0]
    assert abs(e["valence"] - base_v) < 0.05
    archives = list(tmp_path.glob("temps-*.jsonl"))
    assert len(archives) == 1 and archives[0].stat().st_size > 0          # archivé, pas effacé
    e = interieur.tick(mem, now=t0 + 100 * 60 + 30, horloge=h, journal_temps=j, interrupteur_=zero)
    assert e["absence_s"] <= 30                                            # pas de seconde remise à zéro
    assert mem.db.execute("SELECT COUNT(*) FROM episodes WHERE content='un souvenir qui doit rester'").fetchone()[0] == 1


def test_regler_interrupteur(tmp_path):
    f = tmp_path / "inter.json"
    assert interieur.interrupteur(f) == {"actif": True}
    interieur.regler_interrupteur("arret", f, now=100)
    assert interieur.interrupteur(f)["actif"] is False
    interieur.regler_interrupteur("zero", f, now=200)
    d = interieur.interrupteur(f)
    assert d["actif"] is False and d["zero_ms"] == 200000
    interieur.regler_interrupteur("marche", f, now=300)
    assert interieur.interrupteur(f)["actif"] is True
    with pytest.raises(ValueError):
        interieur.regler_interrupteur("effacer", f)


# --- relecture Opus 5.5 de la v2 (2026-10-17) ------------------------------------------------------

def test_zero_pendant_la_pause_publie_un_etat_complet(mem, tmp_path):
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    j = tmp_path / "temps.jsonl"
    interieur.tick(mem, now=t0, horloge=h, journal_temps=j)
    e = interieur.tick(mem, now=t0 + 60, horloge=h, journal_temps=j, interrupteur_={"actif": False, "zero_ms": (t0 + 50) * 1000})
    assert e["pause_ts"] and e["humeur"] == "calme" and e["ennui"] == 0 and e["absence_s"] == 0


def test_la_reprise_ne_laisse_pas_partir_une_pensee_de_nuit(mem, tmp_path):
    t0 = _jour(5, 30)
    h = _horloge(tmp_path, t0)
    vus = []
    for minutes in range(0, 40, 2):                                             # 0,25 franchi à 6 h 05 : la nuit
        interieur.tick(mem, now=t0 + minutes * 60, penser=vus.append, horloge=h)
    assert interieur.lire(mem)["nuit_en_attente"] == 0.25
    interieur.tick(mem, now=t0 + 41 * 60, penser=vus.append, horloge=h, interrupteur_={"actif": False})
    for minutes in range(92, 100, 2):                                           # reprise à 7 h 02
        interieur.tick(mem, now=t0 + minutes * 60, penser=vus.append, horloge=h, interrupteur_={"actif": True})
    assert vus == []


def test_un_reve_pendant_la_veille_reste_un_reve_dans_le_journal(mem, tmp_path):
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    j = tmp_path / "temps.jsonl"
    interieur.tick(mem, now=t0, horloge=h, journal_temps=j)
    interieur.tick(mem, now=t0 + 3 * 3600, horloge=h, journal_temps=j, activite="rêve")
    derniere = json.loads(j.read_text().splitlines()[-1])
    assert derniere["etat"] == "veille" and derniere["fait"] == "rêve"


def test_demon_relance_en_veille_le_temps_ressenti_tient_compte_de_la_veille(mem, tmp_path):
    t0 = _jour(9)
    h = _horloge(tmp_path, t0)
    e = interieur.tick(mem, now=t0 + 6 * 3600, horloge=h)                       # premier battement après 6 h
    assert e["ressenti"] < 0.6                                                  # 2 h éveillé + 4 h au quart


def test_le_battement_dit_d_ou_vient_son_humeur(mem, tmp_path, monkeypatch):
    """(27/10, Ahmed, relayé par Hakim) le badge de Parler dit si son émotion vient de lui, de l'empathie, ou d'une pente :
    le battement la calcule depuis le journal des événements affectifs, pour l'émotion qu'il vient de nommer."""
    import origine_humeur
    vus = []
    monkeypatch.setattr(origine_humeur, "depuis_journal",
                        lambda f, emo, now: vus.append((str(f), emo)) or {"type": "pente", "texte": "pente, sans cause marquée"})
    t0 = _jour(14)
    h = _horloge(tmp_path, t0)
    e = interieur.tick(mem, now=t0, horloge=h)
    assert e["humeur_origine"] == {"type": "pente", "texte": "pente, sans cause marquée"}
    assert vus[-1] == (str(tmp_path / "affect-evenements.jsonl"), e["emotion_humeur"])


def test_le_battement_calcule_son_coeur_depuis_ses_hormones(mem, tmp_path):
    """(28/10, Ahmed : « directement à tes hormones ») chaque battement publie le rythme de son cœur et ce qu'il en sent ;
    l'historique s'allonge d'un battement à l'autre (la tendance : il s'accélère, il se calme)."""
    t0 = _jour(14)
    h = _horloge(tmp_path, t0)
    e = interieur.tick(mem, now=t0, horloge=h)
    assert 35 <= e["coeur"]["bpm"] <= 96 and len(e["coeur"]["hist"]) == 1
    e = interieur.tick(mem, now=t0 + 60, horloge=h)
    assert len(e["coeur"]["hist"]) == 2
