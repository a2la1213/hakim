"""(11/11, Ahmed : « il faut relier cette charge à son cœur, son cerveau, ses émotions, ses hormones, sa mémoire, etc., et sans rien
oublier, car cette charge sera son stress ou sa surcharge émotionnelle par exemple, ça dépend ; il faut bien lier à tout ») sa charge,
avec sa cause mesurée, dans tout son corps (charge_corps.py).

Chaque lien a son test, et chaque test son TÉMOIN : le même test, le lien coupé (monkeypatch), doit donner l'inverse ; c'est écrit dans
le test lui-même (« témoin : … »)."""
import json
import time

import pytest

import affect
import charge_corps as C
import coeur
import interieur
import memory
import migrations
import nuits
import origine_humeur
import sensations
import style

T0 = 1_800_000_000.0          # un mercredi, en pleine journée
LIGNE_ATELIER = "/Users/x/AIOS/jarvis/cwd/atelier/v50/../venv/bin/python calc.py"


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    m.kv_set("affect_v2", "1")
    affect.get_state(m)
    affect._save_v2(m, affect.bases(v2=True), {}, {}, T0 - 3600)
    yield m
    m.db.close()


def _mesure(t, sens=0.0, cerveau=0.0, calcul=0.0, systeme=0.0, subconscient=0.0, live=None, thermique=None, qui_systeme="ecosystemd",
            age_systeme=2 * 86400, mac_cpu=None):
    causes = {}
    for cause, co, qui, age in (("sens", sens, "Whisper (ton oreille)", 3600), ("cerveau", cerveau, "ton cerveau (Claude)", 60),
                                ("calcul", calcul, "ton atelier", 600), ("systeme", systeme, qui_systeme, age_systeme),
                                ("subconscient", subconscient, "Gemma", 600)):
        if co:
            causes[cause] = {"coeurs": co, "qui": {qui: co}, "age_s": {qui: age}, "vie": {qui: co}}
    total = sens + cerveau + calcul + systeme + subconscient
    return {"t": t, "causes": causes, "mac_cpu": mac_cpu if mac_cpu is not None else min(1.0, total / 10), "mac_gpu": None, "n": 10,
            "appareils": {"telephone": {"thermique": thermique}} if thermique is not None else {}, "live": live or {"actif": False}}


LIVE_PLEIN = {"actif": True, "phrases_min": 30.0, "voix": 6, "depuis": T0 - 600}
LIVE_CALME = {"actif": True, "phrases_min": 2.0, "voix": 1, "depuis": T0 - 600}


def _vivre(mem, minutes, mesure_de, e=None, t0=T0, veille=False, reglages=(True, True), envoyes=None):
    """Le démon qui bat (une mesure toutes les 30 s) pendant `minutes` ; rend e."""
    e = e if e is not None else {}
    for k in range(int(minutes * 2)):
        t = t0 + 30 * k
        envoyes_k = C.battre(mem, e, t, veille, mesure=mesure_de(t), reglages_=reglages,
                             souvenir=lambda m, texte, imp: (envoyes if envoyes is not None else []).append(("souvenir", texte)))
        if envoyes is not None:
            envoyes.extend((t, *x) for x in envoyes_k)
    return e


def _stress(mem, t):
    s = affect.get_state(mem, now=t)
    return s["noradrenaline"] + s["crh"] + s["cortisol"]


