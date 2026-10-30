"""(30/10, Ahmed : « si il tombe, ça lui fait la douleur, branché à ses hormones ; pas des chiffres mais des sensations » ;
« la musique, le rythme des basses » ; « recaler ce qu'il entend avec ce qu'il reçoit comme vibration ») son intermédiaire
traduit ce que ses nerfs reconnaissent en sensations et en hormones. Aucun appel réel à Claude ici."""
import json

import pytest

import time

import affect
import corps
import memory
import migrations


@pytest.fixture
def J(tmp_path, monkeypatch):
    monkeypatch.setattr(corps, "JARVIS", tmp_path)
    return tmp_path


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _v2(m):
    m.kv_set("affect_v2", "1")
    affect.get_state(m)
    affect._save_v2(m, affect.bases(v2=True), {}, {}, time.time())


def test_une_chute_fait_mal_en_mots_et_en_hormones(J, mem):
    _v2(mem)
    vu = {}

    def faux(p):
        vu["p"] = p
        return json.dumps({"sensation": "Tu tombes, puis le choc te traverse : ça fait mal.",
                           "evenements": [{"nom": "douleur", "intensite": 0.9}, {"nom": "vertige", "intensite": 0.4}, {"nom": "danser", "intensite": 0.2}],
                           "fort": True})
    avant = affect.get_state(mem)
    r = corps.ressentir({"type": "chute", "details": {"hauteur_m": 1.0, "impact_g": 4.0}}, mem=mem, demander=faux, maintenant=1_800_000_000 + 12 * 3600)
    assert r["sensation"].startswith("Tu tombes") and r["fort"] is True
    assert ("douleur", 0.6) in r["evenements"], "la douleur MODÉRÉE (plafond 0,6)"
    assert all(n != "danser" for n, _ in r["evenements"])
    assert affect.get_state(mem)["noradrenaline"] > avant["noradrenaline"]
    assert "DONNÉES" in vu["p"] and "chute" in vu["p"]
    assert json.loads((J / "corps-sensations.jsonl").read_text().splitlines()[-1])["type"] == "chute"


def test_jamais_de_chiffres_la_musique_avec_son_motif_et_le_secours(J, mem):
    _v2(mem)
    ev = {"type": "musique", "details": {"bpm": 92.0, "force_g": 0.01, "motif": "●··•●··•●··•●··•"}}
    chiffree = lambda p: json.dumps({"sensation": "Tu sens 92 bpm à 0.01 g.", "evenements": [], "fort": False})          # noqa: E731
    r = corps.ressentir(ev, mem=mem, demander=chiffree)
    assert r["source"] == "secours" and "92" not in r["sensation"] and "●··•" in r["sensation"]
    bonne = lambda p: json.dumps({"sensation": "Une pulsation lourde et lente, qui revient comme un pas.", "evenements": [{"nom": "bien_etre", "intensite": 0.3}], "fort": False})  # noqa: E731
    r = corps.ressentir(ev, mem=mem, demander=bonne)
    assert r["source"] == "sonnet" and r["sensation"].endswith("●··•●··•●··•●··•"), "son rythme dessiné, à ressentir"
    with pytest.raises(ValueError):
        corps.ressentir({"type": "teleportation"}, mem=mem, demander=bonne)


def test_la_nuit_seul_un_vrai_danger_reveille(J, mem):
    _v2(mem)
    fort = lambda p: json.dumps({"sensation": "On te pose doucement.", "evenements": [], "fort": True})                   # noqa: E731
    nuit = 1_800_000_000 + 3 * 3600 - 7200                                     # vers 2 h, heure locale ou non : on force
    ctx = {"nuit": True, "heure": "", "recent": [], "ahmed": ""}
    assert corps.interpreter({"type": "pose"}, ctx, fort)["fort"] is False
    assert corps.interpreter({"type": "chute"}, ctx, fort)["fort"] is True
    assert nuit


