"""La chaîne « studio pro » de chaque voix (13/11, Ahmed : « un mix et master pro pour chaque voix, avec tous les nettoyages et les
modifs, et le mix et le master »). Un banc à VÉRITÉ CONNUE : une voix chantée propre (synthèse : notes tenues, vibrato, formants,
sifflantes, silences), dégradée de façon connue, puis l'écart à la voix propre (SI-SDR) avant et après chaque étape. Les seuils sont
écrits ici. Chaque mécanisme a son TÉMOIN : le même test, le mécanisme coupé (STUDIO_PRO_COUPE=<nom>), doit échouer.
(Le banc sur de vraies voix — Hakim, papa — : jarvis/studio_pro_banc.py.)"""
import json
import math
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
import studio_projet as SP  # noqa: E402

P.COUPE = frozenset(x for x in os.environ.get("STUDIO_PRO_COUPE", "").split(",") if x)
pytestmark = pytest.mark.skipif(not Path(studio.FFMPEG).exists(), reason="ffmpeg absent")
SR = 44100


@pytest.fixture(scope="module")
def voix():
    return B.voix_chantee(12.0)


def _seul(etape, **extra):
    return {"actif": True, **{e: ("auto" if e == etape else "non") for e in P.ETAPES}, **extra}


def _passe(x, etape, **extra):
    y, r = P.traiter(x, SR, _seul(etape, **extra))
    return y, r.get(etape) or {}


# ------------------------------------------------------------------------------------------------ A. le nettoyage, à vérité connue
def test_la_voix_propre_ressort_intacte(voix):
    """Toute la chaîne en « auto » sur une voix propre : aucune étape ne se déclenche, la voix ressort échantillon pour échantillon."""
    x, _ = voix
    y, r = P.traiter(x, SR, {"actif": True})
    assert [e for e in P.ETAPES if (r.get(e) or {}).get("actif")] == []
    assert P.si_sdr(x, y) >= 60


def test_souffle_profil_appris_sur_les_silences(voix):
    """Du bruit rose à 20 dB sous la voix : détecté (les silences sont du BRUIT : non voisés), et le Wiener à profil appris remonte
    l'écart d'au moins 2,5 dB ; aucune latence. Témoins : « souffle » coupé ; « voisement_derive » coupé (un bruit rose passe alors
    pour voisé, rien n'est débruité)."""
    x, _ = voix
    d = B.avec_bruit(x, 20)
    y, r = _passe(d, "souffle")
    assert r.get("actif") and r["mesure"]["bruit"] is True
    assert P.si_sdr(x, y) >= P.si_sdr(x, d) + 2.5, (P.si_sdr(x, d), P.si_sdr(x, y))
    assert P.decalage_echantillons(x, y, 500) == 0
    assert not P.mesure_souffle(x)["present"]


def test_ronflement_appris_dans_les_silences_et_suivi_en_phase(voix):
    """Le secteur à −42 dBFS (50 Hz et 7 harmoniques, sa fréquence qui dérive de ±0,05 Hz) : retiré d'au moins 15 dB (SI-SDR). Une voix
    en sol et ré (98, 147 Hz, voisins de 100 et 150 Hz) n'est pas abîmée par l'estimation : témoin « ronflement_silences » (estimé
    sur toute la prise, il emporte les partiels) ; témoin « suivi_phase » (la phase interpolée entre les silences décroche)."""
    x, _ = voix
    d = B.avec_ronflement(x, -42)
    y, r = _passe(d, "ronflement")
    assert r.get("actif") and r["mesure"]["hz"] == 50.0
    assert P.si_sdr(x, y) >= P.si_sdr(x, d) + 15, (P.si_sdr(x, d), P.si_sdr(x, y))
    assert not P.mesure_ronflement(x)["present"]


def test_ronflement_sous_un_long_chant_sans_silence():
    """(Le mutant survivant du 13/11 : sans le suivi de phase, le test d'avant passait encore — ses silences reviennent toutes les
    2,5 s.) 11,7 s de chant SANS un silence (les phrases recollées), 1,5 s de calme avant et après ; le réseau qui dérive : la phase
    interpolée entre les deux calmes décroche (+0,6 dB), suivie sur toute la prise elle tient (+15 dB au moins). Témoin « suivi_phase »."""
    x, ph = B.voix_chantee(16.0)
    chant = np.vstack([x[int(a * SR): int(b * SR)] for a, b in ph])
    calme = 1e-5 * np.random.default_rng(1).standard_normal((int(1.5 * SR), 2))
    v = np.vstack([calme, chant, calme])
    d = B.avec_ronflement(v, -42)
    y, r = _passe(d, "ronflement")
    assert r.get("actif")
    assert P.si_sdr(v, y) >= P.si_sdr(v, d) + 15, (P.si_sdr(v, d), P.si_sdr(v, y))