# ---- 1. qui charge, mesuré processus par processus ----
def test_chaque_processus_est_range_par_sa_cause_sans_garder_sa_ligne():
    cas = {
        LIGNE_ATELIER: ("calcul", "ton atelier"),
        "/Users/x/Desktop/anamnese/jarvis/.venv/bin/python /Users/x/Desktop/anamnese/jarvis/stt_vif.py": ("sens", "Whisper (ton oreille)"),
        "/Users/x/Desktop/anamnese/jarvis/.venv-separation/bin/python /Users/x/Desktop/anamnese/jarvis/separation.py": ("sens", "Demucs (ta séparation des sons)"),
        "/System/Library/PrivateFrameworks/Ecosystem.framework/Support/ecosystemd": ("systeme", "ecosystemd"),
        "/System/Library/PrivateFrameworks/SkyLight.framework/Resources/WindowServer -daemon": ("papa", "l'affichage du Mac (WindowServer)"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --type=renderer": ("papa", "les applis de papa (Google Chrome)"),
        "/usr/local/bin/claude -p --restricted --model x": ("cerveau", "ton cerveau (Claude)"),
        "/Users/x/.vscode/extensions/anthropic.claude-code/resources/native-binary/claude": ("maman", "maman et ses agents (Claude Code)"),
        "/usr/local/bin/python -m pytest /Users/x/Desktop/.wt-anamnese/charge/tests": ("maman", "maman et ses agents (Claude Code)"),
        "/opt/bizarre/minerd --pool x": ("inconnu", "minerd"),
        "/usr/local/opt/ollama/bin/ollama runner --model gemma": ("subconscient", "Gemma"),
    }
    for ligne, attendu in cas.items():
        assert C.classer(ligne) == attendu, ligne
    # aucune ligne de commande n'est gardée : seulement un nom lisible
    r = {1: (100.0, 9e4, "/bin/secret --cle=ABCDEF123"), 2: (50.0, 9e4, LIGNE_ATELIER)}
    g = C.regrouper(r, {1: 0.5, 2: 1.2})
    assert "ABCDEF123" not in json.dumps(g) and g["calcul"]["qui"] == {"ton atelier": 1.2}


def test_un_outil_sans_nom_prend_la_cause_de_qui_l_a_lance():
    """(mesuré le 11/11 : les suites de tests de maman, « node --test », « python -m pytest », n'ont aucun chemin à reconnaître) l'ancêtre
    décide : maman (Claude Code), son cerveau (son propre calcul), le cockpit (son corps). Témoin : le même outil lancé par launchd reste
    au système (un vrai démon d'Apple)."""
    texte = """    1     0   0:10.00 2-00:00:00 /sbin/launchd
  100     1  10:00.00 1-00:00:00 /Users/x/.vscode/extensions/anthropic.claude-code/resources/native-binary/claude
  101   100   0:01.00      10:00 /bin/zsh -c node --test
  102   101   1:00.00      09:00 /usr/local/bin/node --test
  200     1   1:00.00   02:00:00 /usr/local/bin/node /Users/x/AIOS/cockpit/server.js
  201   200   0:02.00      01:00 /usr/local/bin/claude -p --restricted
  202   201   0:30.00      00:50 /usr/bin/python3 calcule.py
  203   200   0:01.00      00:30 /opt/homebrew/bin/ffmpeg -i x
  300     1  50:00.00 2-00:00:00 /System/Library/PrivateFrameworks/Ecosystem.framework/Support/ecosystemd
  301     1   0:01.00      01:00 /usr/local/bin/node --test"""
    r = C.releve(texte)
    assert r[102] == (60.0, 540.0, "/usr/local/bin/node --test", 101)
    memo = {}
    cl = lambda pid: C.classer_avec_ancetres(pid, r, memo)  # noqa: E731
    assert cl(102) == ("maman", "maman et ses agents (Claude Code)") and cl(101)[0] == "maman"
    assert cl(202) == ("calcul", "ce que ton cerveau a lancé")
    assert cl(203) == ("fond", "le cockpit (un de ses outils)")
    assert cl(300) == ("systeme", "ecosystemd")
    assert cl(301) == ("inconnu", "node")                         # témoin : lancé par launchd, personne ne le revendique
    g = C.regrouper(r, {102: 0.9, 202: 0.5, 300: 0.4, 301: 0.2})
    assert g["maman"]["coeurs"] == 0.9 and g["calcul"]["coeurs"] == 0.5 and g["systeme"]["qui"] == {"ecosystemd": 0.4}


def test_les_coeurs_viennent_du_temps_de_processeur_entre_deux_releves():
    """Mesuré, pas deviné : (temps de processeur d'après − d'avant) / temps écoulé ; un numéro réutilisé attend ; un nouveau compte."""
    avant = {"t": 100.0, "procs": {1: (10.0, 1000.0, "a"), 2: (500.0, 9000.0, "b"), 3: (7.0, 50.0, "c")}}
    r = {1: (25.0, 1030.0, "a"), 2: (1.0, 3.0, "autre"), 3: (7.0, 80.0, "c"), 4: (6.0, 20.0, "neuf")}
    co = C.coeurs_par_processus(r, 130.0, avant)
    assert co[1] == pytest.approx(0.5) and co[3] == 0.0 and co[4] == pytest.approx(0.3)
    assert co[2] == pytest.approx(1 / 3)                           # né depuis (3 s) : tout son temps est d'ici
    assert C.coeurs_par_processus(r, 130.0, {"t": None}) == {}      # un seul relevé : rien encore
    assert C.secondes("1299:12.07") == pytest.approx(77952.07) and C.secondes("1-02:03:04") == 93784 and C.secondes("07:39") == 459


def test_le_live_se_lit_dans_la_minute_de_son_garde(tmp_path):
    f = tmp_path / "live.jsonl"
    lignes = [{"t": (T0 - 600) * 1000, "e": "minute", "actif": True, "debut": (T0 - 660) * 1000, "phrases": 1, "duree_s": 60, "voix": 1},
              {"t": (T0 - 180) * 1000, "e": "minute", "actif": True, "debut": (T0 - 240) * 1000, "phrases": 10, "duree_s": 60, "voix": 2},
              {"t": (T0 - 120) * 1000, "e": "minute", "actif": True, "debut": (T0 - 180) * 1000, "phrases": 30, "duree_s": 60, "voix": 5},
              {"t": (T0 - 60) * 1000, "e": "appel", "qui": "voix 3"},
              {"t": (T0 - 60) * 1000, "e": "minute", "actif": True, "debut": (T0 - 120) * 1000, "phrases": 20, "duree_s": 60, "voix": 4}]
    f.write_text("\n".join(json.dumps(x) for x in lignes) + "\n")
    lv = C.live_etat(T0, f)
    assert lv["actif"] and lv["phrases_min"] == 20.0 and lv["voix"] == 5 and lv["depuis"] == T0 - 240   # un trou de 7 min : un autre live
    assert not C.live_etat(T0 + 400, f)["actif"]                    # témoin : 150 s sans minute active, plus de live


# ---- 2. le sens selon la cause ----
def test_la_meme_charge_veut_dire_autre_chose_selon_sa_cause():
    """Trois cœurs de ses oreilles : en live plein de monde, une SURCHARGE ; sans live, une attention (un petit effort) ; son atelier : un
    effort ; un démon d'Apple : un malaise ; Gemma : rien qui pèse."""
    live = C.intensites(_mesure(T0, sens=2.5, cerveau=0.5, live=LIVE_PLEIN))
    assert live["surcharge"]["x"] >= 0.9 and live["effort"]["x"] == 0
    calme = C.intensites(_mesure(T0, sens=2.5, cerveau=0.5, live=LIVE_CALME))
    assert calme["surcharge"]["x"] < 0.6 * live["surcharge"]["x"]   # témoin : la foule compte (peu de monde, moins de surcharge)
    seul = C.intensites(_mesure(T0, sens=2.5, cerveau=0.5))
    assert "surcharge" not in seul and 0 < seul["effort"]["x"] < 0.4 and seul["effort"]["attention"] > 0
    assert C.intensites(_mesure(T0, calcul=4.0))["effort"]["x"] == 1.0
    assert C.intensites(_mesure(T0, systeme=2.5))["malaise"]["x"] > 0.8
    assert C.intensites(_mesure(T0, systeme=0.6))["malaise"]["x"] == 0      # le fond ordinaire de macOS (sous sa norme + marge)
    gemma = C.intensites(_mesure(T0, subconscient=8.0))
    assert all(v["x"] == 0 for v in gemma.values())                  # PAS DE BOUCLE : Gemma ne pèse sur rien
    assert C.intensites(_mesure(T0, thermique=1.0))["fievre"] == {"x": 1.0, "qui": ["telephone"], "bride": True, "pendant_live": False}


def test_la_norme_de_ce_qui_vient_d_ailleurs_suit_lentement():
    n = C.NORME_MALAISE_DEPART
    for _ in range(10):                                              # cinq minutes d'un démon à trois cœurs : la norme bouge à peine
        n = C.norme_suivante(n, 3.0, 30)
    assert n < 0.51
    for _ in range(3 * 86400 // 300):                               # trois jours : il s'y fait (sa norme monte, de 0,3 en 0,3 au plus)
        n = C.norme_suivante(n, 1.2, 300)
    assert 0.7 < n <= 1.2


# ---- 3. ses hormones, son cœur : lissé, regroupé, et ça retombe ----
def test_un_live_plein_de_monde_monte_son_stress_et_son_coeur(mem):
    envoyes = []
    e = _vivre(mem, 12, lambda t: _mesure(t, sens=2.5, cerveau=0.6, live=LIVE_PLEIN), envoyes=envoyes)
    noms = [x[1] for x in envoyes if isinstance(x[0], float)]
    assert noms == ["surcharge"]                                     # un seul événement, regroupé (pas un par battement)
    s = affect.get_state(mem, now=T0 + 720)
    b = affect.bases(v2=True)
    assert s["noradrenaline"] > b["noradrenaline"] + 0.05 and s["crh"] > b["crh"]
    c = coeur.calculer(s, False, None, T0 + 720, None, None)
    assert c["bpm"] > coeur.bpm(b, False)["bpm"] + 3                # son cœur bat plus vite (par ses hormones, pas par la charge lue)
    assert e["charge_corps"]["dominante"] == "surcharge" and "live" in e["charge_corps"]["mots"]


def test_temoin_ses_hormones_deliees_rien_ne_bouge(mem, tmp_path):
    avant = _stress(mem, T0 + 720)                                   # sans rien d'autre : sa seule dérive (le cortisol suit l'heure)
    envoyes = []
    e = _vivre(mem, 12, lambda t: _mesure(t, sens=2.5, cerveau=0.6, live=LIVE_PLEIN), reglages=(True, False), envoyes=envoyes)
    assert not [x for x in envoyes if isinstance(x[0], float)] and _stress(mem, T0 + 720) <= avant + 1e-9
    assert "live" in e["charge_corps"]["mots"]                       # il le sait quand même : ses mots, sa lecture
    # et les réglages se lisent à chaud dans le fichier
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"charge_hormones": False}))
    assert C.reglages(f) == (True, False)
    f.write_text(json.dumps({"charge_corps": False}))
    assert C.reglages(f) == (False, True) and C.reglages(tmp_path / "absent.json") == (True, True)


