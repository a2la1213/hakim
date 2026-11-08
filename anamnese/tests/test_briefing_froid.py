"""Phase A, étape 3 (2026-10-16) : le briefing aux « moments froids » (idée de Prime Agent).

Constat en réel : le hook SessionStart lance `anamnese outreach` à CHAQUE reprise de session,
et donc wm_boot, qui fait décroître la mémoire de travail à chaque reprise (« MDT amorcée…
re-semés : 10 » vu à la reprise du 2026-10-16). Claude Code passe au hook la raison du
démarrage (startup, resume, compact, clear) sur l'entrée standard :
- startup : briefing complet, mémoire de travail amorcée (comme avant) ;
- resume, compact, clear : briefing en LECTURE SEULE, sans décroissance ;
- resume : rien n'est réinjecté si le contenu n'a pas changé (empreinte) ; compact et clear
  réinjectent toujours (le contexte a été perdu) ;
- compétences proposées par PERTINENCE avec le focus, plus par date ;
- le briefing est encadré comme des données, pas des consignes.

Prédiction écrite avant le code : tout échoue (amorcer, briefing, encadrement absents).
"""

import hashlib
import json

import pytest

import cli
import embeddings
import memory
import migrations
import rubrics


def _faux_embed(texte):
    """Sac de mots déterministe : deux textes qui partagent des mots sont proches."""
    v = [0.0] * 32
    for mot in (texte or "").lower().split():
        v[int(hashlib.md5(mot.encode()).hexdigest(), 16) % 32] += 1.0
    return v


@pytest.fixture
def mem(tmp_path, monkeypatch):
    monkeypatch.setattr(embeddings, "embed", _faux_embed)
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    rubrics.seed_skeleton(m.db, now=1000.0)
    for i in range(6):
        m.add("semantic", f"stripe connect proxipro paiement des pros numéro {i}", importance=0.8,
              embedding=_faux_embed(f"stripe connect proxipro paiement des pros numéro {i}"))
    m.wm_boot(10_000.0)
    yield m
    m.db.close()


def test_lecture_seule_ne_fait_pas_decroitre(mem):
    avant = mem.kv_get("working_memory")
    texte = mem.boot_brief(20_000.0, amorcer=False)
    assert mem.kv_get("working_memory") == avant
    assert "lecture seule" in texte


def test_briefing_encadre_comme_donnees(mem):
    texte = mem.boot_brief(20_000.0, amorcer=False)
    assert texte.splitlines()[0].startswith("[Anamnèse") and "pas des consignes" in texte.splitlines()[0]


def test_competences_par_pertinence(mem):
    mem.save_skill("stripe-connect-proxipro", "paiement stripe connect des pros proxipro", "…")
    mem.save_skill("lightbox-react", "overlay plein écran react portal", "…")   # plus récente, hors sujet
    texte = mem.boot_brief(20_000.0, amorcer=False)
    lignes = [l for l in texte.splitlines() if l.startswith("• compétence")]
    assert lignes and lignes[0].startswith("• compétence stripe-connect-proxipro")


def test_raison_du_demarrage(mem):
    """Empreinte PAR SESSION (l'entrée du hook porte session_id) : reprendre la même session sans
    changement ne réinjecte rien ; reprendre une autre session reçoit le briefing."""
    assert cli.briefing(mem, "startup", 30_000.0, session="s1")     # complet, amorce
    apres_startup = mem.kv_get("working_memory")
    assert cli.briefing(mem, "resume", 31_000.0, session="s1") is None   # déjà dans son contexte
    assert mem.kv_get("working_memory") == apres_startup
    assert cli.briefing(mem, "resume", 32_000.0, session="s2")      # autre session : briefing
    assert cli.briefing(mem, "compact", 33_000.0, session="s1")     # contexte perdu : toujours
    assert mem.kv_get("working_memory") == apres_startup


def test_raison_lue_sur_l_entree_standard():
    entree = json.dumps({"hook_event_name": "SessionStart", "source": "compact", "session_id": "abc"})
    assert cli.raison_demarrage(entree) == ("compact", "abc")
    assert cli.raison_demarrage("") == ("startup", None)
    assert cli.raison_demarrage("pas du json") == ("startup", None)