def test_clics_isoles_reperes_et_repares(voix):
    """Douze clics de bouche (deux sur trois entre les phrases) : chaque clic HORS du chant est trouvé et baisse d'au moins 15 dB ;
    ceux noyés dans le chant ne sont pas vus, le passage doux d'adeclick les entame (l'erreur autour de TOUS les clics baisse d'au
    moins 5 dB ; SI-SDR +5 dB). La voix propre n'a aucun « clic » (les impulsions de la glotte reviennent à chaque période : témoin
    « clics_isoles », la médiane du voisinage en fait des clics) ; témoin « clics_noyes » (sans le passage doux)."""
    x, ph = voix
    assert P.mesure_clics(x)["clics"] == 0
    c, pos = B.avec_clics(x, phrases_s=ph)
    y, r = _passe(c, "clics")
    assert r.get("actif") and r["mesure"]["clics"] >= 4
    w = int(0.005 * SR)
    err = lambda z, s: float(((z - x)[s] ** 2).sum())
    hors = [i for i in pos if not any(a - 0.05 <= i / SR <= b + 0.05 for a, b in ph)]
    assert len(hors) >= 4
    for i in hors:
        s = slice(max(0, i - w), i + w)
        assert 10 * math.log10(err(y, s) / err(c, s)) <= -15, (i / SR, 10 * math.log10(err(y, s) / err(c, s)))
    sel = np.zeros(len(x), bool)
    for i in pos:
        sel[max(0, i - w): i + w] = True
    assert 10 * math.log10(err(y, sel) / err(c, sel)) <= -5, 10 * math.log10(err(y, sel) / err(c, sel))
    assert P.si_sdr(x, y) >= P.si_sdr(x, c) + 5


def test_plosives_adoucies_seulement_pendant_la_bouffee(voix):
    """Une plosive (bouffée de 40-70 Hz) au début de chaque phrase : +15 dB au moins ; la voix propre n'en a aucune."""
    x, ph = voix
    d = B.avec_plosives(x, ph)
    y, r = _passe(d, "plosives")
    assert r.get("actif") and r["mesure"]["plosives"] >= len(ph) - 1
    assert P.si_sdr(x, y) >= P.si_sdr(x, d) + 15, (P.si_sdr(x, d), P.si_sdr(x, y))
    assert P.mesure_plosives(x)["plosives"] == 0


def test_ecretage_reconstruit(voix):
    """Écrêtée à 70 % de sa crête : les plateaux trouvés, reconstruits (+3 dB au moins) ; la voix propre n'a aucun plateau."""
    x, _ = voix
    d = B.ecreter(x, 0.7) / 0.7
    y, r = _passe(d, "ecretage")
    assert r.get("actif") and r["mesure"]["plateaux"] >= 3
    assert P.si_sdr(x, y) >= P.si_sdr(x, d) + 3, (P.si_sdr(x, d), P.si_sdr(x, y))
    assert not P.mesure_ecretage(x)["present"]


def test_respirations_baissees_jamais_supprimees(voix):
    """Des respirations fortes (−12 dB sous la voix) contre une vérité aux respirations naturelles (−30 dB) : baissées (+6 dB au moins),
    et JAMAIS supprimées (leur énergie reste à 9 dB au plus sous l'originale, pour −8 dB réglés)."""
    x, ph = voix
    ref = B.avec_respirations(x, ph, -30)
    d = B.avec_respirations(x, ph, -12)
    y, r = _passe(d, "respirations")
    assert r.get("actif") and r["mesure"]["respirations"] >= len(ph) - 2
    assert P.si_sdr(ref, y) >= P.si_sdr(ref, d) + 6, (P.si_sdr(ref, d), P.si_sdr(ref, y))
    souffle = d - x
    sel = np.abs(souffle[:, 0]) > 0
    baisse = M.db(y[sel] - x[sel]) - M.db(souffle[sel])
    assert -9.0 <= baisse <= -5.0, baisse
    assert P.mesure_respirations(x)["respirations"] == 0


