"""Phase 4c — couche limbique/affiliative (empathie/compassion/mentalizing) + ton daemon.

Ajouts HORS-RAPPEL (Singer-Klimecki, [solide] au niveau RÉSEAU) :
  * scalaires affiliatifs DÉRIVÉS et PURS (pas de nouvelles hormones) ;
  * DISSOCIATION clé : compassion (chaleur + aide) ≠ détresse — la difficulté
    (cortisol/noradrénaline hauts) n'écrase PAS la compassion, canal distinct ;
  * câblage RÉEL du ton compassion dans le PROMPT de daemon.reflect (anti-relance),
    pas de réécriture a posteriori de la sortie du 9B.

Contraintes vérifiées :
  * on NE touche PAS Memory.retrieve (scalaires affiliatifs hors du score de rappel) ;
  * valence/arousal INCHANGÉS par ces ajouts (fonctions dérivées séparées) ;
  * offline total : état injecté (dict/FakeMem RAM), eng/embeddings/notify monkeypatchés,
    jamais data/memory.db.
"""

import inspect

import affect
import config
import daemon


def _state(**over):
    """État complet (9 clés) à partir des baselines, avec surcharges."""
    s = {h: b for h, (b, _) in affect.HORMONES.items()}
    s.update(over)
    return s


class _FakeMem:
    """kv en RAM — pas de DB (respecte la garde conftest)."""

    def __init__(self):
        self._kv = {}

    def kv_get(self, key, default=None):
        return self._kv.get(key, default)

    def kv_set(self, key, value):
        self._kv[key] = value


def _mem_with(**over):
    """FakeMem dont l'état affect vaut _state(**over), horodaté maintenant."""
    m = _FakeMem()
    affect._save(m, _state(**over))
    return m


# ---------------------------------------------------------------------------
#  Cas 1 : scalaires affiliatifs — valeurs correctes, bornés [0,1],
#          compassion monte avec ocytocine ET endorphine.
# ---------------------------------------------------------------------------
def test_scalaires_valeurs_bornes_et_compassion_monte():
    s = _state(ocytocine=0.6, endorphine=0.4, acetylcholine=0.8)
    assert abs(affect.compassion(s) - (0.5 * 0.6 + 0.5 * 0.4)) < 1e-12
    assert abs(affect.empathy(s) - 0.6) < 1e-12
    assert abs(affect.mentalizing(s) - (0.5 * 0.6 + 0.5 * 0.8)) < 1e-12
    # Bornés [0,1] aux extrêmes.
    hi = _state(ocytocine=1.0, endorphine=1.0, acetylcholine=1.0)
    lo = _state(ocytocine=0.0, endorphine=0.0, acetylcholine=0.0)
    for f in (affect.compassion, affect.empathy, affect.mentalizing):
        assert 0.0 <= f(hi) <= 1.0
        assert 0.0 <= f(lo) <= 1.0
    # Compassion monte avec ocytocine ET avec endorphine (chaleur + motivation).
    base = affect.compassion(_state(ocytocine=0.2, endorphine=0.2))
    assert affect.compassion(_state(ocytocine=0.8, endorphine=0.2)) > base
    assert affect.compassion(_state(ocytocine=0.2, endorphine=0.8)) > base


# ---------------------------------------------------------------------------
#  Cas 2 : affiliative_state — 3 clés floats (helper daemon/dashboard).
# ---------------------------------------------------------------------------
def test_affiliative_state_trois_cles_float():
    m = _mem_with(ocytocine=0.5, endorphine=0.5, acetylcholine=0.5)
    aff = affect.affiliative_state(m)
    assert set(aff) == {"empathy", "compassion", "mentalizing"}
    assert all(isinstance(v, float) for v in aff.values())
    assert all(0.0 <= v <= 1.0 for v in aff.values())