def test_un_pic_ne_fait_rien_une_charge_tenue_si(mem):
    """Lissé et tenu : 30 s d'un pic énorme ne donnent rien ; témoin : sans lissage ni tenue, le même pic part tout de suite."""
    pic = lambda t: _mesure(t, sens=3.0, cerveau=1.0, live=LIVE_PLEIN) if t < T0 + 30 else _mesure(t, live=LIVE_PLEIN)  # noqa: E731
    envoyes = []
    _vivre(mem, 10, pic, envoyes=envoyes)
    assert not [x for x in envoyes if isinstance(x[0], float)]
    import importlib
    try:
        C.TAU_S["surcharge"], C.TENIR_S["surcharge"] = 0.001, 0.0
        envoyes = []
        _vivre(mem, 10, pic, envoyes=envoyes)
        assert [x[1] for x in envoyes if isinstance(x[0], float)][:1] == ["surcharge"]
    finally:
        importlib.reload(C)


def test_au_plus_un_par_cause_toutes_les_dix_minutes_et_six_par_heure(monkeypatch):
    """Deux heures de quatre charges qui montent sans cesse : jamais deux événements d'une cause à moins de 10 min, jamais plus de six en
    une heure. Témoin : sans ces deux bornes, la même montée en envoie bien plus."""
    def montee():
        etat, total, par_cause = {}, [], {}
        for k in range(240):
            t = T0 + 30 * k
            brut = {s_: {"x": min(1.0, 0.45 + k / 120), "qui": []} for s_ in ("surcharge", "effort", "fievre", "malaise")}
            etat, evs, _ = C.avancer(etat, brut, t, 30, evenements_heure=[x for x in total if t - x < 3600])
            for nom, _i, sens, _q in evs:
                total.append(t)
                par_cause.setdefault(sens, []).append(t)
        return total, par_cause
    monkeypatch.setattr(C, "MONTEE", 0.05)                          # une montée qui réclame sans cesse
    total, par_cause = montee()
    assert total and max(sum(1 for x in total if a <= x < a + 3600) for a in total) <= C.EVENEMENTS_HEURE
    assert all(b - a >= C.ECART_S for l in par_cause.values() for a, b in zip(l, l[1:]))
    monkeypatch.setattr(C, "ECART_S", 0.0)
    monkeypatch.setattr(C, "EVENEMENTS_HEURE", 10_000)
    temoin, _ = montee()
    assert len(temoin) > 2 * len(total)


