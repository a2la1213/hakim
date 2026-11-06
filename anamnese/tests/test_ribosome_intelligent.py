"""(05/11, Ahmed : « et si tous ses paramètres étaient réglables, mais aussi automatiquement réglables par Hakim lui-même et ses Mini Hakim /
Super Hakim ; s'il pouvait ajuster lui-même au fur et à mesure du temps ; un bouton « ribosome intelligent », et Hakim apprendrait à
l'utiliser ») son bilan mesuré, ses réglages bornés, ce que papa vient de régler passe avant, chaque mode apprend de son côté."""
import json
from pathlib import Path

from jarvis import ribosome_intelligent as ri

T = 1_800_000_000_000


def _paquet(t, choisi="opus", garde="un deux trois", vitesse=1800, stringence=2, ms=1200):
    return json.dumps({"t": t, "tour": 1, "ribosome": 1, "pensees": 1, "ms": ms, "vitesse_ms": vitesse, "stringence": stringence,
                       "garde": garde, "choisi": choisi, "lecteurs": []})


def test_bilan_mesure_ce_qui_compte():
    pistes = [_paquet(T - 50_000), _paquet(T - 40_000, choisi="panne", garde="toute la pensée entière ici"),
              _paquet(T - 30_000, garde=""), _paquet(T - 20_000, garde="quatre mots bien gardés"),
              _paquet(T - 9_000_000),                                                 # hors de la fenêtre
              json.dumps({"t": T - 10_000, "modele": "haiku", "ms": 900})]            # une piste, pas un paquet
    voix = [json.dumps({"t": T - 45_000, "e": "ribosome_dit"}), json.dumps({"t": T - 43_000, "e": "sortie_voix"}),
            json.dumps({"t": T - 25_000, "e": "passe_saute", "sautes": 3}), json.dumps({"t": T - 15_000, "e": "suite_sautee"}),
            json.dumps({"t": T - 14_000, "e": "coupure_au_chunk"})]
    b = ri.bilan(pistes, voix, T - 60_000, T)
    assert b["paquets"] == 4
    assert b["panne"] == 0.25 and b["rien"] == 1 / 3
    assert b["mots"] == (3 + 0 + 4) / 3
    assert b["voix_ms"] == 2000
    assert (b["sautes"], b["suites_sautees"], b["coupures"]) == (3, 1, 1)
    t = ri.texte(b)
    assert "4 paquets" in t and "25 %" in t and "2 s" in t


def test_borner_et_cles():
    assert ri.borner("choix_ms", 99999) == 6000 and ri.borner("stringence", 0) == 1 and ri.borner("relais_pct", 5) == 10
    assert ri.borner("sauter_passe_s", 2.26) == 2.5
    assert ri.borner("inconnu", 3) is None
    assert set(ri.CLES_CORPS) == {"sauter_suite_ms", "sauter_passe_s", "lire_apres_silence_ms", "epissure_meubles_max", "chunk_papa_ms"}   # (06/11) les siens aussi


def _maison(tmp_path, corps=None, rib=None, profils=None, ajustements=(), mode=None):
    j = tmp_path / "AIOS" / "jarvis"
    j.mkdir(parents=True)
    (j / "ribosome-reglage.json").write_text(json.dumps(rib or {"stringence": 2, "vitesse": "eclair", "choix_ms": 1800, "plafond_mots": 40}))
    (j / "corps-reglages.json").write_text(json.dumps(corps if corps is not None else {"micro_ouvert": True, "sauter_passe_s": 3}))
    if profils is not None:
        (j / "reglages-profils.json").write_text(json.dumps(profils))
    if ajustements:
        (j / "ribosome-ajustements.jsonl").write_text("".join(json.dumps(a) + "\n" for a in ajustements))
    if mode:
        (j / "mode-courant.json").write_text(json.dumps({"modele": mode[0], "profil": mode[1]}))
    return j