def test_continu_retire(voix):
    x, _ = voix
    d = B.avec_continu(x, 0.05)
    y, r = _passe(d, "continu")
    assert r.get("actif") and P.si_sdr(x, y) >= 40
    assert not P.mesure_continu(x)["present"]


def test_porte_douce_entre_les_phrases(voix):
    """Après le débruitage d'un bruit à 20 dB, l'expandeur baisse encore le fond entre les phrases (4 dB au moins) sans toucher la voix
    (SI-SDR pas moins bon) ; sur une voix propre, il ne se déclenche pas."""
    x, ph = voix
    d = B.avec_bruit(x, 20)
    sans, _ = P.traiter(d, SR, {**_seul("souffle")})
    avec, r = P.traiter(d, SR, {**_seul("souffle"), "porte": "auto"})
    assert (r.get("porte") or {}).get("actif")
    gaps = np.zeros(len(x), bool)
    for (a0, b0), (a1, _) in zip(ph, ph[1:]):
        gaps[int((b0 + 0.15) * SR): int((a1 - 0.15) * SR)] = True
    assert M.db(avec[gaps]) <= M.db(sans[gaps]) - 4, (M.db(sans[gaps]), M.db(avec[gaps]))
    assert P.si_sdr(x, avec) >= P.si_sdr(x, sans) - 0.3
    assert not P.mesure_porte(x)["present"]


# ------------------------------------------------------------------------------------------------ B. les modifs
def test_nivellement_avant_la_compression(voix):
    """Un niveau qui varie de ±6 dB (toutes les 4 s) : ramené (SI-SDR +8 dB au moins, l'écart-type du niveau au moins divisé par 2) ;
    une voix déjà égale (écart-type < 3 dB) n'est pas touchée."""
    x, _ = voix
    d = B.avec_niveau_qui_varie(x)
    y, r = _passe(d, "nivellement")
    assert r.get("actif")
    assert P.si_sdr(x, y) >= P.si_sdr(x, d) + 8, (P.si_sdr(x, d), P.si_sdr(x, y))
    assert P.mesure_nivellement(y)["ecart_type_db"] <= P.mesure_nivellement(d)["ecart_type_db"] / 2
    assert not P.mesure_nivellement(x)["present"]


def test_caler_un_double_phrase_par_phrase(voix):
    """Un double (la même voix un peu changée : plus douce, filtrée, du souffle) décalé de +40, −25, +15 ms… phrase par phrase : chaque
    décalage retrouvé à 3 ms près."""
    x, ph = voix
    m = P._mono(x)
    vrais = [40, -25, 15, 30, -35, 20, -10]
    dbl = np.zeros_like(m)
    for (a, b), dms in zip(ph, vrais):
        i0, i1 = int((a - 0.1) * SR), int((b + 0.1) * SR)
        s = int(dms / 1000 * SR)
        seg = m[i0:i1] * 0.6
        dbl[i0 + s: i1 + s] += seg[: len(dbl[i0 + s: i1 + s])]
    dbl = P._filtre_fft(dbl, SR, lambda f: P._butter_mag(f, 7000, 2, False)) + 1e-4 * np.random.default_rng(2).standard_normal(len(dbl))
    out = P.caler_phrases(m, dbl, SR)
    trouves = [o["decalage_ms"] for o in out]
    assert len(out) == len(ph)
    for t, v in zip(trouves, vrais):
        assert abs(t - v) <= 3, (trouves, vrais)


def test_aucune_etape_n_ajoute_de_latence(voix):
    x, ph = voix
    d = B.avec_clics(B.avec_plosives(B.avec_ronflement(B.avec_bruit(x, 25), -45), ph), phrases_s=ph)[0]
    for dn in ("wiener", "afftdn"):
        y, _ = P.traiter(d, SR, {"actif": True, "debruiteur": dn, "nivellement": "non"})
        assert P.decalage_echantillons(x, y, 3000) == 0, dn


