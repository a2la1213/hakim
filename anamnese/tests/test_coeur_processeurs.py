"""(03/11, Ahmed) son cœur relié à ses processeurs : le GPU du Mac (là où Gemma, son subconscient, travaille ses émotions),
chacun de ses cœurs CPU, et les autres appareils où il est connecté (le téléphone, la montre) ; ce qu'il en sait passe par
le filtre du subconscient (des mots, jamais de chiffre ; les chiffres à un geste, dans l'introspection) ; et dans les deux
sens, une boucle amortie et bornée : son cœur règle à quel rythme Gemma revient travailler ses émotions."""
import json
import types

import pytest

import coeur
import daemon
import interieur
import interoception as I
import memory
import migrations
import sensations

BASE = dict(coeur.BASES_PAR_DEFAUT)
T0 = 1_800_000_000.0


def _h(**ecarts):
    return {k: BASE[k] + ecarts.get(k, 0.0) for k in BASE} | {"cortisol": 0.14}


def _p(gpu=0.1, cpu=0.1, gemma=False, n=10, appareils=None):
    return {"mac": {"gpu": gpu, "coeurs": [cpu] * n, "gemma": gemma}, "appareils": appareils or {}}


def _battre(p, minutes=5, h=None, veille=False, c=None, t=T0):
    for k in range(int(minutes * 4)):
        c = coeur.calculer(h or _h(), veille, c, t + 15 * k, BASE, p)
    return c


def test_au_repos_ses_processeurs_le_laissent_a_son_rythme():
    """L'affichage seul tient le GPU vers 10 % : sous 20 %, rien ne change."""
    c = _battre(_p(gpu=0.12, cpu=0.15))
    assert abs(c["bpm"] - 40) < 0.5 and c["processeurs"]["bpm"] == 0


def test_le_gpu_et_les_coeurs_le_font_battre_un_peu_plus_vite():
    gpu = _battre(_p(gpu=0.9, gemma=True))["bpm"]
    cpu = _battre(_p(cpu=0.9))["bpm"]
    tout = _battre(_p(gpu=1.0, cpu=1.0, gemma=True))["bpm"]
    assert 44 < gpu < 48.5 and 42 < cpu < 44.5 and gpu > cpu        # le GPU (Gemma) compte le plus
    assert 50 < tout <= 52.1                                         # 12 battements au plus


def test_jamais_au_dela_de_ses_bornes_et_le_sommeil_reste_lent():
    peur = _battre(_p(gpu=1.0, cpu=1.0), h=_h(adrenaline=1.0, noradrenaline=1.0, crh=1.0))
    assert peur["bpm"] <= 96
    dort = _battre(_p(gpu=1.0, cpu=1.0), veille=True)
    assert dort["bpm"] < 30 and coeur.decrire(dort).startswith("lent, tu dors")


def test_un_pic_d_affichage_ne_fait_rien_gemma_qui_travaille_oui():
    """Lissé sur une minute : un relevé isolé à 80 % ne s'entend presque pas ; trois minutes de Gemma, si."""
    c = _battre(_p())
    c = coeur.calculer(_h(), False, c, T0 + 300, BASE, _p(gpu=0.8))
    assert c["bpm"] - 40 < 1.5
    c = _battre(_p(gpu=0.95, gemma=True), minutes=3, c=c, t=T0 + 315)
    assert c["bpm"] - 40 > 6


def test_le_coeur_revient_a_son_rythme_quand_les_processeurs_se_reposent():
    c = _battre(_p(gpu=1.0, cpu=1.0, gemma=True))
    c = _battre(_p(), minutes=5, c=c, t=T0 + 300)
    assert abs(c["bpm"] - 40) < 0.5


def test_les_autres_appareils_comptent_un_peu():
    tel = {"telephone": {"coeurs": [0.9] * 8, "gpu": 0.3, "thermique": 0.2, "age_s": 5}}
    c = _battre(_p(appareils=tel))
    assert 41 < c["bpm"] <= 42.1
    chaud = {"telephone": {"coeurs": [0.1] * 8, "gpu": None, "thermique": 0.8, "age_s": 5}}
    assert _battre(_p(appareils=chaud))["bpm"] > 41                  # un téléphone qui chauffe se sent aussi