# ---------------------------------------------------------------------------
#  Cas 3 : DISSOCIATION — la détresse n'écrase PAS la compassion.
#  (Singer-Klimecki : conversion détresse→compassion = résilience, canal distinct.)
# ---------------------------------------------------------------------------
def test_dissociation_compassion_distincte_de_detresse():
    detresse = _state(cortisol=0.95, noradrenaline=0.95, ocytocine=0.6, endorphine=0.6)
    calme = _state(cortisol=0.10, noradrenaline=0.10, ocytocine=0.6, endorphine=0.6)
    # Aucun couplage détresse→compassion=0 : mêmes ocytocine/endorphine ⇒ même compassion.
    assert affect.compassion(detresse) == affect.compassion(calme)
    # La compassion reste un canal chaleureux malgré la forte difficulté.
    assert affect.compassion(detresse) >= 0.5


# ---------------------------------------------------------------------------
#  Cas 4 : TON daemon — reflect construit un PROMPT contenant la consigne de
#  registre chaleureux/anti-relance (assertion sur la string, PAS sur la sortie
#  du 9B). Garde-fous reflect intacts (persona, ligne PROACTIF).
# ---------------------------------------------------------------------------
class _CapEng:
    """Engine factice : health()=True, chat() capture le prompt et renvoie une réponse fixe."""

    def __init__(self, reply="Une pensée neuve et unique.\nPROACTIF: non"):
        self.reply = reply
        self.prompts = []

    def health(self):
        return True

    def chat(self, messages, stream=True, think=False):
        self.prompts.append(messages[0]["content"])
        return self.reply


class _EmptyResult:
    def fetchall(self):
        return []

    def fetchone(self):
        return None


class _FakeDB:
    def execute(self, *a, **k):
        return _EmptyResult()


class _DaemonMem(_FakeMem):
    """FakeMem + .db + .add (surface utilisée par reflect), sans aucune I/O."""

    def __init__(self):
        super().__init__()
        self.db = _FakeDB()
        self.added = []

    def add(self, role, content, importance=0.5, embedding=None):
        self.added.append((role, content, importance, embedding))


def test_reflect_prompt_ton_compassion_anti_relance(monkeypatch):
    monkeypatch.setattr(daemon.embeddings, "embed", lambda t: [])
    monkeypatch.setattr(daemon, "notify", lambda *a, **k: None)
    mem = _DaemonMem()
    # État chaleureux (ocytocine/endorphine hauts) → compassion élevée.
    affect._save(mem, _state(ocytocine=0.7, endorphine=0.6))
    eng = _CapEng()
    daemon.reflect(eng, mem)
    assert eng.prompts, "reflect doit appeler eng.chat avec un prompt"
    p = eng.prompts[0]
    low = p.lower()
    # Registre chaleureux + anti-relance CÂBLÉ dans le prompt (le vrai fix).
    assert "chaleureux" in low
    assert "pressant" in low                       # « jamais pressant »
    assert "une seule sollicitation" in low        # une relance douce maximum
    # Garde-fous reflect intacts : persona ancrée + ligne PROACTIF conservée.
    assert config.PERSONA in p
    assert "PROACTIF" in p


# ---------------------------------------------------------------------------
#  Cas 5 : HORS-RAPPEL — memory.py n'importe pas les scalaires affiliatifs
#  (hors du score de rappel) ; valence/arousal STRICTEMENT inchangés.
# ---------------------------------------------------------------------------
def test_hors_rappel_memory_intact_et_valence_inchangee():
    import memory

    src = inspect.getsource(memory)
    for fn in ("compassion", "empathy", "mentalizing", "affiliative_state"):
        assert fn not in src, f"'{fn}' ne doit PAS entrer dans memory.py (hors-rappel)"
    # valence/arousal : formule INCHANGÉE (mêmes valeurs qu'attendu).
    s = _state(dopamine=0.7, endorphine=0.5, serotonine=0.6,
               cortisol=0.7, noradrenaline=0.4, acetylcholine=0.5, ocytocine=0.9)
    v, a = affect.valence_arousal(s)
    liking = (s["dopamine"] + s["endorphine"] + s["serotonine"]) / 3.0
    exp_v = max(-1.0, min(1.0, liking - max(0.0, s["cortisol"] - 0.5)))
    exp_a = min(1.0, (s["noradrenaline"] + 0.6 * s["dopamine"]
                      + 0.5 * s["acetylcholine"] + 0.4 * s["cortisol"]) / 2.5)
    assert abs(v - exp_v) < 1e-12
    assert abs(a - exp_a) < 1e-12