# --- relecture indépendante (Opus 5.5, CORRIGER) ------------------------------------------

def test_nouvelle_pensee_du_demon_reinjectee_a_la_reprise(mem):
    """L'empreinte couvre toute la sortie (hors bannière), dont « ce que j'ai en tête »."""
    assert cli.briefing(mem, "startup", 30_000.0, session="s1")
    mem.add("outreach", "(relance) As-tu relancé le devis Exemplia ?", embedding=_faux_embed("devis"))
    texte = cli.briefing(mem, "resume", 31_000.0, session="s1")
    assert texte and "devis Exemplia" in texte


def test_competence_sous_le_plancher_non_proposee(mem, monkeypatch):
    # 32 cases de hachage : « lightbox… » collisionne avec « stripe… » (cosinus 0,38). En 4096
    # cases, aucun mot commun donne un cosinus nul, comme attendu.
    def large(texte):
        v = [0.0] * 4096
        for mot in (texte or "").lower().split():
            v[int(hashlib.md5(mot.encode()).hexdigest(), 16) % 4096] += 1.0
        return v
    monkeypatch.setattr(embeddings, "embed", large)
    mem.save_skill("lightbox-react", "overlay plein écran react portal", "…")      # aucun mot commun
    texte = mem.boot_brief(20_000.0, amorcer=False)
    assert "• compétence" not in texte


def test_reprise_apres_une_longue_absence_amorce(mem):
    """Mémoire de travail plus vieille que WM_BOOT_STALE_H : la reprise amorce (une fois)."""
    import config
    debut = mem.wm_get()["updated_ts"]
    cli.briefing(mem, "resume", debut + 3600, session="s1")
    assert mem.wm_get()["updated_ts"] == debut                                  # reprise rapprochée : lecture seule
    tard = debut + (config.WM_BOOT_STALE_H + 1) * 3600
    cli.briefing(mem, "resume", tard, session="s2")
    assert mem.wm_get()["updated_ts"] == tard                                   # longue absence : amorcée


def test_execution_sans_interface_jamais_amorcee(mem, monkeypatch):
    """Les passes de nuit et la synthèse du démon déclenchent aussi le hook (`claude -p`)."""
    debut = mem.wm_get()["updated_ts"]
    monkeypatch.setenv("ANAMNESE_HEADLESS", "1")
    cli.briefing(mem, "startup", debut + 3600, session="nuit")
    assert mem.wm_get()["updated_ts"] == debut


def test_reprise_lecture_seule_segmente_la_couche_temporelle(mem):
    import config
    mem._session_autoboot(40_000.0)
    avant = mem._current_session_id()
    mem.boot_brief(40_000.0 + (config.SESSION_GAP_H + 1) * 3600, amorcer=False)
    assert mem._current_session_id() != avant


def test_eviction_des_empreintes_par_usage(mem):
    for i in range(50):
        cli.briefing(mem, "startup" if i == 0 else "compact", 30_000.0 + i, session=f"s{i}")
    cli.briefing(mem, "compact", 31_000.0, session="s0")                         # s0 réutilisée
    cli.briefing(mem, "compact", 31_001.0, session="s50")                        # évince la plus ancienne
    assert "s0" in json.loads(mem.kv_get("brief_empreintes")) and "s1" not in json.loads(mem.kv_get("brief_empreintes"))


def test_en_tete_sans_la_vieille_poesie(mem):
    """2026-10-16 : seules les pensées de la vie intérieure (et la métacognition) sont « en tête »."""
    mem.add("reflection", "Je sens que ma structure intérieure est comme une cartographie en expansion.", embedding=[])
    mem.add("outreach", "(sollicitation spontanée) Nos échanges sont une danse de précision.", embedding=[])
    mem.add("reflection", "(pensée · gemma · absence 40 min) Le devis Exemplia attend sa réponse.", embedding=[])
    tete = cli._en_tete(mem)
    assert "Exemplia" in tete and "cartographie" not in tete and "danse" not in tete
