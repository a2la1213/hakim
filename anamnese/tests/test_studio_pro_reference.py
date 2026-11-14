"""Le calage d'une voix sur une voix de RÉFÉRENCE (14/11, Ahmed : « j'aimerais juste que les mix [de ma voix] soient aussi bien que sa
voix », la voix de Hakim). Un banc à VÉRITÉ CONNUE : des voix de synthèse (un chant, un rap avec ses sifflantes), colorées par des
courbes connues (un micro, une pièce), des sifflantes renforcées, une réverbération connue ; le calage doit retirer ce qui a été ajouté,
ne pas toucher une voix propre, et ne pas prendre la HAUTEUR d'une voix (la personne) pour une couleur. Chaque mécanisme a son TÉMOIN :
le même test, le mécanisme coupé (STUDIO_PRO_COUPE=<nom>), doit échouer. (Le banc sur les vraies voix : studio_pro_banc.banc_reference.)"""
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "jarvis"))
import studio  # noqa: E402
import studio_mesures as M  # noqa: E402
import studio_pro as P  # noqa: E402
import studio_pro_banc as B  # noqa: E402
import studio_pro_reference as R  # noqa: E402
import studio_projet as SP  # noqa: E402

P.COUPE = frozenset(x for x in os.environ.get("STUDIO_PRO_COUPE", "").split(",") if x)
pytestmark = pytest.mark.skipif(not Path(studio.FFMPEG).exists(), reason="ffmpeg absent")
SR = 44100
TI = np.array(R.TIERS, float)


@pytest.fixture(scope="module")
def chant():
    return B.voix_chantee(16.0)


@pytest.fixture(scope="module")
def chant_aigu():
    """Le même conduit vocal (les mêmes formants), une octave plus haut : une autre hauteur, pas une autre couleur."""
    return B.voix_chantee(16.0, homme=False, graine=5)


@pytest.fixture(scope="module")
def rap():
    return B.voix_rappee(16.0)


def _vraie(courbe):
    return [-float(courbe(np.array([c]))[0]) for c in TI]


def _micro_piece(f):
    return B.courbe_micro(f) + B.courbe_piece(f)


# ------------------------------------------------------------------------------------------------ A. la mesure
def test_la_hauteur_suivie(chant, rap):
    """YIN : la fondamentale médiane d'un chant (notes de 98 à 196 Hz) et d'un rap (135 à 175 Hz) à 5 % près."""
    h = R.hauteur(P._mono(chant[0]))
    assert 130 <= h["f0_hz"] <= 160 and h["voise"] > 0.4, h
    h = R.hauteur(P._mono(rap[0]))
    assert 145 <= h["f0_hz"] <= 170, h


def test_l_enveloppe_ne_prend_pas_la_hauteur_pour_une_couleur(chant, chant_aigu):
    """Le même conduit vocal chanté une octave plus haut : son spectre moyen diffère de plus de 15 dB sous 200 Hz (la fondamentale de
    chacun), son ENVELOPPE à 1,5 dB en moyenne (4,5 au pire) de 250 Hz à 5 kHz ; au-dessus de 630 Hz (là où le spectre moyen ne dépend plus de la
    hauteur), l'enveloppe dit la même chose que lui à 1,5 dB près ; la courbe d'appariement reste sous 2,5 dB jusqu'à 5 kHz (rien à
    corriger : c'est la personne) et ne touche à rien sous 160 Hz. Témoin « ref_enveloppe » (le spectre moyen : la courbe creuserait la
    fondamentale)."""
    a, b = R.profil(chant[0]), R.profil(chant_aigu[0])
    lt = np.array(a["tiers_db"]) - np.array(b["tiers_db"])
    assert np.abs(lt[TI < 200]).max() > 15
    ea = np.array([np.nan if v is None else v for v in a["enveloppe"]["tiers_db"]], float)
    eb = np.array([np.nan if v is None else v for v in b["enveloppe"]["tiers_db"]], float)
    sel = (TI >= 250) & (TI <= 5000) & ~np.isnan(ea) & ~np.isnan(eb)
    d = (ea - eb)[sel]
    assert sel.sum() >= 10 and np.abs(d - d.mean()).mean() <= 1.5 and np.abs(d - d.mean()).max() <= 4.5, d
    haut = (TI >= 630) & (TI <= 8000) & ~np.isnan(ea) & ~np.isnan(eb)
    e = (ea - eb)[haut] - lt[haut]
    assert np.abs(e - e.mean()).max() <= 1.5, e
    c = np.array(R.courbe_appariement(a, b))
    assert np.abs(c[TI <= 5000]).max() <= 2.5 and np.abs(c[TI < 160]).max() == 0.0 and abs(c[TI == 160][0]) <= 1.0, c