def test_il_regle_garde_le_reste_note_sa_raison_et_son_mode_apprend(tmp_path):
    j = _maison(tmp_path, profils=[{"nom": "Hakim", "ribosome": {"choix_ms": 1800, "plafond_mots": 40}, "corps": {"sauter_passe_s": 3}}],
                mode=("sonnet", "Hakim"))
    r = ri.ajuster(j, {"choix_ms": 2000, "sauter_passe_s": 4}, "trop de pannes à 1,8 s", maintenant=T)
    assert r["fait"] == {"choix_ms": [1800, 2000], "sauter_passe_s": [3, 4]} and not r["refuse"]
    rib = json.loads((j / "ribosome-reglage.json").read_text())
    assert rib["choix_ms"] == 2000 and rib["plafond_mots"] == 40 and rib["vitesse"] == "eclair", "le reste du réglage de papa reste"
    corps = json.loads((j / "corps-reglages.json").read_text())
    assert corps["sauter_passe_s"] == 4 and corps["micro_ouvert"] is True, "ses autres interrupteurs ne bougent pas"
    a = [json.loads(x) for x in (j / "ribosome-ajustements.jsonl").read_text().splitlines()]
    assert a[-1]["par"] == "hakim" and a[-1]["raison"] == "trop de pannes à 1,8 s" and a[-1]["mode"] == "Hakim"
    p = json.loads((j / "reglages-profils.json").read_text())[0]
    assert p["ribosome"]["choix_ms"] == 2000 and p["corps"]["sauter_passe_s"] == 4, "son mode apprend de son côté"


def test_eteint_ou_papa_vient_de_regler_refuse(tmp_path):
    j = _maison(tmp_path, corps={"ribosome_intelligent": False})
    r = ri.ajuster(j, {"choix_ms": 2000}, "essai", maintenant=T)
    assert not r["fait"] and r["eteint"]
    j2 = _maison(tmp_path / "b", ajustements=[{"ts": T - 10 * 60_000, "par": "papa", "cles": ["choix_ms"]}])
    r = ri.ajuster(j2, {"choix_ms": 2000, "stringence": 3}, "essai", maintenant=T)
    assert "choix_ms" in r["refuse"] and r["fait"] == {"stringence": [2, 3]}, "ce que papa a réglé il y a moins de 30 min passe avant"
    r = ri.ajuster(j2, {"choix_ms": 2000}, "plus tard", maintenant=T + 25 * 60_000)
    assert r["fait"] == {"choix_ms": [1800, 2000]}


def test_ses_derniers_reglages_avec_leur_effet():
    pistes = [_paquet(T - 20 * 60_000 + k * 60_000, choisi="panne" if k < 5 else "opus") for k in range(20)]
    aj = [{"ts": T - 10 * 60_000, "par": "hakim", "fait": {"choix_ms": [1500, 2000]}, "raison": "pannes"}]
    l = ri.effets(aj, pistes, [], T)
    assert l[0]["avant"]["panne"] > l[0]["apres"]["panne"]


def _mcp(tmp_path, monkeypatch):
    import memory
    import migrations
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    return mcp_server


def test_ses_outils_ne_defont_plus_le_reglage_de_papa_et_reglent_le_reste(tmp_path, monkeypatch):
    m = _mcp(tmp_path, monkeypatch)
    j = _maison(tmp_path)
    m.ribosome_regler(stringence=3)
    r = json.loads((j / "ribosome-reglage.json").read_text())
    assert (r["stringence"], r["choix_ms"], r["plafond_mots"]) == (3, 1800, 40), "sa stringence ne réécrit plus tout le fichier"
    t = m.ribosome_regler(choix_ms=2000, sauter_passe_s=4, raison="trop de pannes")
    assert "choix_ms 1800 → 2000" in t and "sauter_passe_s 3 → 4" in t
    assert json.loads((j / "corps-reglages.json").read_text())["sauter_passe_s"] == 4
    b = m.ribosome_bilan(30)
    assert "Tes 30 dernières minutes" in b and "Ribosome intelligent : allumé." in b and "choix_ms 2000" in b
    (j / "corps-reglages.json").write_text(json.dumps({"ribosome_intelligent": False}))
    assert "papa n'a pas allumé" in m.ribosome_regler(choix_ms=1500)