def test_reglages_bornes_et_modes():
    r = P.borner({"souffle": "non", "clics": "oui", "plosives": "n'importe", "respirations_db": -99, "type": "double", "debruiteur": "x",
                  "actif": "non"})
    assert r["souffle"] == "non" and r["clics"] == "oui" and r["plosives"] == "auto" and r["respirations_db"] == -30
    assert r["type"] == "double" and r["debruiteur"] == "auto" and r["actif"] is False
    x, _ = B.voix_chantee(4.0)
    d = B.avec_continu(x, 0.05)
    y, rap = P.traiter(d, SR, {"continu": "non"})
    assert not rap["continu"]["actif"] and abs(y.mean() - 0.05) < 1e-3              # coupée : le continu reste
    assert "décalage continu retiré" in P.resume(P.traiter(d, SR, {})[1])


# ------------------------------------------------------------------------------------------------ C. le mix (studio_projet)
@pytest.fixture
def isoler(tmp_path, monkeypatch):
    monkeypatch.setattr(studio, "TELEPHONE", tmp_path / "telephone" / "Hakim" / "Chansons")
    monkeypatch.setattr(studio, "DOCUMENTS", tmp_path / "telephone" / "Hakim")
    monkeypatch.setattr(studio, "JOURNAL_DOCUMENTS", tmp_path / "telephone-ecritures.jsonl")
    monkeypatch.setattr(studio, "STUDIO", tmp_path / "chansons" / "studio")
    monkeypatch.setattr(studio, "CHANSONS", tmp_path / "chansons")
    monkeypatch.setattr(studio, "chant_en_cours", lambda taches=None: None)
    return tmp_path


def _projet_voix(pistes, tempo=120.0, duree=12.0):
    """Un projet : des voix (fichier, rôle, réglages) et une instru (un grave et un bruit doux)."""
    p = SP.nouveau("Essai pro", tempo=tempo, tonalite="A minor")
    d = SP.dossier(p["id"])
    t = np.arange(int(duree * SR)) / SR
    inst = 0.2 * np.sin(2 * np.pi * 55 * t) + 0.02 * B.bruit_rose(len(t), 5)[:, 0]
    M.ecrire_wav(d / "pistes" / "instru.wav", np.column_stack([inst, inst]), SR, 32)
    for i, (x, role, r) in enumerate(pistes):
        M.ecrire_wav(d / "pistes" / f"v{i}.wav", x, SR, 32)

    def remplir(q):
        for i, (x, role, r) in enumerate(pistes):
            tr = SP.ajouter_piste(q, f"pistes/v{i}.wav", role, f"Voix {i}", duree_s=duree)
            if r:
                SP.regler_piste(tr, r)
        SP.ajouter_piste(q, "pistes/instru.wav", "instru", "Instru", duree_s=duree)
        q["duree_s"] = duree
    SP.modifier(p["id"], remplir)
    return p["id"]


def _sifflante_et_crete(duree=6.0):
    """Une voix d'essai : un 220 Hz tenu, avec des crêtes brèves (+14 dB, 3 ms) toutes les 250 ms."""
    t = np.arange(int(duree * SR)) / SR
    x = 0.08 * np.sin(2 * np.pi * 220 * t)
    for k in range(int(duree * 4)):
        i = int((0.1 + k * 0.25) * SR)
        x[i:i + 130] += 0.4 * np.sin(2 * np.pi * 220 * t[i:i + 130]) * np.hanning(130)
    return np.column_stack([x, x])


def test_compression_en_deux_temps_tient_les_cretes(isoler, tmp_path):
    """Les crêtes brèves d'une voix (+14 dB, 3 ms) : avec la compression rapide devant la lente, l'écart crête/efficace baisse d'au
    moins 3 dB de plus qu'avec la lente seule. Témoin « deux_temps »."""
    x = _sifflante_et_crete()
    lente = {"comp": {"actif": True, "seuil_db": -24, "ratio": 2.5, "attaque_ms": 20, "relache_ms": 250}, "eq": {"coupe_bas_hz": 0},
             "reverb": 0, "pro": {"actif": False}}
    pid = _projet_voix([(x, "voix_hakim", lente)], duree=6.0)
    p = SP.lire(pid)
    p["pistes"] = [t for t in p["pistes"] if t["role"] != "instru"]
    f1, f2 = tmp_path / "lente.wav", tmp_path / "deux.wav"
    SP.rendre_bus(p, SP.dossier(pid), f1)
    SP.regler_piste(p["pistes"][0], {"comp_rapide": {"actif": True, "seuil_db": -16, "ratio": 6, "attaque_ms": 0.5, "relache_ms": 60}})
    SP.rendre_bus(p, SP.dossier(pid), f2)
    a, b = M.lire(f1)[0], M.lire(f2)[0]
    cf = lambda z: 20 * math.log10(np.abs(z).max() / np.sqrt((z ** 2).mean()))
    assert cf(b) <= cf(a) - 3, (cf(a), cf(b))