def test_la_traine_se_mesure_aux_fins_seches(chant):
    """Une réverbération connue (T60 1,5 s) de plus en plus forte : la traîne mesurée aux fins de phrase de la voix SÈCHE monte à chaque
    pas, et la T60 apparente retrouve 1,5 s à 20 % près. Témoin « ref_fins_seches » (les fins cherchées dans la voix mouillée : la
    réverbération forte les cache)."""
    x, _ = chant
    m = P._mono(x)
    fins = R.fins_de_phrase(m)[1]
    rng = np.random.default_rng(1)
    n = int(SR * 1.8)
    ir = rng.standard_normal(n) * 10 ** (-3 * (np.arange(n) / SR) / 1.5)
    ir /= np.sqrt((ir ** 2).sum())
    w = np.convolve(m, ir)[: len(m)]
    w *= np.sqrt((m ** 2).sum() / (w ** 2).sum())
    tr = []
    for g in (0.0, 0.3, 0.6, 1.2):
        r = R.reverberation(m + g * w, fins=fins)
        tr.append(r["traine_db"])
        if g == 0.6:
            assert 1.2 <= r["t60_apparente_s"] <= 1.8, r
    assert all(t is not None for t in tr) and all(b >= a + 3 for a, b in zip(tr, tr[1:])), tr


def test_une_fin_de_phrase_est_une_pause_pas_un_trou_entre_deux_syllabes(rap):
    """Un rap : les fins trouvées sont les vraies fins de phrase (le dernier son de chaque phrase, à 60 ms près), pas les trous entre les
    syllabes. Témoin « ref_pause »."""
    x, ph = rap
    m = P._mono(x)
    l = P.niveaux_db(m, SR, 0.005, 0.005)
    vraies = []
    for a, b in ph:                                      # le dernier instant de la phrase à moins de 20 dB de son maximum
        i0, i1 = int(a / 0.005), min(len(l), int((b + 0.1) / 0.005))
        seg = l[i0:i1]
        vraies.append((i0 + int(np.flatnonzero(seg >= seg.max() - 20)[-1])) * 0.005)
    fins = [i * 0.005 for i in R.fins_de_phrase(m)[1]]
    assert len(fins) >= len(ph) - 1
    for f in fins:
        assert min(abs(f - v) for v in vraies) <= 0.06, (f, vraies)


# ------------------------------------------------------------------------------------------------ B. l'égalisation d'appariement
def test_une_couleur_connue_est_retiree(chant):
    """Un chant passé dans un micro et une pièce connus (présence creusée, aigus en trop, boue à 400 Hz) puis calé sur sa propre voix
    propre : la courbe appliquée suit la vraie correction à 0,6 dB près (2,8 dB sans calage) et le SI-SDR remonte d'au moins 10 dB.
    Témoin « ref_egaliseur »."""
    x, _ = chant
    deg = B.colorer(x, _micro_piece)
    y, rap = R.caler(deg, R.profil(x))
    err = B.erreur_de_courbe(rap.get("courbe_db") or [0.0] * len(TI), _vraie(_micro_piece))
    assert err <= 0.6, (err, rap.get("courbe_db"))
    assert P.si_sdr(x, y) >= P.si_sdr(x, deg) + 10, (P.si_sdr(x, deg), P.si_sdr(x, y))


def test_la_couleur_est_retiree_meme_sur_une_autre_hauteur(chant, chant_aigu):
    """La référence chante une octave plus haut (le même conduit vocal) : la couleur connue est quand même retirée (la courbe à 1,5 dB
    de la vraie, contre 2,8 dB sans calage), sans creuser la fondamentale de la voix calée. Témoin « ref_enveloppe »."""
    x, _ = chant
    deg = B.colorer(x, _micro_piece)
    y, rap = R.caler(deg, R.profil(chant_aigu[0]))
    c = rap.get("courbe_db") or [0.0] * len(TI)
    err = B.erreur_de_courbe(c, _vraie(_micro_piece))
    assert err <= 1.5, (err, c)
    assert max(abs(v) for v, f in zip(c, TI) if f < 250) <= 3.0, c
    assert P.si_sdr(x, y) >= P.si_sdr(x, deg) + 6, (P.si_sdr(x, deg), P.si_sdr(x, y))


