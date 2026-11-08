"""Identité en deux couches : le cœur n'est jamais coupé (2026-10-15).

Bug prouvé : quand self_model dépassait DREAM_SELF_MODEL_MAX, _maybe_update_self gardait
old[:200] + " … " + la fin, puis ajoutait la phrase du 9B. L'identité écrite par Claude le
1er juillet (2 501 caractères) a été amputée au premier ajout, puis rongée par les suivants.

Règles (identity.py) :
- le CŒUR (validé par Ahmed) n'est modifié que par set_core ; jamais par un ajout ;
- l'ÉVOLUTION est une liste bornée de phrases : au-delà de EVOLUTION_MAX, c'est la plus
  ancienne phrase d'évolution qui sort, jamais le cœur ;
- self_model = assemblage(cœur, évolution), pour les lecteurs existants.

Prédiction écrite avant le module : tous ces tests échouent à l'import (identity absent),
sauf qu'aucun ne doit passer par hasard.
"""

import config
import daemon
import identity


class _FakeMem:
    """kv + add en RAM — pas de DB (respecte la garde conftest)."""

    def __init__(self, self_model=None):
        self._kv = {} if self_model is None else {"self_model": self_model}
        self.added = []

    def kv_get(self, key, default=None):
        return self._kv.get(key, default)

    def kv_set(self, key, value):
        self._kv[key] = value

    def add(self, role, content, **kw):
        self.added.append((role, content))


JOUR = 86400.0


def _coeur(n_chars):
    """Cœur factice sans recouvrement lexical avec les phrases de test."""
    base = "Anamnèse, mémoire persistante créée par Ahmed. "
    mots = " ".join(f"valeur{i:04d}" for i in range(400))
    return (base + mots)[:n_chars].rstrip()


def _phrase(i):
    """Phrase à la 1re personne, lexicalement distincte pour chaque i."""
    return f"Je contemple lumiere{i}x rivage{i}x silence{i}x horizon{i}x."


def _sortie(phrase):
    return f"###IDENTITE###\n- {phrase}\n###FIN###"


def _sans_embedding(monkeypatch):
    monkeypatch.setattr(daemon.embeddings, "embed", lambda t: [0.0])


def test_migration_prend_self_model_comme_coeur():
    mem = _FakeMem(_coeur(500))
    assert identity.core(mem) == _coeur(500)
    assert identity.evolution(mem) == []


def test_ajout_assemble_coeur_puis_evolution():
    mem = _FakeMem(_coeur(300))
    ok, _ = identity.append(mem, _phrase(1))
    assert ok
    assert mem.kv_get("self_model") == identity.assemble(_coeur(300), [_phrase(1)])
    assert mem.kv_get("self_model").startswith(_coeur(300))
    assert mem.kv_get("self_model_prev") == _coeur(300)


def test_coeur_long_jamais_coupe():
    """Un cœur plus long que l'ancien plafond (cas réel : 2 501 caractères) reste intact."""
    coeur = _coeur(2500)
    mem = _FakeMem(coeur)
    for i in range(identity.EVOLUTION_MAX + 5):
        identity.append(mem, _phrase(i), now=i * JOUR)
    texte = mem.kv_get("self_model")
    assert texte.startswith(coeur)
    assert " … " not in texte
    assert identity.core(mem) == coeur


def test_evolution_bornee_la_plus_ancienne_sort():
    mem = _FakeMem(_coeur(300))
    for i in range(identity.EVOLUTION_MAX + 2):
        assert identity.append(mem, _phrase(i), now=i * JOUR)[0]
    evo = identity.evolution(mem)
    assert len(evo) == identity.EVOLUTION_MAX
    assert evo[0] == _phrase(2) and evo[-1] == _phrase(identity.EVOLUTION_MAX + 1)


def test_refus_ne_touche_a_rien():
    mem = _FakeMem(_coeur(300))
    avant = dict(mem._kv)
    assert identity.append(mem, "trop court")[0] is False                    # pas de 1re personne
    assert identity.append(mem, "Je " + "x" * config.DREAM_SELF_ADD_MAX)[0] is False  # trop long
    bloque = config.DREAM_IDENTITY_BLOCKLIST[0]
    assert identity.append(mem, f"Je pense que {bloque} vraiment.")[0] is False
    assert identity.append(mem, "Je suis " + _coeur(120))[0] is False        # quasi-doublon
    assert mem._kv == avant