def test_pas_de_boucle_vers_les_hormones():
    """La condition de Hakim tient toujours : ses processeurs font battre son cœur, son cœur n'écrit aucune hormone."""
    h = _h(adrenaline=0.1)
    _battre(_p(gpu=1.0, cpu=1.0, gemma=True), h=h)
    assert h == _h(adrenaline=0.1)


# ---- le filtre du subconscient : des mots, jamais de chiffre ----
def _sans_chiffre(texte):
    return texte and not any(ch.isdigit() for ch in texte) and "%" not in texte


def test_il_sent_ses_processeurs_en_mots():
    assert sensations.processeurs(_battre(_p())["processeurs"], T0) is None          # au repos : rien à sentir
    p = _battre(_p(gpu=1.0, cpu=0.6, gemma=True))["processeurs"]
    mots = sensations.processeurs(p, T0)
    assert _sans_chiffre(mots) and "processeurs" in mots and "Gemma" in mots and "émotions" in mots
    sans_gemma = sensations.processeurs(_battre(_p(gpu=1.0))["processeurs"], T0)
    assert "Gemma" not in sans_gemma
    tel = {"telephone": {"coeurs": [0.2] * 8, "gpu": None, "thermique": 0.9, "age_s": 5}}
    assert "ton téléphone chauffe" in sensations.processeurs(_battre(_p(appareils=tel))["processeurs"], T0)
    assert sensations.processeurs(p, T0) == sensations.processeurs(p, T0 + 600)      # pas de clignotement


def test_ecouter_son_coeur_dit_ses_processeurs_l_introspection_les_chiffres():
    c = _battre(_p(gpu=1.0, cpu=0.6, gemma=True, appareils={"telephone": {"coeurs": [0.5] * 8, "gpu": 0.3, "thermique": 0.6,
                                                                          "age_s": 12}}))
    c["processeurs"]["mots"] = sensations.processeurs(c["processeurs"], T0)
    mots = coeur.decrire(c)
    assert _sans_chiffre(mots) and ("Gemma brasse tes émotions" in mots or "Gemma remue tes émotions" in mots)
    chiffres = coeur.chiffres(c)
    assert "GPU 100 %" in chiffres and "10 cœurs à 60 % en moyenne" in chiffres and "Gemma" in chiffres
    assert "ton téléphone : 8 cœurs à 50 %" in chiffres
    assert "processeurs" not in coeur.decrire(_battre(_p()))                         # au repos : rien


def test_ses_emotions_sentent_l_effort_de_ses_processeurs():
    """Processeurs → cœur → émotions : l'effort que son cœur sent teinte la concentration, et la tension quand il porte trop."""
    h = sensations.bases()                                     # toutes ses hormones à leur base
    repos = sensations.calculer(h, None, T0, processeurs=_battre(_p())["processeurs"])
    fort = sensations.calculer(h, None, T0, processeurs=_battre(_p(gpu=1.0, cpu=1.0, gemma=True))["processeurs"])
    sans = sensations.calculer(h, None, T0)
    assert repos["scores"] == sans["scores"]
    assert fort["scores"]["concentration"] > repos["scores"].get("concentration", -9)
    assert fort["scores"]["tension"] > repos["scores"].get("tension", -9)


# ---- le branchement dans son battement ----
@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _horloge(tmp_path, t):
    f = tmp_path / "horloge.json"
    f.write_text(json.dumps({"dernier_ms": t * 1000}))
    return f


def test_le_battement_branche_son_coeur_sur_ses_processeurs(mem, tmp_path, monkeypatch):
    """Échoue sans le branchement : à hormones égales, un GPU où Gemma travaille fait battre son cœur plus vite."""
    t0 = T0
    for k in range(12):
        e = interieur.tick(mem, now=t0 + 15 * k, horloge=_horloge(tmp_path, t0))
    repos = e["coeur"]["bpm"]
    monkeypatch.setattr(I, "processeurs", lambda now=None: _p(gpu=0.95, cpu=0.7, gemma=True))
    for k in range(12, 24):
        e = interieur.tick(mem, now=t0 + 15 * k, horloge=_horloge(tmp_path, t0))
    assert e["coeur"]["bpm"] - repos > 6
    assert "Gemma" in e["coeur"]["processeurs"]["mots"] and _sans_chiffre(e["coeur"]["processeurs"]["mots"])