def _profil_fabrique(env, ltas=None, bruit=None):
    n = len(TI)
    return {"enveloppe": {"tiers_db": list(env)}, "tiers_db": list(ltas if ltas is not None else [0.0] * n),
            "bruit_tiers_db": list(bruit if bruit is not None else [-80.0] * n)}


def test_la_courbe_est_lissee_sur_une_octave():
    """Une différence FINE (±5 dB d'un tiers d'octave à l'autre, comme des formants qui ne sont pas à la même place) ne passe pas dans la
    courbe (moins de 2 dB) ; une différence large (+4 dB sur deux octaves) passe. Témoin « ref_lissage »."""
    ref = _profil_fabrique([0.0] * len(TI))
    fine = _profil_fabrique([5.0 if i % 2 else -5.0 for i in range(len(TI))])
    assert max(abs(v) for v in R.courbe_appariement(fine, ref)) <= 2.0
    large = _profil_fabrique([4.0 if 500 <= c <= 2000 else 0.0 for c in TI])
    c = R.courbe_appariement(large, ref)
    assert min(v for v, f in zip(c, TI) if 630 <= f <= 1600) <= -3.0, c


def test_la_courbe_est_bornee_a_6_db():
    """Une différence large de 12 dB : la courbe s'arrête à ±6 dB. Témoin « ref_borne »."""
    ref = _profil_fabrique([0.0] * len(TI))
    src = _profil_fabrique([-12.0 if 1000 <= c <= 4000 else 0.0 for c in TI])
    c = R.courbe_appariement(src, ref)
    assert max(c) <= 6.0 and max(c) >= 5.0, c


def test_jamais_remonter_le_souffle():
    """Une bande où la voix n'est qu'à 10 dB au-dessus de son propre bruit (sous la marge de 20 dB) n'est jamais relevée, même si la
    référence y est plus forte. Témoin « ref_bruit »."""
    ref = _profil_fabrique([0.0] * len(TI))
    env = [-6.0 if 3000 <= c <= 6000 else 0.0 for c in TI]
    ltas = [-20.0] * len(TI)
    bruit = [-30.0 if 3000 <= c <= 6000 else -80.0 for c in TI]
    c = R.courbe_appariement(_profil_fabrique(env, ltas, bruit), ref)
    assert max(v for v, f in zip(c, TI) if 3000 <= f <= 6000) <= 0.0, c


def test_une_voix_propre_ne_bouge_pas(chant, rap):
    """Une voix calée sur sa propre référence : aucune courbe, et elle ressort intacte (SI-SDR ≥ 50 dB), chant comme rap."""
    for x, _ in (chant, rap):
        y, r = R.caler(x, R.profil(x))
        assert max(abs(v) for v in r["courbe_db"]) == 0.0
        assert P.si_sdr(x, y) >= 50, P.si_sdr(x, y)


# ------------------------------------------------------------------------------------------------ C. les sifflantes
def test_les_sifflantes_reviennent_a_la_force_de_la_reference(rap):
    """Un rap dont les sifflantes sont renforcées de 6 dB (trames sifflantes seulement) : le dé-esseur calé sur la voix d'origine rattrape
    au moins la moitié de l'écart de force (90e centile) et le SI-SDR remonte d'au moins 4 dB ; la part de sifflantes (le style) ne
    sert pas de cible. Témoin « ref_sifflantes »."""
    x, _ = rap
    pv = R.profil(x, avec_hauteur=False)
    deg = B.renforcer_sifflantes(x, 6.0)
    y, r = R.caler(deg, pv, reglages={"ref_egaliseur": "non"})
    vrai, avant = pv["sifflantes"]["p90_db"], R.profil_sifflantes(P._mono(deg))["p90_db"]
    apres = R.profil_sifflantes(P._mono(y))["p90_db"]
    assert avant - vrai >= 1.5
    assert apres <= avant - 0.5 * (avant - vrai), (vrai, avant, apres)
    assert P.si_sdr(x, y) >= P.si_sdr(x, deg) + 4, (P.si_sdr(x, deg), P.si_sdr(x, y))