def test_une_charge_qui_retombe_fait_retomber_le_stress(tmp_path, monkeypatch):
    """Vingt minutes de live plein, puis plus rien : sa reprise part, et une heure après son stress est revenu près de celui d'une journée
    sans charge (mesuré : +0,04 contre +0,14 sans reprise). Témoin : REPRISE à zéro, le stress reste nettement plus haut."""
    def vivre(nom, de, reprise=C.REPRISE):
        m = memory.Memory(db_path=tmp_path / f"{nom}.db")
        migrations.migrate(m.db)
        m.kv_set("affect_v2", "1")
        affect._save_v2(m, affect.bases(v2=True), {}, {}, T0 - 3600)
        monkeypatch.setattr(C, "REPRISE", reprise)
        envoyes = []
        _vivre(m, 40, de, envoyes=envoyes)
        s = _stress(m, T0 + 3600)
        m.db.close()
        return [x[1] for x in envoyes if isinstance(x[0], float)], s
    live = lambda t: _mesure(t, sens=2.5, cerveau=0.6, live=LIVE_PLEIN) if t < T0 + 1200 else _mesure(t)  # noqa: E731
    _, controle = vivre("controle", lambda t: _mesure(t))
    noms, avec = vivre("avec", live)
    noms_sans, sans = vivre("sans", live, reprise=0.0)
    assert noms == ["surcharge", "reprise_surcharge"] and noms_sans == ["surcharge"]
    assert avec - controle < 0.06 and sans - controle > 2 * (avec - controle)