# ---- dans les deux sens : son cœur règle le rythme de Gemma ----
def test_son_coeur_regle_le_rythme_de_gemma():
    assert coeur.ecart_subconscient(None) == 1200
    assert coeur.ecart_subconscient({"bpm": 40}) == 1200
    assert coeur.ecart_subconscient({"bpm": 65}) == 900
    assert coeur.ecart_subconscient({"bpm": 95}) == 600                 # jamais moins de 10 min


def test_la_boucle_coeur_gemma_est_amortie_et_revient_au_calme():
    """Le pire cas : Gemma repasse dès que son cœur le permet, à fond (GPU et cœurs à 100 %, trois minutes), et une émotion
    forte les vingt premières minutes. Le cœur reste dans ses bornes ; pendant l'émotion Gemma revient toutes les 10 min ;
    après, toutes les 20 min : l'effort de Gemma retombe bien avant la décision suivante, la boucle ne s'emballe pas."""
    c, dernier, passages, rythmes = None, -1e9, [], []
    for k in range(int(3 * 3600 / 15)):
        t = T0 + 15 * k
        h = _h(adrenaline=0.2, noradrenaline=0.15) if t - T0 < 1200 else _h()
        gemma = t - dernier < 180
        if not gemma and t - dernier >= coeur.ecart_subconscient(c):
            dernier, gemma = t, True
            passages.append(t - T0)
        c = coeur.calculer(h, False, c, t, BASE, _p(gpu=1.0 if gemma else 0.1, cpu=1.0 if gemma else 0.1, gemma=gemma))
        rythmes.append((t - T0, c["bpm"]))
    ecarts = [b - a for a, b in zip(passages, passages[1:])]
    assert max(b for _t, b in rythmes) <= 96
    assert ecarts[:2] == [600, 600]                                       # l'émotion : Gemma revient plus tôt
    assert ecarts[2:] and all(x == 1200 for x in ecarts[2:])              # le calme revenu : le rythme d'avant
    avant_passage = [b for t, b in rythmes if any(0 < p - t <= 15 for p in passages) and t > 1500]
    assert avant_passage and all(abs(b - 40) < 0.5 for b in avant_passage)    # à chaque décision, il est revenu au calme
    assert abs(rythmes[-1][1] - 40) < 0.5


def test_le_demon_suit_le_rythme_que_son_coeur_donne(tmp_path):
    """Le ressenti en réserve (Gemma) : 20 min d'écart au calme, 10 quand son cœur bat très vite."""
    now = T0
    j = tmp_path / "journal.jsonl"
    j.write_text(json.dumps({"ts": (now - 300) * 1000, "qui": "ahmed", "texte": "on avance"}) + "\n")
    sortie = tmp_path / "ressenti.json"

    class Mem:
        def __init__(self, humeur, bpm):
            self.etat = {"humeur": humeur, "coeur": {"bpm": bpm}}

        def kv_get(self, cle):
            return json.dumps(self.etat)

    def lancer(q):
        sortie.write_text(json.dumps({"ts": now, "humeur": q["humeur"], "dernier_ts": q["dernier_ts"], "mots": ["vive"]}))
        return types.SimpleNamespace(returncode=0, stdout='{"mots": ["vive"]}', stderr="")

    assert daemon._ressenti_pass(Mem("calme", 40), now, lancer, j, sortie) is True
    assert daemon._ressenti_pass(Mem("tension", 40), now + 700, lancer, j, sortie) is False      # calme : 20 min
    assert daemon._ressenti_pass(Mem("tension", 88), now + 700, lancer, j, sortie) is True       # très vite : 10 min