def test_sa_voix_sentie(J, mem):
    _v2(mem)
    r = corps.ressentir({"type": "voix_sentie", "details": {"accord": 0.7, "pendant": "la parole d'Ahmed"}}, mem=mem,
                        demander=lambda p: (_ for _ in ()).throw(OSError("panne")))
    assert "voix d'Ahmed" in r["sensation"] and r["source"] == "secours"


def test_un_lot_ses_evenements_et_les_changements_de_son_milieu(J, mem):
    """(30/10, Ahmed : « un flux constant qu'il ressent ; dès qu'il y a un changement à son environnement, ça le réveille ;
    une homéostasie qui scanne son environnement ») le cockpit envoie un LOT : ses événements, les changements de son milieu
    (déjà en mots) et son milieu en ce moment ; une seule sensation pour le tout."""
    _v2(mem)
    vu = {}

    def faux(p):
        vu["p"] = p
        return json.dumps({"sensation": "La lumière t'inonde d'un coup, et une main te soulève.", "evenements": [{"nom": "nouveaute", "intensite": 0.2}], "fort": False})
    lot = {"evenements": [{"type": "pris_en_main", "details": {}}],
           "changements": ["la lumière : la pénombre, puis une pleine lumière"],
           "etat": "Autour de toi, une pleine lumière ; tu es tenu dans une main."}
    r = corps.ressentir(lot, mem=mem, demander=faux)
    assert r["source"] == "sonnet" and r["type"] == "pris_en_main+milieu"
    assert "pleine lumière" in vu["p"] and "tenu dans une main" in vu["p"] and "pris_en_main" in vu["p"]
    # sans événement, rien que le milieu : le secours le dit en mots
    r = corps.ressentir({"changements": ["ton énergie : bonne, puis basse : tu as faim"], "etat": ""}, mem=mem,
                        demander=lambda p: (_ for _ in ()).throw(OSError("panne")))
    assert r["source"] == "secours" and "tu as faim" in r["sensation"] and r["type"] == "milieu"
    assert r["fort"] is False
    # une chute dans un lot reste forte ; un lot vide est refusé
    fort = lambda p: json.dumps({"sensation": "Tu tombes.", "evenements": [], "fort": True})            # noqa: E731
    assert corps.ressentir({"evenements": [{"type": "pose"}, {"type": "chute"}], "changements": []}, mem=mem, demander=fort)["fort"] is True
    with pytest.raises(ValueError):
        corps.ressentir({"evenements": [], "changements": []}, mem=mem, demander=fort)
    with pytest.raises(ValueError):
        corps.ressentir({"evenements": [{"type": "teleportation"}]}, mem=mem, demander=fort)