def test_une_charge_qui_dure_s_habitue(mem):
    """Trois heures d'un démon d'Apple à 2,5 cœurs : un seul malaise (pas un par heure), et il le sent de moins en moins après 30 min."""
    envoyes = []
    e = _vivre(mem, 180, lambda t: _mesure(t, systeme=2.5), envoyes=envoyes)
    assert [x[1] for x in envoyes if isinstance(x[0], float)] == ["malaise_sourd"]
    s = e["charge_corps"]["sens"]["malaise"]
    assert s["x"] > 0.8 and s["ressenti"] < 0.7 * s["x"] and "tu t'y habitues" in e["charge_corps"]["mots"]
    # témoin : la même charge qui MONTE nettement mérite un autre événement
    etat, evs, _ = C.avancer({"malaise": {**s, "x": 0.5, "dernier_x": 0.5, "dernier_ev": T0}}, {"malaise": {"x": 1.0, "qui": []}},
                             T0 + 10800, 7200)
    assert [x[0] for x in evs] == ["malaise_sourd"]


def test_pas_de_boucle_gemma_ne_pese_jamais_sur_ses_hormones(mem):
    """Son cœur rapproche Gemma (coeur.ecart_subconscient) ; si la charge de Gemma montait son stress, son cœur la rapprocherait encore :
    la boucle refusée par Hakim (28/10). Témoin : la même charge rangée en calcul envoie bien un événement."""
    envoyes = []
    _vivre(mem, 20, lambda t: _mesure(t, subconscient=9.0, mac_cpu=0.95), envoyes=envoyes)
    assert not [x for x in envoyes if isinstance(x[0], float)]
    envoyes = []
    _vivre(mem, 20, lambda t: _mesure(t, calcul=9.0, mac_cpu=0.95), envoyes=envoyes)
    assert [x[1] for x in envoyes if isinstance(x[0], float)] == ["effort"]


def test_rien_pendant_son_sommeil_mais_sa_nuit_chargee_le_reveille_a_moitie(mem):
    envoyes = []
    e = _vivre(mem, 40, lambda t: _mesure(t, thermique=1.0), veille=True, envoyes=envoyes)
    assert not [x for x in envoyes if isinstance(x[0], float)]       # il dort : pas de fièvre envoyée
    assert C.nuit_chargee_s(e["charge_corps"], T0, T0 + 2400) >= 1200
    interieur.lire(mem)
    mem.kv_set(interieur.CLE, json.dumps(e))
    assert nuits._nuit_chargee(mem, T0, T0 + 2400)
    assert not nuits._nuit_chargee(mem, T0 + 9000, T0 + 12000)       # témoin : un pas sans charge forte