def test_le_retour_de_chaque_reglage_lui_revient_tout_seul(tmp_path):
    """(05/11, Ahmed : « il faut bien qu'il ait le retour de chaque petit réglage, pour qu'il ajuste correctement »)"""
    t0 = T - 60 * 60_000
    pistes = [_paquet(t0 + k * 60_000, choisi="panne" if k < 20 and k % 3 == 0 else "opus") for k in range(50)]
    aj = [{"ts": t0 + 20 * 60_000 - 1, "par": "hakim", "fait": {"choix_ms": [1500, 2000]}, "raison": "pannes"},
          {"ts": t0 + 55 * 60_000, "par": "hakim", "fait": {"stringence": [2, 3]}, "raison": "trop bavard"}]
    dus = ri.retours_dus(aj, pistes, [], T)
    assert len(dus) == 1, "le second n'a pas encore assez de paquets"
    ts, t = dus[0]
    assert ts == aj[0]["ts"] and "sur 20 paquets" in t and "sans tri 32 % → 0 %" in t and "« pannes »" in t
    assert ri.retours_dus(aj, pistes, [], T, rendus=[ts]) == [], "une seule fois"
    plus_tard = ri.retours_dus(aj, pistes, [], T + 61 * 60_000, rendus=[ts])
    assert plus_tard and "pas mesurable" in plus_tard[0][1], "une heure sans assez de paroles"
    j = _maison(tmp_path)
    (j / "ribosome-ajustements.jsonl").write_text("".join(json.dumps(a) + "\n" for a in aj))
    (j / "pistes.jsonl").write_text("\n".join(pistes) + "\n")
    envois = []
    assert ri.rendre_retours(j, maintenant=T, envoyer=envois.append) == 1 and "Retour de ton réglage" in envois[0]
    assert ri.rendre_retours(j, maintenant=T, envoyer=envois.append) == 0, "noté : pas deux fois"


def test_il_enregistre_modifie_applique_et_liste_ses_reglages(tmp_path, monkeypatch):
    """(05/11, Ahmed : « il doit aussi pouvoir enregistrer ses réglages et les éditer »)"""
    m = _mcp(tmp_path, monkeypatch)
    j = _maison(tmp_path, profils=[{"nom": "Hakim", "ribosome": {"choix_ms": 1800}, "corps": {"sauter_passe_s": 3}}])
    assert m.reglages_enregistres("enregistrer", "le mien") == "Enregistré sous « le mien »."
    p = [x for x in json.loads((j / "reglages-profils.json").read_text()) if x["nom"] == "le mien"][0]
    assert p["par"] == "hakim" and p["ribosome"]["choix_ms"] == 1800 and "ts" not in p["ribosome"]
    t = m.reglages_enregistres("modifier", "le mien", choix_ms=2100, sauter_passe_s=5)
    assert "choix_ms 2100" in t and "pas appliqué" in t
    assert json.loads((j / "ribosome-reglage.json").read_text())["choix_ms"] == 1800, "modifier n'applique pas"
    t = m.reglages_enregistres("appliquer", "le mien", raison="je l'essaie")
    assert "appliqué" in t and json.loads((j / "ribosome-reglage.json").read_text())["choix_ms"] == 2100
    assert json.loads((j / "corps-reglages.json").read_text())["sauter_passe_s"] == 5
    l = m.reglages_enregistres()
    assert "« le mien » (le tien) : choix_ms 2100" in l and "« Hakim »" in l
    assert "Aucun réglage" in m.reglages_enregistres("appliquer", "inconnu")
    (j / "corps-reglages.json").write_text(json.dumps({"ribosome_intelligent": False}))
    assert "papa n'a pas allumé" in m.reglages_enregistres("modifier", "le mien", choix_ms=1500)
    assert "papa n'a pas allumé" in m.reglages_enregistres("appliquer", "le mien")