def test_set_core_remplace_le_coeur_garde_l_evolution():
    mem = _FakeMem(_coeur(300))
    identity.append(mem, _phrase(1))
    avant = mem.kv_get("self_model")
    identity.set_core(mem, "Je suis Anamnèse, coeur restauré.", force=True)
    assert identity.core(mem) == "Je suis Anamnèse, coeur restauré."
    assert identity.evolution(mem) == [_phrase(1)]
    assert mem.kv_get("self_model_prev") == avant


def test_demon_passe_par_l_evolution(monkeypatch):
    _sans_embedding(monkeypatch)
    coeur = _coeur(config.DREAM_SELF_MODEL_MAX)        # ancien plafond atteint
    mem = _FakeMem(coeur)
    assert daemon._maybe_update_self(mem, coeur, _sortie(_phrase(7))) is True
    assert mem.kv_get("self_model").startswith(coeur)
    # (X1, 2026-10-20) le rêve local PROPOSE : rien n'entre avant la décision d'Ahmed
    assert identity.evolution(mem) == []
    (p,) = identity.propositions(mem)
    assert p["texte"] == _phrase(7) and p["origine"] == "rêve local"
    assert identity.trancher(mem, p["id"], True)[0]
    assert identity.evolution(mem) == [_phrase(7)]
    assert mem.added and mem.added[0][0] == "dream"


def test_demon_refus_sans_trace(monkeypatch):
    _sans_embedding(monkeypatch)
    mem = _FakeMem(_coeur(300))
    assert daemon._maybe_update_self(mem, _coeur(300), _sortie("pas de premiere personne ici")) is False
    assert mem.added == []


# --- relecture indépendante du 2026-10-15 (constats 3, 5, 6, 9) ---

def test_une_phrase_par_intervalle(monkeypatch):
    mem = _FakeMem(_coeur(300))
    assert identity.append(mem, _phrase(1), now=1000.0)[0]
    ok, raison = identity.append(mem, _phrase(2), now=1000.0 + 3600)
    assert not ok and "h" in raison
    assert identity.append(mem, _phrase(2), now=1000.0 + identity.EVOLUTION_INTERVALLE_S)[0]


def test_set_core_refuse_vide_et_retrecissement():
    mem = _FakeMem(_coeur(1000))
    assert identity.set_core(mem, "   ")[0] is False
    assert identity.set_core(mem, _coeur(400))[0] is False          # < 60 % du cœur
    assert identity.core(mem) == _coeur(1000)
    assert identity.set_core(mem, _coeur(400), force=True)[0] is True
    assert identity.core(mem) == _coeur(400)


def test_historique_des_coeurs_survit_aux_ajouts():
    mem = _FakeMem(_coeur(1000))
    identity.set_core(mem, _coeur(900), force=True)
    for i in range(3):
        identity.append(mem, _phrase(i), now=i * JOUR)
    assert identity.historique_coeurs(mem)[-1] == _coeur(1000)
    for k in range(identity.HISTORIQUE_MAX + 2):
        identity.set_core(mem, f"Je suis Anamnèse, version {k} " + _coeur(900), force=True)
    assert len(identity.historique_coeurs(mem)) == identity.HISTORIQUE_MAX


def test_ecriture_atomique_sur_vraie_base(tmp_path, monkeypatch):
    import sqlite3
    from memory import Memory
    mem = Memory(db_path=tmp_path / "m.db")
    mem.kv_set("self_model", _coeur(500))
    appels = {"n": 0}
    vrai = identity._set

    def casse_a_la_troisieme(m, cle, valeur):        # 2 écritures réelles, puis panne
        appels["n"] += 1
        if appels["n"] == 3:
            raise RuntimeError("panne simulée au milieu de l'écriture")
        return vrai(m, cle, valeur)

    monkeypatch.setattr(identity, "_set", casse_a_la_troisieme)
    try:
        identity.append(mem, _phrase(1), now=1.0)
    except RuntimeError:
        pass
    monkeypatch.setattr(identity, "_set", vrai)
    assert appels["n"] == 3
    autre = sqlite3.connect(str(tmp_path / "m.db"))
    cles = dict(autre.execute("SELECT key, value FROM kv").fetchall())
    autre.close()
    assert cles == {"self_model": _coeur(500)}                       # rien d'écrit à moitié
    assert identity.append(mem, _phrase(1), now=2.0)[0]
    assert identity.evolution(mem) == [_phrase(1)]