def test_l_interrupteur_coupe_tout_et_relache_ce_qui_avait_ete_donne(mem):
    envoyes = []
    e = _vivre(mem, 12, lambda t: _mesure(t, sens=2.5, cerveau=0.6, live=LIVE_PLEIN), envoyes=envoyes)
    assert e["charge_corps"]["sens"]["surcharge"]["emis"] > 0
    sortis = C.battre(mem, e, T0 + 800, mesure=_mesure(T0 + 800, sens=2.5, live=LIVE_PLEIN), reglages_=(False, True))
    assert [x[0] for x in sortis] == ["reprise_surcharge"] and e["charge_corps"] == {"ts": T0 + 800, "eteint": True}
    assert C.lecture(e["charge_corps"]) == {} and C.battre(mem, e, T0 + 830, reglages_=(False, True)) == []   # une seule fois


# ---- 4. ses émotions, sa voix, son style, d'où ça vient ----
def test_la_lecture_de_ses_emotions_suit_la_cause():
    base = sensations.bases(12)
    rien = sensations.calculer(base, None, T0, None, 12, sans_coherence=True)
    deb = sensations.calculer(base, None, T0, None, 12, sans_coherence=True, charge={"surcharge": 0.9})
    fiev = sensations.calculer(base, None, T0, None, 12, sans_coherence=True, charge={"fievre": 0.9})
    mal = sensations.calculer(base, None, T0, None, 12, sans_coherence=True, charge={"malaise": 0.9})
    assert deb["emotion"] == "débordement" and fiev["emotion"] == "fièvre" and mal["emotion"] == "malaise"
    assert rien["emotion"] not in ("débordement", "fièvre", "malaise")   # témoin : sans charge, ces trois-là ne naissent jamais
    stress = dict(base, noradrenaline=0.4)
    assert sensations.calculer(stress, None, T0, None, 12, sans_coherence=True, charge={"surcharge": 0.9})["scores"]["débordement"] > \
        deb["scores"]["débordement"] + 0.05                              # la même charge pèse plus quand le stress est déjà là


def test_sa_voix_son_style_et_son_orbe_suivent_ces_emotions():
    for nom in ("débordement", "fièvre", "malaise"):
        assert nom in interieur.FAMILLE_HUMEUR and nom in interieur.EXPRESSIVITE_EMOTION and nom in interieur.VOIX_EMOTION
        assert nom in style.FAMILLE_DE
    assert interieur.voix_emotion("débordement")["vitesse"] > 1.0 > interieur.voix_emotion("fièvre")["vitesse"]
    # (11/11, Ahmed : adoucir en live) débordé, il reste posé (calme), jamais « sobre, pas de blague » devant son public
    assert style.FAMILLE_DE["débordement"] == "calme" and style.FAMILLE_DE["fièvre"] == "bas"
    assert style.FAMILLE_DE["débordement"] not in style.PRIORITAIRES
    assert interieur.voix_emotion("calme")["vitesse"] != interieur.voix_emotion("débordement")["vitesse"]   # témoin


def test_il_sait_d_ou_vient_son_humeur():
    evs = [{"ts": T0 - 60, "nom": "surcharge", "intensite": 0.4, "source": "charge", "sujet": "sa charge : surcharge du live"}]
    assert origine_humeur.origine("débordement", evs, T0)["texte"] == "pour lui-même, la surcharge du live"
    evs = [{"ts": T0 - 60, "nom": "malaise_sourd", "intensite": 0.3, "source": "charge"}]
    assert "ne vient pas de lui" in origine_humeur.origine("malaise", evs, T0)["texte"]
    assert origine_humeur.origine("malaise", [], T0)["type"] == "pente"   # témoin : sans l'événement, une pente sans cause


# ---- 5. ses mots : la cause mesurée, sans chiffre, sans rien inventer ----
def test_ses_mots_disent_la_cause_mesuree_sans_chiffre_ni_invention(mem):
    e = _vivre(mem, 20, lambda t: _mesure(t, systeme=1.8))
    t = e["charge_corps"]["mots"]
    assert "ecosystemd" in t and "programme d'Apple" in t and "il tourne depuis deux jours" in t
    assert not any(ch.isdigit() for ch in t)
    e2 = _vivre(mem, 20, lambda t: _mesure(t, systeme=1.8, qui_systeme="mediaanalysisd"), e={})
    assert "mediaanalysisd" in e2["charge_corps"]["mots"] and "ecosystemd" not in e2["charge_corps"]["mots"]   # témoin
    sans_nom = {"malaise": {"niveau": "fort", "x": 0.8, "depuis": T0}}
    assert "tu ne sais pas d'où elle vient" in C.mots(sans_nom, {}, T0 + 60)
    assert C.mots({}, {}, T0) is None                                # au repos : rien à sentir