def test_saturation_legere_pour_la_presence(isoler, tmp_path, voix):
    """L'excitateur (saturation 0,2) : les aigus (8 kHz) montent de 1,5 dB au moins, les médiums ne bougent pas de plus de 1 dB.
    Témoin « saturation »."""
    x, _ = voix
    pid = _projet_voix([(x, "voix_hakim", {"comp": {"actif": False}, "eq": {"coupe_bas_hz": 0}, "reverb": 0, "pro": {"actif": False}})])
    p = SP.lire(pid)
    p["pistes"] = [t for t in p["pistes"] if t["role"] != "instru"]
    f1, f2 = tmp_path / "a.wav", tmp_path / "b.wav"
    SP.rendre_bus(p, SP.dossier(pid), f1)
    SP.regler_piste(p["pistes"][0], {"saturation": 0.2})
    SP.rendre_bus(p, SP.dossier(pid), f2)
    ba, bb = np.array(M.bandes(M.lire(f1)[0])), np.array(M.bandes(M.lire(f2)[0]))
    e = (bb - bb[4]) - (ba - ba[4])                     # relatif à 500 Hz
    assert e[8] >= 1.5 and abs(e[5]) <= 1.0, e


def test_de_esseur_apres_la_compression():
    """L'ordre de la tranche : coupe-bas, coupe-haut, égaliseur, compression rapide, compression lente, saturation, PUIS le dé-esseur.
    Témoin « deesser_apres »."""
    t = SP.reglages_par_defaut("voix_hakim")
    SP.regler_piste(t, {"deesser": 0.5, "saturation": 0.2, "eq": {"coupe_haut_hz": 9000}, "comp_rapide": {"actif": True}})
    ch = [f.split("=")[0] for f in SP._chaine_piste(t, 120)]
    assert ch == ["highpass", "lowpass", "acompressor", "acompressor", "aexciter", "deesser"], ch


def test_doubles_ouverts_plus_bas_plus_filtres_et_cales(isoler, voix):
    """Une voix principale et deux doubles (décalés de +30 et −20 ms) : au mix auto, les doubles s'ouvrent à gauche et à droite, plus
    filtrés (coupe-bas ≥ 200 Hz, coupe-haut ≤ 9 kHz), 6 dB sous la principale (±1,5) ; ils sont recalés (régions par phrase) à 3 ms
    près. Témoins « types » et « calage »."""
    x, ph = voix
    m = P._mono(x)

    def decale(ms, g=0.7):
        s = int(ms / 1000 * SR)
        y = np.zeros_like(m)
        y[max(0, s): len(m) + min(0, s)] = m[max(0, -s): len(m) - max(0, s)] * g
        return np.column_stack([y, y])
    pid = _projet_voix([(x, "voix_hakim", None), (decale(30), "voix_hakim", {"pro": {"type": "double"}}),
                        (decale(-20), "voix_hakim", {"pro": {"type": "double"}})])
    p = SP.lire(pid)
    d = SP.dossier(pid)
    tr = Path(d) / ".t"
    tr.mkdir()
    rap = SP.mixer_auto(p, d, tr)
    lead, d1, d2 = p["pistes"][:3]
    assert d1["pan"] * d2["pan"] < 0 and abs(d1["pan"]) >= 0.5 and abs(lead["pan"]) < 0.01
    for t in (d1, d2):
        assert t["eq"]["coupe_bas_hz"] >= 200 and 1000 <= t["eq"]["coupe_haut_hz"] <= 9000
        e = rap[t["id"]]["equilibre"][-1]
        assert abs(e["ecart_lu"] + 6) <= 1.5, e
        assert rap[t["id"]]["calage"]["cale"] is True
    fichiers, _ = SP.preparer_voix(p, d, tr)
    L = SP._sur_la_ligne(fichiers.get(lead["id"]) or d / lead["fichier"], lead["regions"], 12.0)
    for t, v in ((d1, 30), (d2, -20)):
        Y = SP._sur_la_ligne(fichiers.get(t["id"]) or d / t["fichier"], t["regions"], 12.0)
        reste = [o["decalage_ms"] for o in P.caler_phrases(L, Y, SR)]
        assert max(abs(r) for r in reste) <= 3, (v, reste)