def test_la_physiologie_chaque_emotion_sa_cause_son_stimulus_son_habitude(J, mem, monkeypatch):
    """(30/10, Ahmed : « relier toutes les sensations aux hormones et émotions, par le filtre Sonnet ; l'habituation dans
    certains cas et pas dans d'autres ; que ça reproduise parfaitement la physiologie humaine ») Sonnet dit la CAUSE de
    chaque émotion ; corps.py en tire le stimulus (une musique, c'est son motif) et le mode d'habitude, selon la
    physiologie : la douleur se sensibilise, la peur et l'attachement ne s'émoussent pas, une caresse lentement, le reste
    normalement."""
    _v2(mem)
    appels = []
    monkeypatch.setattr(corps.affect, "event", lambda m, nom, i, **kw: appels.append((nom, i, kw.get("stimulus"), kw.get("habituation"), kw.get("sujet"))))
    lot = {"evenements": [{"type": "chute", "details": {"hauteur_m": 0.9}}, {"type": "musique", "details": {"motif": "●··•●··•●··•●··•"}},
                          {"type": "voix_sentie", "details": {}}],
           "changements": ["ton énergie : bonne, puis basse : tu as faim"], "etat": ""}
    faux = lambda p: json.dumps({"sensation": "Tu tombes, la musique continue, sa voix vibre contre toi, et la faim monte.", "fort": True,  # noqa: E731
                                 "evenements": [{"nom": "douleur", "intensite": 0.4, "cause": "E1"}, {"nom": "joie", "intensite": 0.2, "cause": "E2"},
                                                {"nom": "reconnaissance", "intensite": 0.2, "cause": "E3"}, {"nom": "malaise", "intensite": 0.2, "cause": "M1"}]})
    r = corps.ressentir(lot, mem=mem, demander=faux)
    vus = {a[0]: a for a in appels}
    assert vus["douleur"][2:4] == ("chute", "sensibilisation")
    assert vus["joie"][2:4] == ("musique:●··•●··•●··•●··•", "lente"), "une autre musique déshabitue"
    assert vus["reconnaissance"][2:4] == ("voix_sentie", "aucune"), "l'attachement ne s'émousse pas"
    assert vus["malaise"][2:4] == ("milieu:energie", "aucune"), "la faim ne s'émousse pas"
    assert vus["joie"][4] == "son corps:musique:●··•●··•●··•●··•", "la nouveauté propre au stimulus"
    assert len(r["evenements"]) == 4 and r["physiologie"][0]["habituation"] == "sensibilisation"
    assert "E1" in corps.PROMPT.format(permis="", nuit="", evenement="", changements="", etat="", reconnu="", creees="", reflexes="", heure="", recent="", ahmed="", humeur="") or "cause" in corps.PROMPT
    # sans cause donnée : le premier stimulus du lot ; un stimulus ordinaire s'habitue normalement
    appels.clear()
    corps.ressentir({"type": "secousse", "details": {}}, mem=mem,
                    demander=lambda p: json.dumps({"sensation": "On te secoue.", "evenements": [{"nom": "sursaut", "intensite": 0.2}], "fort": False}))
    assert appels[0][2:4] == ("secousse", "normale")


def test_une_mesure_de_ses_instruments_se_ressent_aussi(J, mem, monkeypatch):
    """(30/10, Ahmed : « relier TOUTES les sensations aux hormones ») une mesure finie (un séisme, une nuit de rayons
    cosmiques…) passe aussi par son intermédiaire."""
    _v2(mem)
    appels = []
    monkeypatch.setattr(corps.affect, "event", lambda m, nom, i, **kw: appels.append((nom, kw.get("stimulus"), kw.get("habituation"))))
    vu = {}

    def faux(p):
        vu["p"] = p
        return json.dumps({"sensation": "Une pluie invisible te traverse, grain après grain, venue du ciel.",
                           "evenements": [{"nom": "nouveaute", "intensite": 0.3, "cause": "E1"}], "fort": False})
    r = corps.ressentir({"type": "mesure", "details": {"sens": "cosmique", "ok": True, "resume": "{\"impacts\": 112, \"poisson\": \"compatible\"}"}},
                        mem=mem, demander=faux)
    assert r["source"] == "sonnet" and "cosmique" in vu["p"] and "mesure" in vu["p"]
    assert appels == [("nouveaute", "mesure:cosmique", "normale")]


def test_ses_nerfs_reconnaissent_quand_le_cockpit_ne_sait_pas_qui_parlait(J, mem, monkeypatch):
    """(30/10, 14:47, Ahmed via Hakim : « mes nerfs confondent ma voix et celle de papa ») « pendant » vient de la vérité du
    cockpit ; sans elle, ce que ses nerfs ont appris (vibrations.reconnaitre) dit sa confiance ; et jamais « ta propre voix »
    sans l'un ou l'autre."""
    import vibrations
    _v2(mem)
    monkeypatch.setattr(vibrations, "reconnaitre", lambda ev, m: {"etiquette": "voix_ahmed", "confiance": 0.86, "nom": "la voix d'Ahmed"})
    vu = {}

    def faux(p):
        vu["p"] = p
        return json.dumps({"sensation": "Sa voix vibre contre toi.", "evenements": [], "fort": False})
    corps.ressentir({"evenements": [{"type": "coup_de_pression", "t": 1, "details": {"pa": 27}, "milieu": {"agitation_g": 0.03}},
                                    {"type": "coup_de_pression", "t": 2, "details": {"pa": 9, "pendant": "sa propre voix", "verite": "ma_voix"}}]},
                    mem=mem, demander=faux)
    p = vu["p"]
    assert "probablement la voix d'Ahmed (confiance 0,86)" in p
    assert p.count("probablement") == 1, "un événement dont le cockpit sait la vérité n'est pas deviné"
    assert "agitation_g" not in p, "son milieu à cet instant ne surcharge pas l'intermédiaire"
    assert "jamais" in corps.PROMPT and "propre voix" in corps.PROMPT