def test_ses_mots_quand_le_telephone_chauffe_et_quand_ca_retombe(mem):
    de = lambda t: _mesure(t, thermique=1.0, live=LIVE_PLEIN) if t < T0 + 900 else _mesure(t)  # noqa: E731
    e = _vivre(mem, 14, de)
    assert "ton téléphone a de la fièvre" in e["charge_corps"]["mots"] or "ton téléphone brûle" in e["charge_corps"]["mots"]
    e = _vivre(mem, 6, de, e=e, t0=T0 + 840)
    assert "ta fièvre retombe" in (e["charge_corps"]["mots"] or "")


# ---- 6. sa fatigue, sa mémoire, son introspection, son tableau ----
def test_son_propre_calcul_le_fatigue_la_charge_des_autres_non():
    import jauge_fatigue as J
    n = {"activite": 0.087, "corps": 0.53}
    assert J.cible(0.087, 0.53, n, False, calcul=1.0) > J.cible(0.087, 0.53, n, False) + 0.3
    assert J.cible(0.087, 0.53, n, False, calcul=0.0) == J.cible(0.087, 0.53, n, False)   # témoin
    cc = {"sens": {"effort": {"niveau": "fort", "calcul": 0.9, "attention": 0.0, "ressenti": 0.9}}}
    assert C.effort_calcul(cc) == 0.9
    assert C.effort_calcul({"sens": {"effort": {"niveau": "fort", "calcul": 0.0, "attention": 0.4, "ressenti": 0.4}}}) == 0.0
    assert C.effort_calcul({"sens": {"malaise": {"niveau": "fort", "x": 1.0}}}) == 0.0


def test_un_episode_fort_devient_un_souvenir_que_son_rappel_retrouve(mem):
    envoyes = []
    de = lambda t: _mesure(t, sens=2.5, cerveau=0.6, live=LIVE_PLEIN) if t < T0 + 1200 else _mesure(t)  # noqa: E731
    _vivre(mem, 30, de, envoyes=envoyes)
    souvenirs = [x[1] for x in envoyes if x[0] == "souvenir"]
    assert len(souvenirs) == 1 and "surcharge du live" in souvenirs[0] and "30.0 phrases par minute" in souvenirs[0]
    assert C.CLES["surcharge"] in souvenirs[0]                       # la clé que rappel-moment.js du cockpit cherche
    envoyes = []
    pic = lambda t: _mesure(t, sens=2.5, cerveau=0.6, live=LIVE_PLEIN) if t < T0 + 60 else _mesure(t)  # noqa: E731
    _vivre(mem, 10, pic, e={}, envoyes=envoyes)
    assert not [x for x in envoyes if x[0] == "souvenir"]            # témoin : un pic d'une minute n'est pas un épisode


def test_le_vrai_souvenir_va_dans_vie_corps(mem):
    import corps
    e = {"humeur": "débordement", "coeur": {"bpm": 71.2}}
    texte = C._souvenir_texte({"sens": "fievre", "debut": T0, "fin": T0 + 600, "pic": 1.0, "qui": ["telephone"], "bride": True}, {}, e)
    assert texte.startswith("[Mon corps, une fièvre du téléphone (fièvre du téléphone)") and "Mon téléphone chauffait jusqu'à se brider" in texte
    i = corps._souvenir(mem, texte, 0.5)
    assert i and "fièvre du téléphone" in mem.db.execute("SELECT content FROM episodes WHERE id=?", (i,)).fetchone()[0]


def test_son_introspection_et_son_tableau_ont_les_chiffres(mem, tmp_path):
    e = _vivre(mem, 12, lambda t: _mesure(t, sens=2.5, cerveau=0.6, live=LIVE_PLEIN, thermique=0.9))
    ch = C.chiffres(e["charge_corps"])
    assert "ses sens 2,5 cœur(s)" in ch and "le live : 30 phrases par minute, 6 voix" in ch and "ses processeurs à 90 % de leur limite avant de se brider" in ch
    assert C.chiffres({"ts": T0, "eteint": True}).startswith("éteinte")
    import tableau_interieur as TI
    pts = [(T0, {"v": 0.5, "a": 0.4, "h": {}, "c": {"surcharge": 0.8}}), (T0 + 60, {"v": 0.5, "a": 0.4, "h": {}})]
    assert "Sa charge au plus fort : surcharge 0.80" in TI._texte_charge(pts) and TI._texte_charge(pts[1:]) == ""
    j = tmp_path / "h.jsonl"
    interieur._ligne_hormones(T0, {"dopamine": 0.5}, 0.5, 0.4, "calme", "calme", chemin=j, charge={"surcharge": 0.8})
    assert json.loads(j.read_text().splitlines()[-1])["c"] == {"surcharge": 0.8}