def test_adlibs_delai_jete_en_fin_de_phrase(isoler, voix, tmp_path):
    """Un ad-lib : son délai n'est envoyé qu'en fin de phrase (fenêtres jetées) : au milieu des phrases, l'écho est au moins 15 dB
    plus bas qu'après leur fin. Témoin « jete »."""
    x, ph = voix
    pid = _projet_voix([(x, "voix_hakim", None), (x * 0.5, "voix_hakim", {"pro": {"type": "adlib"}})])
    p = SP.lire(pid)
    d = SP.dossier(pid)
    tr = Path(d) / ".t"
    tr.mkdir()
    SP.mixer_auto(p, d, tr)
    ad = p["pistes"][1]
    assert ad["jetes"] and ad["delai"] >= 0.3
    q = {**p, "pistes": [dict(ad, reverb=0, volume_db=0, pan=0)]}
    q["pistes"][0]["regions"] = ad["regions"]
    f = tmp_path / "ad.wav"
    SP.rendre_bus(q, d, f, seules=[ad["id"]])
    y = P._mono(M.lire(f)[0]) - 10 ** (0 / 20) * 0                 # le son entier (sec + écho)
    sec = tmp_path / "sec.wav"
    q2 = {**q, "pistes": [dict(q["pistes"][0], delai=0)]}
    SP.rendre_bus(q2, d, sec, seules=[ad["id"]])
    echo = y - P._mono(M.lire(sec)[0])
    # (les échos tombent 0,5, 1 et 1,5 s après : le milieu d'une phrase se mesure hors des 1,7 s qui suivent la fin de la précédente)
    fins = [-9.0] + [b for _, b in ph]
    au_milieu = np.concatenate([echo[int(max(a + 0.4, fp + 1.7) * SR): int((b - 0.5) * SR)] for (a, b), fp in zip(ph, fins)
                                if b - 0.5 > max(a + 0.4, fp + 1.7) + 0.05])
    apres = np.concatenate([echo[int((b + 0.15) * SR): int((b + 0.45) * SR)] for a, b in ph])
    assert M.db(au_milieu) <= M.db(apres) - 15, (M.db(au_milieu), M.db(apres))


def test_bus_des_voix_et_retour_de_reverb_filtre(isoler, voix, tmp_path):
    """Le mix auto pose un bus des voix (seuil mesuré) et le graphe le contient ; le retour de réverb est filtré (coupe-haut 8 kHz) et
    pré-retardé d'une triple croche (120 BPM : 62,5 → 60 ms au plus). Témoins « bus_voix », « predelai », « retour_filtre »."""
    x, _ = voix
    pid = _projet_voix([(x, "voix_hakim", None), (x * 0.5, "voix_papa", None)])
    p = SP.lire(pid)
    d = SP.dossier(pid)
    tr = Path(d) / ".t"
    tr.mkdir()
    SP.mixer_auto(p, d, tr)
    assert p["bus_voix"]["actif"] and -50 <= p["bus_voix"]["seuil_db"] <= -3
    ir = SP.reponse_impulsionnelle(tmp_path / "ir.wav")
    _, fc, _ = SP.graphe(p, d, ir=ir)
    assert "[busvoix]" in fc
    assert "adelay=60.0:all=1" in fc and "lowpass=f=8000" in fc
    assert SP.predelai_ms(140) == 53.6 and SP.predelai_ms(0) == 20.0


# ------------------------------------------------------------------------------------------------ D. le master
def _bus(tmp_path, duree=8.0):
    """Un bus de mix : un 808 (55 Hz) à coups forts, des médiums réguliers, des graves EN OPPOSITION de phase (trop larges)."""
    t = np.arange(int(duree * SR)) / SR
    k = np.zeros_like(t)
    for i in range(int(duree * 2)):
        a = int(i * 0.5 * SR)
        k[a:a + int(0.3 * SR)] += np.exp(-np.arange(int(0.3 * SR)) / SR / 0.12)[: len(k[a:a + int(0.3 * SR)])]
    graves = 0.5 * k * np.sin(2 * np.pi * 55 * t)
    med = 0.08 * np.sin(2 * np.pi * 1000 * t) * (1 + 0.2 * np.sin(2 * np.pi * 0.5 * t))
    cote = 0.1 * np.sin(2 * np.pi * 70 * t)
    x = np.column_stack([graves + med + cote, graves + med - cote])
    f = tmp_path / "bus.wav"
    M.ecrire_wav(f, x, SR, 32)
    return f