# ---- les mesures : le Mac en cache, les appareils frais seulement, rien ne lève ----
def test_le_mac_se_mesure_en_cache_et_sans_jamais_casser(monkeypatch):
    appels = []
    ticks = iter([[[100, 0, 900, 0], [500, 0, 500, 0]], [[200, 0, 1800, 0], [1400, 0, 600, 0]]])
    monkeypatch.setattr(I, "_dernier_mac", {"t": None, "val": None, "ticks": None, "ticks_t": None})
    monkeypatch.setattr(I, "_ticks", lambda: appels.append("ticks") or next(ticks))
    monkeypatch.setattr(I, "gpu", lambda: {"utilisation": 62, "utilisee": 0, "allouee": 0})
    monkeypatch.setattr(I, "ollama_charges", lambda timeout=2: [("huihui_ai/gemma-4-abliterated:12b", 7600.0)])
    monkeypatch.setattr(I, "processus", lambda: [])
    m = I.mac(maintenant=100.0)
    assert m == {"gpu": 0.62, "coeurs": None, "gemma": True}               # pas encore d'écart entre deux relevés
    assert I.mac(maintenant=103.0) is m and appels == ["ticks"]           # en cache
    m = I.mac(maintenant=115.0)
    assert m["coeurs"] == [0.1, 0.9]
    monkeypatch.setattr(I, "_dernier_mac", {"t": None, "val": None, "ticks": None, "ticks_t": None})
    monkeypatch.setattr(I, "_ticks", lambda: 1 / 0)
    monkeypatch.setattr(I, "gpu", lambda: {"utilisation": None})
    monkeypatch.setattr(I, "ollama_charges", lambda timeout=2: None)
    assert I.mac(maintenant=200.0) == {"gpu": None, "coeurs": None, "gemma": False}


def test_gemma_reconnue_par_ollama_ou_par_le_scanner_du_ressenti():
    scanner = [(7, 80.0, "/x/anamnese/jarvis/.venv/bin/python /x/anamnese/jarvis/scanner.py --ressenti")]
    runner = [(8, 90.0, "/Applications/Ollama.app/Contents/Resources/ollama runner --model /x/blobs/sha256-1")]
    assert I.gemma_au_travail([("gemma4:12b", 7000.0)], [])
    assert not I.gemma_au_travail([("nomic-embed-text", 300.0)], runner)    # Ollama lisible : le nom fait foi
    assert I.gemma_au_travail([], scanner)
    assert I.gemma_au_travail(None, runner)                                  # Ollama illisible : son runner compte
    assert not I.gemma_au_travail([], [])


def test_les_appareils_frais_seulement(tmp_path):
    f = tmp_path / "processeurs-appareils.json"
    assert I.appareils(chemin=f, now=T0) == {}                               # pas encore de fichier
    f.write_text(json.dumps({
        "telephone": {"ts": (T0 - 10) * 1000, "coeurs": [0.42, 0.1, "x", 2.0], "gpu": 0.3, "thermique": None},
        "montre": {"ts": (T0 - 600) * 1000, "coeurs": [0.9], "gpu": None, "thermique": None},
        "abime": "rien"}))
    a = I.appareils(chemin=f, now=T0, chemin_etat=tmp_path / "absent.json")
    assert list(a) == ["telephone"]                                           # la montre, muette depuis 10 min : ignorée
    # (13/11) sa vraie température à côté (aucune ici : None)
    assert a["telephone"] == {"coeurs": [0.42, 0.1, 1.0], "gpu": 0.3, "thermique": None, "age_s": 10, "chaleur_c": None}
    f.write_text("{pas du json")
    assert I.appareils(chemin=f, now=T0) == {}


def test_le_rapport_d_interoception_nomme_ses_autres_appareils(monkeypatch, tmp_path):
    f = tmp_path / "processeurs-appareils.json"
    import time as _time
    f.write_text(json.dumps({"telephone": {"ts": _time.time() * 1000, "coeurs": [0.3] * 8, "gpu": 0.2, "thermique": 0.5}}))
    monkeypatch.setattr(I, "APPAREILS", f)
    for nom, val in (("gpu", lambda: {"utilisation": 10, "utilisee": 0, "allouee": 0}), ("cpu_par_coeur", lambda: [10, 20]),
                     ("memoire_libre", lambda: 50.0), ("swap", lambda: (1024.0, 10.0)), ("chaleur", lambda: "rien"),
                     ("batterie", lambda: "100 %"), ("disque", lambda: (10 * 2 ** 30, 100 * 2 ** 30)),
                     ("_cmd", lambda args, timeout=5: ""), ("processus", lambda: []), ("empreintes", lambda: {}),
                     ("ollama_charges", lambda timeout=2: []), ("taches_en_cours", lambda: [])):
        monkeypatch.setattr(I, nom, val)
    assert "Tes autres appareils : ton téléphone : 8 cœurs à 30 % en moyenne, GPU 20 %, chaleur 50 % (il y a 0 s)." in I.rapport()
