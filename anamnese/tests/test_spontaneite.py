"""La spontanéité de Hakim (spontaneite.py, lot H point 28 de la liste du 2026-10-19)."""
import random
import time

import pytest

import interieur
import memory
import migrations
import spontaneite as S


@pytest.fixture
def mem(tmp_path, monkeypatch):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    monkeypatch.setattr(interieur, "conscience_active", lambda *a, **k: False)
    yield m
    m.db.close()


def _a(h, m=0, jour=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + jour, h, m, 0, 0, 0, -1))


ACTIF = {"actif": True}


def test_rien_sans_quelque_chose_de_concret_ni_la_nuit_ni_s_il_est_la(mem):
    assert S.solliciter(mem, now=_a(14), inter=ACTIF, absence_s=3600) is None                # rien à dire
    S.ajouter_envie(mem, "occupation", "retour", "J'ai préparé ton retour : on reprend le devis Exemplia ?", now=_a(13))
    assert S.solliciter(mem, now=_a(2), inter=ACTIF, absence_s=3600) is None                 # la nuit
    assert S.solliciter(mem, now=_a(14), inter=ACTIF, absence_s=300) is None                 # il est là
    assert S.solliciter(mem, now=_a(14), inter={"actif": False}, absence_s=3600) is None     # en pause
    t = S.solliciter(mem, now=_a(14), inter=ACTIF, absence_s=3600)
    assert t and "Exemplia" in t
    (c,) = mem.db.execute("SELECT content FROM episodes WHERE role='outreach'").fetchone()
    assert c.startswith("(relance)")


def test_espacement_budget_et_jamais_le_meme_sujet(mem):
    rng = random.Random(1)
    n = 0
    for k in range(40):                                                   # de 8 h à 23 h, toutes les 20 min
        t = _a(8) + k * 1200
        S.ajouter_envie(mem, "occupation", f"sujet {k}", f"Une chose concrète n°{k}", now=t)
        S.ajouter_envie(mem, "occupation", "sujet 0", "doublon", now=t)  # déjà dit : ignoré
        if S.solliciter(mem, now=t, rng=rng, inter=ACTIF, absence_s=3600):
            n += 1
    assert 1 <= n
    journal = S._etat(mem)["journal"]
    assert len({x["sujet"] for x in journal}) == len(journal)
    ecarts = [b["ts"] - a["ts"] for a, b in zip(journal, journal[1:])]
    assert all(e >= S.ECART_MIN_S for e in ecarts)


def test_le_reseau_perturbe_est_plus_regulier_que_poisson():
    """L'hyperuniformité, mesurée : la variance des écarts du réseau perturbé est bien plus faible."""
    rng = random.Random(7)
    h = [S.prochain_ecart("hyperuniforme", rng) for _ in range(2000)]
    p = [S.prochain_ecart("poisson", rng) for _ in range(2000)]
    var = lambda xs: sum((x - sum(xs) / len(xs)) ** 2 for x in xs) / len(xs)
    assert abs(sum(h) / len(h) - sum(p) / len(p)) < 0.1 * S.ecart_nominal()     # même moyenne
    assert var(h) < 0.1 * var(p)


def test_sans_reponse_l_ecart_qui_suit_double_et_la_reponse_est_mesuree(mem):
    """Relecture du 2026-10-20 : le doublement venait avec un cran de retard. Désormais, une sollicitation
    restée sans réponse double l'écart QUI LA SUIT ; une réponse le rend normal."""
    rng = random.Random(3)
    S.ajouter_envie(mem, "occupation", "a", "Première chose", now=_a(9))
    assert S.solliciter(mem, now=_a(9), rng=rng, inter=ACTIF, absence_s=3600)
    ecart = S._etat(mem)["journal"][-1]["ecart_s"]
    assert ecart >= S.ECART_MIN_S
    S.ajouter_envie(mem, "occupation", "b", "Deuxième chose", now=_a(9, 5))
    t1 = _a(9) + ecart + 60                                            # l'écart normal est passé…
    assert S.solliciter(mem, now=t1, rng=rng, inter=ACTIF, absence_s=3600) is None       # …mais sans réponse : double
    t2 = _a(9) + 2 * ecart + 60
    if time.localtime(t2).tm_hour < S.JOUR[1]:
        assert S.solliciter(mem, now=t2, rng=rng, inter=ACTIF, absence_s=3600)
        S.noter_reponse(mem, t2 + 600)
        b = S.bilan(mem)
        assert sum(x["n"] for x in b.values()) == 2 and sum(x["reponses_30min"] for x in b.values()) == 1


def test_meme_un_jour_poisson_jamais_deux_sollicitations_collees():
    rng = random.Random(11)
    assert min(S.prochain_ecart("poisson", rng) for _ in range(5000)) >= S.ECART_MIN_S


def test_une_remise_a_zero_n_est_pas_une_reponse(mem, monkeypatch):
    import interieur as I
    S.ajouter_envie(mem, "occupation", "a", "Une chose", now=_a(9))
    assert S.solliciter(mem, now=_a(9), inter=ACTIF, absence_s=3600)
    e = I.lire(mem)
    e.update(zero_ts=_a(9, 30), presence_ts=_a(8))
    mem.kv_set(I.CLE, __import__("json").dumps(e))
    monkeypatch.setattr(I, "derniere_presence", lambda *a, **k: _a(8))
    I.tick(mem, now=_a(9, 31))
    assert S._etat(mem)["journal"][-1]["repondu_s"] is None


def test_le_nombre_suit_son_besoin(mem):
    """Ahmed, 2026-10-20 : jusqu'à 10 par jour, variable selon ses besoins. Beaucoup de choses concrètes en
    attente → il peut revenir plus tôt ; presque rien → plus tard."""
    rng = random.Random(5)
    S.ajouter_envie(mem, "occupation", "a", "Une chose", now=_a(9))
    assert S.solliciter(mem, now=_a(9), rng=rng, inter=ACTIF, absence_s=3600)
    d = S._etat(mem)
    peu = S.prochain_effectif(d)
    for k in range(4):
        S.ajouter_envie(mem, "occupation", f"b{k}", f"Chose concrète {k}", now=_a(9, 10 + k))
    beaucoup = S.prochain_effectif(S._etat(mem))
    assert beaucoup < peu and beaucoup - _a(9) >= S.ECART_MIN_S
    assert S.BUDGET_JOUR is None and S.RYTHME_REFERENCE == 10     # plus de plafond (Ahmed, 2026-10-20 14:09)