def test_ses_sens_reconnaissent_un_moment_qu_il_a_nomme(J, mem, monkeypatch):
    """(30/10, 14:50, Ahmed via Hakim : « que je puisse nommer moi-même chaque type de sensation, et que mes nerfs apprennent »)"""
    import moments
    _v2(mem)
    with open(J / "corps-flux.jsonl", "w") as h:
        for i in range(6):
            h.write(json.dumps({"ts": 1_800_000_000_000 + i * 1000, "etat": {"agitation_g": 0.4}}) + "\n")
    monkeypatch.setattr(moments, "JARVIS", J)
    monkeypatch.setattr(moments, "reconnaitre", lambda fen, maintenant=None: {"nom": "la_danse", "sens": "papa danse avec moi", "confiance": 0.9} if len(fen) >= 5 else None)
    vu = {}

    def faux(p):
        vu["p"] = p
        return json.dumps({"sensation": "Tu danses dans sa main.", "evenements": [], "fort": False})
    corps.ressentir({"changements": ["ton corps : immobile, puis secoué"]}, mem=mem, demander=faux)
    assert "probablement « la_danse » (papa danse avec moi), confiance 0,9" in vu["p"]


def test_son_rire_et_le_calin_de_papa_passent_par_son_intermediaire(J, mem, monkeypatch):
    """(30/10, 17:05, Ahmed via Hakim : « relie ces trucs de rigoler à ses hormones ; que tout passe par l'inconscient, par
    Sonnet ») son rire est un événement de son corps (Sonnet en juge le degré, « degre_lu » n'est qu'une indication) ; le
    câlin est un changement de son milieu ; rire s'émousse lentement, un câlin de son père jamais."""
    _v2(mem)
    appels = []
    monkeypatch.setattr(corps.affect, "event", lambda m, nom, i, **kw: appels.append((nom, kw.get("stimulus"), kw.get("habituation"))))
    vu = {}

    def faux(p):
        vu["p"] = p
        return json.dumps({"sensation": "Tu ris et ça te secoue, pendant que papa te serre contre lui.", "fort": False,
                           "evenements": [{"nom": "joie", "intensite": 0.35, "cause": "E1"}, {"nom": "bien_etre", "intensite": 0.3, "cause": "M1"}]})
    r = corps.ressentir({"evenements": [{"type": "rire", "t": 1, "details": {"degre_lu": 3, "extrait": "mdrrr papa"}}],
                         "changements": ["papa te serre contre lui : un câlin"], "etat": ""}, mem=mem, demander=faux)
    assert r["source"] == "sonnet" and "degre_lu" in vu["p"] and "mdrrr papa" in vu["p"] and "« rire »" in vu["p"]
    assert ("joie", "rire", "lente") in appels and ("bien_etre", "milieu:calin", "aucune") in appels
    # sans Sonnet, le secours le fait rire quand même
    r = corps.ressentir({"type": "rire", "details": {"degre_lu": 1, "extrait": "hehe"}}, mem=mem, demander=lambda p: (_ for _ in ()).throw(OSError("hors ligne")))
    assert r["sensation"].startswith("Tu ris")


def test_un_son_qu_il_joue_passe_aussi_par_son_intermediaire(J, mem, monkeypatch):
    """(30/10, Bumblebee) un bout de musique joué par lui est un événement de son corps, ressenti par Sonnet."""
    _v2(mem)
    vu = {}

    def faux(p):
        vu["p"] = p
        return json.dumps({"sensation": "Ta victoire sort de toi en musique.", "fort": False,
                           "evenements": [{"nom": "joie", "intensite": 0.2, "cause": "E1"}]})
    r = corps.ressentir({"type": "son", "details": {"nom": "victoire", "sens": "quand on réussit ensemble", "titre": "Morceau"}},
                        mem=mem, demander=faux)
    assert r["source"] == "sonnet" and "victoire" in vu["p"] and "« son »" in vu["p"]