# ------------------------------------------------------------------------------------------------ D. dans le projet : la référence et le mix
@pytest.fixture
def isoler(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "TELEPHONE", tmp_path / "telephone" / "Hakim" / "Chansons")
    monkeypatch.setattr(studio, "DOCUMENTS", tmp_path / "telephone" / "Hakim")
    monkeypatch.setattr(studio, "JOURNAL_DOCUMENTS", tmp_path / "telephone-ecritures.jsonl")
    monkeypatch.setattr(studio, "STUDIO", tmp_path / "chansons" / "studio")
    monkeypatch.setattr(studio, "CHANSONS", tmp_path / "chansons")
    monkeypatch.setattr(studio, "chant_en_cours", lambda taches=None: None)
    return tmp_path


def _projet(pistes, tempo=120.0, duree=14.0):
    """Un projet : des voix (tableau, rôle, réglages) et une instru (un grave et un bruit doux)."""
    p = SP.nouveau("Essai référence", tempo=tempo, tonalite="A minor")
    d = SP.dossier(p["id"])
    t = np.arange(int(duree * SR)) / SR
    inst = 0.2 * np.sin(2 * np.pi * 55 * t) + 0.02 * B.bruit_rose(len(t), 5)[:, 0]
    M.ecrire_wav(d / "pistes" / "instru.wav", np.column_stack([inst, inst]), SR, 32)
    for i, (x, role, r) in enumerate(pistes):
        M.ecrire_wav(d / "pistes" / f"v{i}.wav", x[: int(duree * SR)], SR, 32)

    def remplir(q):
        for i, (x, role, r) in enumerate(pistes):
            tr = SP.ajouter_piste(q, f"pistes/v{i}.wav", role, f"Voix {i}", duree_s=duree)
            if r:
                SP.regler_piste(tr, r)
        SP.ajouter_piste(q, "pistes/instru.wav", "instru", "Instru", duree_s=duree)
        q["duree_s"] = duree
    SP.modifier(p["id"], remplir)
    return p["id"]


def _reverbere(x, rt=1.5, wet=0.6, graine=3):
    m = P._mono(x)
    rng = np.random.default_rng(graine)
    n = int(SR * rt * 1.2)
    ir = rng.standard_normal(n) * 10 ** (-3 * (np.arange(n) / SR) / rt)
    ir /= np.sqrt((ir ** 2).sum())
    w = np.convolve(m, ir)[: len(m)]
    y = m + wet * w * np.sqrt((m ** 2).sum() / (w ** 2).sum())
    y *= 0.5 / np.abs(y).max()
    return np.column_stack([y, y])


def test_la_voix_de_papa_se_cale_sur_la_voix_de_hakim_du_projet(isoler, chant, chant_aigu):
    """« auto » : la voix de papa (colorée par un micro et une pièce connus) se cale sur la voix de Hakim du projet ; la voix de Hakim,
    elle, n'est pas touchée ; « référence=non » sur la piste, ou la référence du projet à « aucune », et rien ne se cale.
    Témoin « reference »."""
    pid = _projet([(chant_aigu[0], "voix_hakim", None), (B.colorer(chant[0], _micro_piece), "voix_papa", None)])
    p, d = SP.lire(pid), SP.dossier(pid)
    fichiers, rap = SP.preparer_pro(p, d)
    h, pa = p["pistes"][0]["id"], p["pistes"][1]["id"]
    assert "reference" not in rap.get(h, {})
    r = rap[pa]["reference"]
    assert r["distance_db"]["apres"] <= r["distance_db"]["avant"] - 0.8, r["distance_db"]
    assert "Voix 0" in r["source"] and "calée sur" in P.resume(rap[pa])
    SP.regler_piste(p["pistes"][1], SP.lire_reglages("référence=non"))
    assert p["pistes"][1]["pro"]["reference"] == "non"
    assert "reference" not in SP.preparer_pro(p, d)[1].get(pa, {})
    SP.regler_piste(p["pistes"][1], {"pro": {"reference": "auto"}})
    SP.regler_reference(p, {"source": "aucune"})
    assert "reference" not in SP.preparer_pro(p, d)[1].get(pa, {})
    assert "Référence : aucune" in SP.resume(p)


