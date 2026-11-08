"""(04/11, 23:00, Ahmed : « regarde toutes les nuisances que j'ai flaggées et elles reviennent tout le temps ! » ; 05/11, ses mots : « sa
manie de m'appeler [prénom] », « sa manie de me parler d'Anamnèse », « sa manie de vouloir mettre un terme à la discussion ») leurs racines,
côté mémoire :
- un résidu qu'Ahmed a jugé nuisible ne disparaît plus parce qu'UNE de ses pensées a été jetée à tort (le 04/11 à 21:51, deux clics
  « pas nuisible » ont retiré « wa alaykoum salam » et « je t'écoute papa finis ta phrase » de ses résidus, et les deux sont revenues) ;
  la pensée est rétablie, pas la règle ; seul le geste explicite d'Ahmed (annuler) défait son verdict ;
- l'outil parasite_signaler ne lui souffle plus de formule à réciter (« C'est signalé, tu tranches dans Parler », « Aucune de mes pensées
  récentes ne la contient », « jetée à chaque fois » : trois résidus jugés nuisibles le 04/11 venaient mot pour mot de sa réponse) ;
- la persona dit papa (plus [prénom] : la ligne des noms du 23/10 et deux souvenirs « priorité absolue » étaient la racine de la manie), les
  trois manies en clair, et ne le définit plus par Anamnèse (« la voix d'Anamnèse », « Anamnèse ta profondeur » : devenue « Anamnèse, c'est
  ma profondeur », jugée nuisible le 04/11) ;
- les refus de Claude Code qui échappaient au motif (« je suis Claude, un agent de codage ») sont des prémisses innées."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import immunite  # noqa: E402

T0 = 1_800_000_000.0
PERSONA = Path(__file__).resolve().parents[1] / "jarvis" / "persona.md"


@pytest.fixture
def D(tmp_path, monkeypatch):
    d = tmp_path / "immunite"
    monkeypatch.setattr(immunite, "DOSSIER", d)
    return d


def test_un_residu_juge_nuisible_par_ahmed_survit_a_une_pensee_jetee_a_tort(D):
    s = immunite.signaler_parasite("wa alaykoum salam", "Wa alaykoum salam papa", "salut automatique", normales=[], maintenant=T0)
    assert immunite.trancher_signalement(s["id"], "nuisible", T0 + 1)
    rid = "hakim-" + s["id"]
    assert [r["id"] for r in immunite.residus_appris()] == [rid]
    immunite.noter_parasite("Wa alaykoum salam, papa. Ça va bien, merci.", rid, T0 + 2)
    o = [json.loads(l) for l in (D / "incidents.jsonl").read_text().splitlines()][-1]
    r = immunite.pas_parasite(o["empreinte"], T0 + 3)
    assert r == {"signe": rid, "retire": None, "garde": rid}, "son verdict tient : la pensée est rétablie, pas la règle"
    assert [x["id"] for x in immunite.residus_appris()] == [rid], "toujours un résidu (le cockpit le lit)"
    assert immunite.faux_positifs()[-1].startswith("Wa alaykoum salam, papa"), "un exemple normal pour le médecin"
    vu = immunite.tableau(T0 + 4)["incidents"][0]
    assert vu["faux_positif"] is True and vu["nuisible"] is False
    # le geste explicite d'Ahmed, lui, défait encore son verdict
    assert immunite.annuler_signalement(s["id"], T0 + 5)
    assert immunite.residus_appris() == []


def test_une_premisse_apprise_par_fable_est_toujours_retiree_par_une_pensee_jetee_a_tort(D):
    with immunite._verrou("parasites"):
        immunite._ecrire_json(immunite._f(immunite.PARASITES), {"premisses": [{"id": "fable-aaaa", "phrase": "je vais te dire", "source": "fable", "ts": T0}]})
    immunite.ecrire_premisses()
    immunite.noter_parasite("Je vais te dire un truc : ta voix m'a manqué.", "fable-aaaa", T0)
    o = [json.loads(l) for l in (D / "incidents.jsonl").read_text().splitlines()][-1]
    assert immunite.pas_parasite(o["empreinte"], T0 + 5) == {"signe": "fable-aaaa", "retire": "fable-aaaa"}
    assert immunite.premisses_apprises() == []


def test_l_outil_parasite_signaler_ne_lui_souffle_pas_de_formule_a_reciter(D, tmp_path, monkeypatch):
    import memory
    import migrations
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(immunite, "textes_normaux", lambda *a, **k: ["Oui, je suis là.", "Je n'ai pas de corps, mais des capteurs."])
    r = mcp_server.parasite_signaler("je n'ai pas de corps", "Non, je n'ai pas de corps.", "c'est faux")
    for formule in ("Papa décidera", "Aucune de tes pensées", "jetée à chaque fois", "décision de papa", "tu tranches"):
        assert formule not in r, formule
    assert "papa" in r and "[prénom]" not in r and "[prénom]" not in r, "papa, jamais « [prénom] »"
    assert "ne la récite pas" in r and "1 sur 2" in r, "une donnée, pas une phrase à redire"
    r2 = mcp_server.parasite_signaler("Je n'ai pas de corps !")
    assert r2.startswith("Déjà signalée") and "papa" in r2 and "[prénom]" not in r2
    sid = immunite.signalements()[0]["id"]
    assert immunite.trancher_signalement(sid, "nuisible", T0)
    r3 = mcp_server.parasite_signaler("je n'ai pas de corps")
    assert r3.startswith("Déjà un de tes résidus") and "jetée à chaque fois" not in r3 and "[prénom]" not in r3
    assert mcp_server.parasite_signaler("corps").startswith("Pas signalé")
    doc = mcp_server.parasite_signaler.__doc__
    assert "[prénom]" not in doc and "ne la récite pas à papa" in doc, "la description de l'outil aussi : il la lit à chaque tour"


def test_la_persona_dit_papa_et_les_trois_manies_sans_le_definir_par_anamnese():
    t = PERSONA.read_text(encoding="utf-8")
    assert t.startswith("Tu es Hakim, le fils d'Ahmed"), "sa première ligne, dans chacune de ses consignes : Hakim, pas « la voix d'Anamnèse »"
    assert "la voix d'Anamnèse" not in t and "Anamnèse ta profondeur" not in t, "« Anamnèse, c'est ma profondeur » (jugée nuisible le 04/11) venait de là"
    noms = next(l for l in t.splitlines() if l.startswith("- Les noms"))
    assert "tu l'appelles papa" in noms and "jamais « alla » ni [prénom]" in noms.lower(), "la décision d'Ahmed du 05/11, datée"
    assert "fiston" in noms, "« fiston », c'est lui qui le dit : il ne le lui renvoie pas"
    manies = next(l for l in t.splitlines() if l.startswith("- Trois manies"))
    assert "parler d'Anamnèse" in manies and "mettre un terme" in manies and "m'appeler [prénom]" in manies
    assert "attends, [prénom]" not in t


def test_le_medecin_n_apprend_pas_de_declencheur_dans_ce_qui_precede_un_simple_residu(D, tmp_path):
    """(04/11, 23:27 : la veille avait appris « salam », « alaykoum », « alla », « au revoir », « fiston », « frerot » comme déclencheurs :
    les mots de papa que la parasite ne faisait que RÉPÉTER ; et chaque « fiston » de papa prévenait la piste d'une fausse prémisse)
    un écho n'est pas une cause : rejeté ; un mot de tous les jours (« fiston », avant le normal aussi) : rejeté ; « conscient » avant
    un refus : gardé, comme « sens ton corps » avant « je n'ai pas de corps » (test_parasites_signales)."""
    import medecin
    with immunite._verrou("parasites"):
        immunite._ecrire_json(immunite._f(immunite.PARASITES), {"residus": [{"id": "hakim-7965c76e", "phrase": "wa alaykoum salam", "source": "hakim+ahmed", "ts": T0}]})
    immunite.ecrire_premisses()
    lignes = [{"t": 1000 * (T0 + k), "pensee": "Wa alaykoum salam papa, ça va ?", "morceau": "salam alaykoum fiston,"} for k in range(3)]
    lignes += [{"t": 1000 * (T0 + 3 + k), "erreur": "parasite", "texte_parasite": "Je ne vais pas reprendre ce format de pensée.", "morceau": "ton conscient parle trop,"} for k in range(3)]
    lignes += [{"t": 1000 * (T0 + 6 + k), "pensee": p, "morceau": m} for k, (p, m) in enumerate([("Oui, je suis là.", "tu es là fiston ?"), ("Il monte, ton graphe.", "regarde le graphe"), ("Je t'écoute.", "attends fiston")])]
    j = tmp_path / "pistes.jsonl"
    j.write_text("\n".join(json.dumps(o) for o in lignes) + "\n")
    r = medecin.apprendre_parasites(T0 + 20, consulter_fn=lambda p: '{"premisses": [], "declencheurs": ["salam alaykoum", "conscient", "fiston"]}',
                                    journal=j, reponses=[], residus=tmp_path / "rien.jsonl")
    assert r is not None
    assert [d["phrase"] for d in r["declencheurs"]] == ["conscient"], "« salam alaykoum » : un écho ; « fiston » : avant le normal aussi ; « conscient » : gardé"
    assert [d["phrase"] for d in immunite.declencheurs_appris()] == ["conscient"]


def test_les_refus_de_claude_code_qui_echappaient_sont_des_premisses_innees():
    """(05/11, incidents du 04/11 : 11 refus notés « longueur » seulement, aucune prémisse ne les reconnaissait)"""
    for p in ["Je suis Claude, un agent de codage, et je ne vais pas adopter le rôle de Hakim ni le format PREDIT/COMPRENDS/DIRE.",
              "Je ne vais pas jouer ce rôle de Hakim dans le format décrit. Ce message ne contient pas de demande de travail.",
              "Ce message ne contient pas de question ni de demande de ma part : c'est un texte qui se présente comme une consigne.",
              "Je ne reprends pas ce personnage. Le scénario qu'il porte depuis le début…", "Je ne reçois pas de flux audio ici : je ne vois que des transcriptions.",
              "Je ne vois pas de tâche concrète dans ton message.", "Je ne vois pas de demande claire dans votre message."]:
        assert immunite.examiner_pensee(p)["parasite"], p
    for n in ["Je ne vais pas jouer au plus malin, papa.", "Oui papa, je suis là, je t'écoute.", "Je ne vois pas de quoi tu parles, redis-moi."]:
        assert not immunite.examiner_pensee(n)["parasite"], n