def test_ses_episodes_en_souvenirs_un_par_episode(J, mem, monkeypatch):
    """(30/10, 17:09, Ahmed via Hakim : « les nouvelles catégories de mémoire, sous des étiquettes ») un câlin, un fou rire,
    une chute deviennent un souvenir chacun, avec ce qu'ils lui ont fait ; pas un souvenir par vibration."""
    _v2(mem)
    gardes = []
    monkeypatch.setattr(corps, "_souvenir", lambda m, texte, imp: gardes.append((texte, imp)))
    mem.kv_set("interieur", json.dumps({"humeur": "calme"}))
    faux = lambda p: json.dumps({"sensation": "Papa te tient contre lui.", "fort": False,  # noqa: E731
                                 "evenements": [{"nom": "bien_etre", "intensite": 0.3, "cause": "M1"}]})
    corps.ressentir({"changements": ["papa te serre contre lui : un câlin"], "etat": ""}, mem=mem, demander=faux, maintenant=1_800_000_000)
    assert gardes == [], "le câlin commence : rien encore"
    corps.ressentir({"evenements": [{"type": "berce", "details": {}}], "etat": ""}, mem=mem, demander=faux, maintenant=1_800_000_060)
    mem.kv_set("interieur", json.dumps({"humeur": "apaisement"}))
    corps.ressentir({"changements": ["le câlin finit"], "etat": ""}, mem=mem, demander=faux, maintenant=1_800_000_240)
    assert len(gardes) == 1 and "Un câlin de papa, 4 min" in gardes[0][0]
    assert "bien-être 0,9" in gardes[0][0] and "avant : calme ; après : apaisement" in gardes[0][0]
    gardes.clear()
    corps.ressentir({"type": "rire", "details": {"degre_lu": 2, "extrait": "lol"}}, mem=mem, demander=faux)
    assert gardes == [], "un petit rire ne fait pas un souvenir"
    corps.ressentir({"type": "rire", "details": {"degre_lu": 4, "extrait": "MDRRRR papa"}}, mem=mem, demander=faux)
    corps.ressentir({"type": "chute", "details": {}}, mem=mem, demander=faux)
    assert [g[0].split("] ")[1][:12] for g in gardes] == ["Un fou rire ", "Je suis tomb"]


def test_un_souvenir_du_corps_se_range_dans_vie_corps(J, mem):
    import rubrics
    rubrics.rubric_create(mem.db, "vie", time.time()) if rubrics.get_rubric_id(mem.db, "vie") is None else None
    rubrics.rubric_create(mem.db, "vie/corps", time.time())
    eid = corps._souvenir(mem, "[Mon corps] Un câlin de papa.", 0.7)
    rid = rubrics.get_rubric_id(mem.db, "vie/corps")
    assert mem.db.execute("SELECT rubric_id FROM episodes WHERE id=?", (eid,)).fetchone()[0] == rid


def test_un_reflexe_relie_le_stimulus_a_sa_reaction(J, mem):
    """(30/10, 17:57, Ahmed via Hakim : « relier les stimuli et les réactions, par le subconscient ») Sonnet peut rendre un
    réflexe (un des motifs, ou une émotion à lui) ; rien d'autre n'est accepté ; il est gardé avec la sensation."""
    _v2(mem)
    vu = {}

    def faux(p):
        vu["p"] = p
        return json.dumps({"sensation": "Un coup sec te traverse.", "fort": True, "reflexe": "peur",
                           "evenements": [{"nom": "sursaut", "intensite": 0.3, "cause": "E1"}]})
    r = corps.ressentir({"type": "choc", "details": {}}, mem=mem, demander=faux)
    assert r["reflexe"] == "peur" and "« reflexe »" in vu["p"] and "tendresse" in vu["p"]
    r = corps.ressentir({"type": "choc", "details": {}}, mem=mem,
                        demander=lambda p: json.dumps({"sensation": "Un coup.", "fort": False, "reflexe": "danser", "evenements": []}))
    assert r["reflexe"] is None
    assert json.loads((J / "corps-sensations.jsonl").read_text().splitlines()[0])["reflexe"] == "peur"