def test_au_mix_le_meme_espace_que_la_reference(isoler, chant, rap):
    """La voix de Hakim porte une réverbération (T60 1,5 s) ; la voix de papa est sèche. Au mix auto, l'envoi de réverbération de papa
    est cherché pour que sa traîne (mesurée aux fins de ses phrases sèches) tombe à 1,5 dB de celle de Hakim ; il reprend aussi le délai
    de Hakim (la tranche). Témoins « ref_espace » (la traîne reste loin), « ref_tranche » (le délai reste celui de papa)."""
    pid = _projet([(_reverbere(chant[0], 1.0, 0.25), "voix_hakim", None), (rap[0], "voix_papa", None)])
    p, d = SP.lire(pid), SP.dossier(pid)
    tr = Path(d) / ".t"
    tr.mkdir()
    rapport = SP.mixer_auto(p, d, tr)
    h, pa = p["pistes"][0], p["pistes"][1]
    e = rapport[pa["id"]]["reference_mix"].get("espace") or {}
    cible = e.get("cible_traine_db")
    fichiers, _ = SP.preparer_voix(p, d, tr)
    sec = R.mesure_mix(SP._rendre_seule(p, d, tr, fichiers, pa, False, "s"))
    hum = R.mesure_mix(SP._rendre_seule(p, d, tr, fichiers, pa, True, "h"), fins=sec["_fins"])
    assert cible is not None and abs(hum["reverberation"]["traine_db"] - cible) <= 1.5 and e["atteinte"], (hum["reverberation"], e)
    assert pa["delai"] == h["delai"] and pa["delai_note"] == h["delai_note"] and pa["delai"] > 0, (pa["delai"], h["delai"])


def test_au_mix_la_densite_se_rapproche_sans_ecraser(isoler, chant, rap):
    """La voix de Hakim est dense (écrêtée en douceur) ; celle de papa a des crêtes (+12 dB, 3 ms, toutes les 300 ms). Au mix auto, le
    compresseur de crêtes de papa resserre le facteur de crête de son corps d'au moins 1 dB, sans descendre sous le haut de la voix.
    Témoin « ref_densite »."""
    dense = np.tanh(3 * chant[0]) * 0.4
    x = rap[0].copy()
    pic = np.abs(x).max()
    for i in range(int(0.5 * SR), len(x) - SR, int(0.3 * SR)):
        x[i:i + int(0.003 * SR)] += 1.5 * pic * np.hanning(int(0.003 * SR))[:, None]
    x *= 0.5 / np.abs(x).max()
    pid = _projet([(dense, "voix_hakim", None), (x, "voix_papa", None)])
    p, d = SP.lire(pid), SP.dossier(pid)
    tr = Path(d) / ".t"
    tr.mkdir()
    rapport = SP.mixer_auto(p, d, tr)
    pa = p["pistes"][1]
    dn = rapport[pa["id"]]["reference_mix"].get("densite") or {}
    assert dn and dn["apres_crete_db"] <= dn["avant_crete_db"] - 1.0, dn
    assert pa["comp_rapide"]["seuil_db"] >= pa["comp"]["seuil_db"] + 6 - 0.05, (pa["comp_rapide"], pa["comp"])


def test_au_mix_la_parite_de_niveau(isoler, chant, chant_aigu):
    """La voix de papa calée vise la même hauteur au-dessus de l'instru que la voix de Hakim (1,5 LU, pas les 2 LU d'une voix de papa
    seule) ; l'équilibre mesuré tombe à 0,5 LU de la cible. Témoin « ref_parite »."""
    pid = _projet([(chant_aigu[0], "voix_hakim", None), (chant[0] * 0.7, "voix_papa", None)])
    p, d = SP.lire(pid), SP.dossier(pid)
    tr = Path(d) / ".t"
    tr.mkdir()
    rapport = SP.mixer_auto(p, d, tr)
    pa = p["pistes"][1]["id"]
    eq = rapport[pa]["equilibre"][-1]
    assert eq["vise_lu"] == SP.VOIX_AU_DESSUS["voix_hakim"] and abs(eq["ecart_lu"] - eq["vise_lu"]) <= 0.5, rapport[pa]["equilibre"]
    assert rapport[pa]["reference_mix"]["vise_lu"] == SP.VOIX_AU_DESSUS["voix_hakim"]