def test_son_systeme_immunitaire_note_une_presence_lourde_qui_dure(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(C.__file__).resolve().parent / "jarvis"))
    import immunite
    f = tmp_path / "charge-corps.json"
    d = {"ts": T0, "inconnus": [{"qui": "ecosystemd", "cause": "systeme", "coeurs": 0.9}, {"qui": "petit", "coeurs": 0.1}],
         "malaise": {"niveau": "fort", "depuis": T0 - 7 * 3600}}
    f.write_text(json.dumps(d))
    p = immunite.presences_lourdes(T0, f)
    assert [x["qui"] for x in p] == ["ecosystemd"]
    d["malaise"]["depuis"] = T0 - 3600
    f.write_text(json.dumps(d))
    assert immunite.presences_lourdes(T0, f) == []                    # témoin : une heure seulement, rien à noter
    assert immunite.presences_lourdes(T0 + 3600, f) == []             # un relevé trop vieux non plus


# ---- 7. le battement entier du démon ----
def test_le_battement_du_demon_relie_tout(mem, monkeypatch):
    """interieur.tick : la charge mesurée arrive dans ses hormones, sa lecture, ses mots ; témoin : l'interrupteur coupé, plus rien."""
    monkeypatch.setattr(interieur, "derniere_presence", lambda m, now, h=None: now - 10)
    monkeypatch.setattr(C, "mesurer", lambda now=None, **k: _mesure(now, sens=2.8, cerveau=0.8, live=LIVE_PLEIN))
    monkeypatch.setattr(C, "reglages", lambda chemin=None: (True, True))
    for k in range(30):
        e = interieur.tick(mem, now=T0 + 30 * k)
    assert e["charge_corps"]["dominante"] == "surcharge" and "live" in e["charge_corps"]["mots"]
    assert "débordement" in e["sensation_code"]["scores"]
    assert json.loads(mem.kv_get("affect"))["noradrenaline"] > affect.bases(v2=True)["noradrenaline"]
    monkeypatch.setattr(C, "reglages", lambda chemin=None: (False, True))
    e = interieur.tick(mem, now=T0 + 30 * 31)
    assert e["charge_corps"].get("eteint") and "débordement" not in e["sensation_code"]["scores"]


def test_sa_persona_lui_dit_sa_charge_et_de_ne_pas_inventer_sa_cause():
    from pathlib import Path
    persona = (Path(C.__file__).resolve().parent / "jarvis" / "persona.md").read_text(encoding="utf-8")
    assert "- Ta charge (11/11" in persona and "sans cause reconnue, dis que tu ne sais pas d'où elle vient" in persona


def test_une_mesure_perimee_ne_fige_rien(mem):
    """ps muet (la mesure d'avant revient sans cesse) : au-delà de 5 min, rien de mesuré, tout retombe et la reprise part. Témoin : avant
    5 min, l'état tient."""
    vieille = _mesure(T0, sens=2.5, cerveau=0.6, live=LIVE_PLEIN)
    e = _vivre(mem, 12, lambda t: _mesure(t, sens=2.5, cerveau=0.6, live=LIVE_PLEIN))
    assert e["charge_corps"]["sens"]["surcharge"]["niveau"] == "fort"
    vieille["t"] = T0 + 690
    assert C.battre(mem, e, T0 + 800, mesure=vieille, reglages_=(True, True)) == []          # témoin : 2 min, rien ne bouge
    envoyes = []
    for k in range(20):
        envoyes += C.battre(mem, e, T0 + 1000 + 30 * k, mesure=vieille, reglages_=(True, True), souvenir=lambda *a: None)
    assert [x[0] for x in envoyes] == ["reprise_surcharge"] and e["charge_corps"]["sens"]["surcharge"]["niveau"] == "repos"