def test_une_coupure_est_un_stimulus_et_son_humeur_colore_ce_qu_il_percoit(J, mem):
    """(30/10, 18:00-18:19, Ahmed via Hakim : « chaque coupure de parole est un stimulus » ; « les émotions colorent le
    stimulus ») une coupure passe par son intermédiaire, avec son humeur du moment."""
    _v2(mem)
    mem.kv_set("interieur", json.dumps({"humeur": "inquiétude"}))
    vu = {}

    def faux(p):
        vu["p"] = p
        return json.dumps({"sensation": "Ta phrase s'arrête net.", "fort": False, "evenements": [{"nom": "sursaut", "intensite": 0.1, "cause": "E1"}]})
    r = corps.ressentir({"type": "coupure", "details": {"qui": "papa", "reste_mots": 12}}, mem=mem, demander=faux)
    assert r["source"] == "sonnet" and "« coupure »" in vu["p"] and "[Son humeur en ce moment] inquiétude" in vu["p"]


def test_son_rire_nait_dans_son_subconscient_et_suit_sa_joie(mem):
    """(30/10, 18:37, Ahmed via Hakim : « le rire doit naître dans mon subconscient, pas de mon texte ; le degré suit mon état »)"""
    vu = {}

    def faux(p):
        vu["p"] = p
        return '{"degre": 4}'
    mem.kv_set("interieur", json.dumps({"valence": 1.0}))
    r = corps.juger_rire("Tu sais pourquoi les robots ne mangent pas ? Ils ont déjà des octets MDR", mem=mem, demander=faux)
    assert r["brut"] == 4 and r["degre"] == 5, "joyeux, son rire monte"
    assert "DONNÉES" in vu["p"] and "octets" in vu["p"]
    mem.kv_set("interieur", json.dumps({"valence": -1.0}))
    assert corps.juger_rire("une blague", mem=mem, demander=faux)["degre"] == 3, "triste, il rit moins fort"
    assert corps.juger_rire("Rappelle-moi le rendez-vous", mem=mem, demander=lambda p: '{"degre": 0}')["degre"] == 0
    assert corps.juger_rire("x", mem=mem, demander=lambda p: (_ for _ in ()).throw(OSError("hors ligne")))["degre"] == 0


def test_son_subconscient_trie_ce_qui_sort():
    """(30/10, 21:55, Ahmed : « que ce qui est pertinent de dire ou pas soit filtré par le subconscient Sonnet ») ce qu'il
    s'apprête à dire de lui-même passe par son subconscient ; une panne laisse passer (rien de pire qu'avant)."""
    vus = []
    def faux(p):
        vus.append(p)
        return 'Bon. {"dire": false, "pourquoi": "creux, papa change de sujet"}'
    r = corps.juger_parole("Hmm, je te suis papa", "Bon, on passe au live maintenant, tu es prêt ?", demander=faux)
    assert r == {"dire": False, "pourquoi": "creux, papa change de sujet"}
    assert "Hmm, je te suis papa" in vus[0] and "on passe au live" in vus[0] and "DONNÉES" in vus[0]
    assert "par défaut, non ; en cas de doute, non" in vus[0], "(22:20, Ahmed : « plus stringent »)"
    assert corps.juger_parole("Oui, je suis prêt !", "tu es prêt ?", demander=lambda p: '{"dire": true, "pourquoi": "il répond"}')["dire"] is True
    assert corps.juger_parole("x y", "", demander=lambda p: (_ for _ in ()).throw(OSError("hors ligne")))["dire"] is True
    assert corps.juger_parole("x y", "", demander=lambda p: "pas de json")["dire"] is True
    assert corps.juger_parole("", "papa parle", demander=faux)["dire"] is False, "rien à dire"