def test_un_profil_garde_sert_de_reference_a_un_projet_sans_hakim(isoler, chant, chant_aigu):
    """La voix de Hakim d'un projet gardée comme profil (« hakim », un travail de la file du studio) : un autre projet, sans voix de
    Hakim, s'y cale en « auto » ; les commandes du cockpit (référence, garder, lister) répondent."""
    pid = _projet([(chant_aigu[0], "voix_hakim", None)])
    vus = []
    q = SP.commande({"action": "garder_reference", "id": pid}, demarrer=vus.append)      # la page : un travail en file
    assert q["ok"] and q["travail"]["type"] == "reference" and q["travail"]["params"]["piste"] == q["piste"] and vus, q
    fiche = studio.faire(q["travail"], studio.STUDIO / "travaux", studio.STUDIO)        # le travailleur, appelé ici
    assert fiche["etat"] == "fini" and fiche["resultat"]["nom"] == "hakim", fiche
    assert [r["nom"] for r in SP.lister_references()] == ["hakim"]
    g = R.lire_profil(SP.references_dir() / "hakim.json")
    assert g["profil"]["enveloppe"]["tiers_db"] and g["cibles"]["humide"]["reverberation"] and g["tranche"]["reverb"] > 0
    pid2 = _projet([(B.colorer(chant[0], _micro_piece), "voix_papa", None)])
    p2, d2 = SP.lire(pid2), SP.dossier(pid2)
    _, rap = SP.preparer_pro(p2, d2)
    r = rap[p2["pistes"][0]["id"]]["reference"]
    assert "profil gardé « hakim »" in r["source"] and r["distance_db"]["apres"] < r["distance_db"]["avant"], r
    q = SP.commande({"action": "reference", "id": pid2, "source": "aucune", "rev": SP.lire(pid2)["rev"]})
    assert q["ok"] and q["projet"]["reference"]["source"] == "aucune"
    assert "reference" not in SP.preparer_pro(q["projet"], d2)[1].get(p2["pistes"][0]["id"], {})
    assert SP.commande({"action": "references"})["references"][0]["nom"] == "hakim"
    assert not SP.commande({"action": "reference", "id": pid2, "source": "n'importe"})["projet"]["reference"]["source"] == "n'importe"


def test_rendu_complet_dit_le_calage(isoler, chant, chant_aigu):
    """Un rendu entier, mix auto : l'avis dit le calage de la voix de papa (l'étape audio et le mix), le master tient −14 LUFS."""
    pid = _projet([(chant_aigu[0], "voix_hakim", None), (B.colorer(chant[0], _micro_piece), "voix_papa", None)])
    r = SP.rendre_projet(pid, "complet", mix_auto=True, envoyer=False)
    assert any("calée sur" in a for a in r["avis"]) and any("calée sur la référence au mix" in a for a in r["avis"]), r["avis"]
    assert abs(r["mesures"]["master"]["lufs"] + 14) <= 0.5


def test_les_outils_de_hakim_disent_la_reference(isoler, tmp_path, monkeypatch, chant, chant_aigu):
    """Hakim règle le calage (studio_piste « référence=non », studio_rendre reference=« aucune » / « t1 ») et garde sa voix comme profil
    (studio_piste action « garder_reference », en file) ; leurs descriptions le disent."""
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    outil = lambda n: mcp_server.mcp._tool_manager.get_tool(n).fn
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    pid = _projet([(chant_aigu[0], "voix_hakim", None), (chant[0], "voix_papa", None)])
    r = outil("studio_piste")("Essai référence", "voix 1", "regler", "référence=non")
    assert r.startswith("Réglée.") and SP.lire(pid)["pistes"][1]["pro"]["reference"] == "non", r
    vus = []
    monkeypatch.setattr(studio, "_demarrer_travailleur", vus.append)
    r = outil("studio_rendre")("Essai référence", reference="aucune")
    assert r.startswith("Rendu lancé") and SP.lire(pid)["reference"]["source"] == "aucune", r
    outil("studio_rendre")("Essai référence", reference="t1")
    assert SP.lire(pid)["reference"] == {"source": "piste", "piste": "t1", "profil": "hakim"}
    r = outil("studio_piste")("Essai référence", "", "garder_reference")
    assert r.startswith("Profil de référence en cours") and "Voix 0" in r, r
    for n, mots in (("studio_piste", ("référence", "garder_reference", "formants")), ("studio_rendre", ("reference", "profil", "aucune"))):
        doc = mcp_server.mcp._tool_manager.get_tool(n).description.lower()
        for w in mots:
            assert w in doc, (n, w)