def _bande_temps(z, f0, sr=SR):
    y = P._filtre_fft(P._mono(z), sr, lambda f: P._butter_mag(f, f0 * 1.5, 4, False) * P._butter_mag(f, f0 / 1.5, 4, True))
    return P.niveaux_db(y, sr, 0.05, 0.05)


def test_master_multibande_graves_mono_et_cible(isoler, tmp_path):
    """Le master : en 3 bandes (les coups de 808 tenus : la plage du grave baisse d'au moins 1,5 dB de plus qu'en une bande, les médiums
    réguliers ne bougent pas) ; les graves en mono sous 120 Hz (le côté à 70 Hz baisse de 15 dB au moins) ; LUFS visé, crête vraie
    ≤ −1 dBTP sur le WAV et le MP3. Témoins « multibande », « mono_graves »."""
    bus = _bus(tmp_path)
    p = SP.nouveau("M")
    params = SP.chaine_master_params(bus, p)
    assert params["multibande"] and len(params["multibande"]) == 3 and params["mono_graves_hz"] == 120
    w, mp3 = tmp_path / "m.wav", tmp_path / "m.mp3"
    SP.masteriser(bus, w, params, mp3)
    une = {**params, "multibande": None, "mono_graves_hz": 0}
    w1 = tmp_path / "m1.wav"
    SP.masteriser(bus, w1, une)
    m, m1 = M.ebur128(w), M.ebur128(mp3)
    assert abs(m["lufs"] + 14) <= 0.5 and m["crete_dbtp"] <= -1.0 and m1["crete_dbtp"] <= -1.0
    xa, xb = M.lire(w)[0], M.lire(w1)[0]
    plage = lambda z: float(np.percentile(_bande_temps(z, 55), 95) - np.percentile(_bande_temps(z, 55), 30))
    assert plage(xa) <= plage(xb) - 1.5, (plage(xa), plage(xb))
    cote = lambda z: M.db(P._filtre_fft((z[:, 0] - z[:, 1]) / 2, SR, lambda f: P._butter_mag(f, 100, 4, False)))
    milieu = lambda z: M.db(P._filtre_fft((z[:, 0] + z[:, 1]) / 2, SR, lambda f: P._butter_mag(f, 100, 4, False)))
    assert cote(xa) - milieu(xa) <= cote(xb) - milieu(xb) - 15, (cote(xa) - milieu(xa), cote(xb) - milieu(xb))


def test_cible_club_plus_fort(isoler, tmp_path):
    """La cible « club » : −9 LUFS (±0,5), la crête vraie toujours ≤ −1 dBTP (WAV et MP3). Témoin « cible »."""
    bus = _bus(tmp_path)
    p = SP.nouveau("C")
    SP.regler_master(p, {"cible": "club"})
    assert p["master"]["cible"] == "club"
    params = SP.chaine_master_params(bus, p)
    w, mp3 = tmp_path / "c.wav", tmp_path / "c.mp3"
    SP.masteriser(bus, w, params, mp3)
    m, m1 = M.ebur128(w), M.ebur128(mp3)
    assert abs(m["lufs"] + 9) <= 0.5 and m["crete_dbtp"] <= -1.0 and m1["crete_dbtp"] <= -1.0, (m, m1)


def test_dither_du_wav_16_bits(tmp_path):
    """Un 1 kHz à −80 dBFS passé en 16 bits : sans dither, la troncature fait des harmoniques (3 kHz) ; avec le dither triangulaire,
    elles tombent d'au moins 10 dB (sous le bruit). Témoin « dither »."""
    t = np.arange(SR * 3) / SR
    x = 10 ** (-80 / 20) * np.sin(2 * np.pi * 1000 * t)
    f = tmp_path / "x.wav"
    M.ecrire_wav(f, np.column_stack([x, x]), SR, 32)
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    SP.exporter_16bits(f, a, dither=True)
    SP._filtre(f, b, "aresample=osf=s16:dither_method=none", "pcm_s16le")

    def h3(z):
        S = np.abs(np.fft.rfft(P._mono(z)[: SR * 2] * np.hanning(SR * 2)))
        fr = np.fft.rfftfreq(SR * 2, 1 / SR)
        return 20 * math.log10(S[(fr > 2990) & (fr < 3010)].max() / S[(fr > 990) & (fr < 1010)].max())
    assert h3(M.lire(a)[0]) <= h3(M.lire(b)[0]) - 10, (h3(M.lire(a)[0]), h3(M.lire(b)[0]))