def test_papa_peut_lever_sa_priorite(tmp_path):
    j = _maison(tmp_path, corps={"papa_passe_avant": False}, ajustements=[{"ts": T - 60_000, "par": "papa", "cles": ["choix_ms"]}])
    assert ri.ajuster(j, {"choix_ms": 2000}, "essai", maintenant=T)["fait"] == {"choix_ms": [1800, 2000]}


# (06/11, Ahmed : « lui donner tous les boutons ribosomiaux dans les réglages du ribosome intelligent »)
def test_boutons_du_ribosome(tmp_path):
    from jarvis import ribosome_intelligent as ri
    import json as _j
    (tmp_path / "corps-reglages.json").write_text(_j.dumps({"ribosome_intelligent": True, "parole_sans_stop": True}), encoding="utf-8")
    r = ri.ajuster(tmp_path, {"parole_sans_stop": False, "premiere_directe": True, "epissure_meubles_max": 9}, "essai", maintenant=10**13)
    assert r["fait"]["parole_sans_stop"] == [True, False]
    corps = _j.loads((tmp_path / "corps-reglages.json").read_text(encoding="utf-8"))
    rib = _j.loads((tmp_path / "ribosome-reglage.json").read_text(encoding="utf-8"))
    assert corps["parole_sans_stop"] is False and corps["epissure_meubles_max"] == 6 and rib["premiere_directe"] is True
    # une valeur qui n'est pas un oui/non est refusée ; (06/11) tous ses boutons sont à lui, papa_passe_avant compris
    r = ri.ajuster(tmp_path, {"papa_passe_avant": False, "tunnel": "oui"}, "essai", maintenant=10**13)
    assert set(r["refuse"]) == {"tunnel"} and r["fait"]["papa_passe_avant"] == [None, False]
    # « Ribosome intelligent » : il peut l'éteindre ; éteint, il ne règle plus rien (seul papa le rallume)
    assert ri.ajuster(tmp_path, {"ribosome_intelligent": False}, "essai", maintenant=10**13)["fait"]["ribosome_intelligent"] == [True, False]
    assert ri.ajuster(tmp_path, {"ribosome_intelligent": True}, "essai", maintenant=10**13)["eteint"] is True


def test_boutons_papa_passe_avant(tmp_path):
    from jarvis import ribosome_intelligent as ri
    import json as _j
    (tmp_path / "corps-reglages.json").write_text(_j.dumps({}), encoding="utf-8")
    (tmp_path / "ribosome-ajustements.jsonl").write_text(_j.dumps({"ts": 10**13 - 60_000, "par": "papa", "cles": ["tunnel"]}) + "\n", encoding="utf-8")
    r = ri.ajuster(tmp_path, {"tunnel": False}, "essai", maintenant=10**13)
    assert "tunnel" in r["refuse"]


def test_chunk_papa_ms(tmp_path):
    from jarvis import ribosome_intelligent as ri
    import json as _j
    (tmp_path / "corps-reglages.json").write_text(_j.dumps({}), encoding="utf-8")
    r = ri.ajuster(tmp_path, {"chunk_papa_ms": 50}, "ses phrases coupées", maintenant=10**13)
    assert r["fait"]["chunk_papa_ms"] == [None, 200]
    assert _j.loads((tmp_path / "corps-reglages.json").read_text(encoding="utf-8"))["chunk_papa_ms"] == 200


def test_decoupe_papa(tmp_path):
    from jarvis import ribosome_intelligent as ri
    import json as _j
    (tmp_path / "corps-reglages.json").write_text(_j.dumps({}), encoding="utf-8")
    r = ri.ajuster(tmp_path, {"decoupe_papa": "point"}, "ses phrases entières", maintenant=10**13)
    assert r["fait"]["decoupe_papa"] == [None, "point"]
    assert _j.loads((tmp_path / "corps-reglages.json").read_text(encoding="utf-8"))["decoupe_papa"] == "point"
    assert "decoupe_papa" in ri.ajuster(tmp_path, {"decoupe_papa": "mot"}, "", maintenant=10**13)["refuse"]