# ------------------------------------------------------------------------------------------------ pour Hakim : ses outils, la page
def test_reglages_en_mots_et_commande_du_master(isoler):
    r = SP.lire_reglages("nettoyage=oui, souffle=non, respirations=auto, respirations_db=-6, type=double, calage=non, saturation=0.3, "
                         "coupe_haut=9000, comp_rapide=oui, débruiteur=afftdn")
    t = SP.reglages_par_defaut("voix_hakim")
    SP.regler_piste(t, r)
    assert t["pro"]["souffle"] == "non" and t["pro"]["respirations_db"] == -6 and t["pro"]["type"] == "double"
    assert t["pro"]["calage"] == "non" and t["pro"]["debruiteur"] == "afftdn" and t["saturation"] == 0.3
    assert t["eq"]["coupe_haut_hz"] == 9000 and t["comp_rapide"]["actif"] is True
    assert "pro" not in SP.reglages_par_defaut("instru")
    p = SP.nouveau("Cmd")
    q = SP.commande({"action": "projet", "id": p["id"], "cible": "club", "multibande": False, "largeur": "0.9", "dither16": "non"})
    assert q["ok"] and q["projet"]["master"]["lufs"] == -9.0 and q["projet"]["master"]["multibande"] is False
    assert q["projet"]["master"]["largeur"] == 0.9 and q["projet"]["master"]["dither16"] is False
    assert "Master : club (-9.0 LUFS)" in SP.resume(q["projet"])


def test_les_outils_de_hakim_exposent_le_studio_pro(isoler, tmp_path, monkeypatch, voix):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    outil = lambda n: mcp_server.mcp._tool_manager.get_tool(n).fn
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    x, _ = voix
    pid = _projet_voix([(x, "voix_hakim", None)])
    r = outil("studio_piste")("essai pro", "voix 0", "regler", "souffle=oui, respirations_db=-10, type=back, saturation=0.25")
    assert r.startswith("Réglée.") and "voix back" in r and "souffle oui" in r
    vus = []
    monkeypatch.setattr(studio, "_demarrer_travailleur", vus.append)
    r = outil("studio_rendre")("essai pro", cible="club")
    assert r.startswith("Rendu lancé") and "club" in r and SP.lire(pid)["master"]["lufs"] == -9.0
    for n, mots in (("studio_rendre", ("nettoyage", "respirations", "multibande", "dither", "club")),
                    ("studio_piste", ("souffle", "ronflement", "clics", "plosives", "respirations", "type", "calage"))):
        doc = mcp_server.mcp._tool_manager.get_tool(n).description.lower()
        for w in mots:
            assert w in doc, (n, w)


def test_rendu_complet_avec_la_chaine_pro(isoler, voix):
    """Un rendu entier, mix auto : la voix dégradée (souffle, ronflement, plosives) nettoyée selon la mesure, le rapport dit ce qui a
    été fait, le WAV 16 bits existe, le master tient −14 LUFS et −1 dBTP."""
    x, ph = voix
    d = B.avec_plosives(B.avec_ronflement(B.avec_bruit(x, 25), -45), ph)
    pid = _projet_voix([(d, "voix_hakim", None)])
    r = SP.rendre_projet(pid, "complet", mix_auto=True, envoyer=False)
    pro = r["pro"][0]["resume"]
    assert "ronflement 50 Hz retiré" in pro and "souffle débruité" in pro and "plosives adoucies" in pro, pro
    assert Path(r["fichiers"]["complet"]["wav16"]).is_file()
    assert abs(r["mesures"]["master"]["lufs"] + 14) <= 0.5 and r["mesures"]["mp3"]["crete_dbtp"] <= -1.0
    assert any("Voix 0 :" in a for a in r["avis"]) and any("3 bandes" in a for a in r["avis"])
    f = r["pro"][0]["fond"]
    assert f["apres_dbfs"] <= f["avant_dbfs"] - 6, f
