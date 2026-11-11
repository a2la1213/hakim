"""L'autotune refait (11/11, Ahmed : « il faut améliorer son autotune : même le léger part en steak ») : sur une voix de synthèse dont on
connaît tout (ses notes, son vibrato, ses formants, ses consonnes), on vérifie ce qui faisait « steak » — et chaque test a son témoin : le
mécanisme coupé (ou l'ancien autotune), le test doit voir la différence."""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

JARVIS = Path(__file__).resolve().parent.parent / "jarvis"
sys.path.insert(0, str(JARVIS))
import autotune as AT  # noqa: E402
import chant  # noqa: E402

SR = 44100
LA3 = 220.0
PYTHON_CHANT = next((p for p in (Path(os.environ.get("JARVIS_PYTHON_CHANT", "")), JARVIS / ".venv-chant" / "bin" / "python",
                                  Path.home() / "Desktop" / "anamnese" / "jarvis" / ".venv-chant" / "bin" / "python") if str(p) not in ("", ".") and p.exists()),
                    JARVIS / ".venv-chant" / "bin" / "python")

# ---------------------------------------------------------------------------------------------------- la voix de synthèse
FORMANTS = {"a": [(700, 110, 1.0), (1220, 90, 0.5), (2600, 160, 0.25)], "i": [(300, 60, 1.0), (2300, 120, 0.4), (3000, 200, 0.2)]}


def _env(f, voy):
    return sum(g / (1 + ((f - F) / B) ** 2) for F, B, g in FORMANTS[voy]) + 0.02


def voyelle(dur, f0, voy="a", amp=0.3):
    """Des harmoniques en phase (une impulsion par période, comme la glotte) sous les formants de la voyelle ; f0 : Hz ou f(t)."""
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = f0(t) if callable(f0) else np.full(n, float(f0))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.zeros(n)
    for h in range(1, 60):
        m = h * f < 5000
        if not m.any():
            break
        x += np.where(m, _env(h * f, voy) / h ** 0.5 * np.cos(h * ph), 0.0)
    r = int(0.01 * SR)
    x[:r] *= np.linspace(0, 1, r)
    x[n - r:] *= np.linspace(1, 0, r)
    return amp * x / np.abs(x).max()


def consonne(dur, amp=0.08, graine=1):
    """Un « s » : du bruit clair."""
    b = np.diff(np.random.default_rng(graine).standard_normal(int(SR * dur) + 1))
    return amp * b * np.hanning(len(b)) / np.abs(b).max()


def silence(dur):
    return np.zeros(int(SR * dur))


def vibrato(f, profondeur_c=25.0, vitesse=5.5, ecart_c=0.0):
    return lambda t: f * 2 ** ((ecart_c + profondeur_c * np.sin(2 * np.pi * vitesse * t)) / 1200)


def phrase():
    """0,1 s de silence ; un « a » tenu 0,8 s, 40 cents trop haut, vibrato ±25 cents ; un « s » de 0,1 s ; un « i » tenu 0,6 s, 30 cents
    trop haut ; 0,1 s de silence. Rend (son, bornes)."""
    morceaux = [silence(0.1), voyelle(0.8, vibrato(LA3, 25, 5.5, 40)), consonne(0.1), voyelle(0.6, LA3 * 2 ** (230 / 1200), "i"), silence(0.1)]
    return np.concatenate(morceaux), {"note1": (0.1, 0.9), "s": (0.9, 1.0), "note2": (1.0, 1.6)}


def cents(x, a, b, ref):
    """La hauteur mesurée (cents depuis ref) sur [a, b] secondes, trame par trame."""
    c = AT.hauteur_cents(x, SR)
    k0, k1 = int(a / 0.005), int(b / 0.005)
    v = c[k0:k1]
    return v[np.isfinite(v)] - ref


def _mi(a, b, marge=0.1):
    return a + marge, b - marge


# ---------------------------------------------------------------------------------------------------- les niveaux

def test_niveaux():
    assert AT.niveau_de(True) == "leger" and AT.niveau_de("léger") == "leger" and AT.niveau_de("light") == "leger"
    assert AT.niveau_de("fort") == "fort" and AT.niveau_de("HARD") == "fort" and AT.niveau_de("max") == "fort"
    assert AT.niveau_de(False) == AT.niveau_de(None) == AT.niveau_de("") == AT.niveau_de("non") == AT.niveau_de(0) == ""
    assert AT.niveau_de(2) == "fort" and AT.niveau_de(1) == "leger"
    y, r = AT.corriger(phrase()[0], SR, niveau="")
    assert r["niveau"] == "" and np.array_equal(y, phrase()[0])


# ---------------------------------------------------------------------------------------------------- correction partielle, vitesse, vibrato

def test_leger_rapproche_de_40_pourcent_et_fort_recale():
    x, B = phrase()
    a, b = _mi(*B["note1"])
    avant = np.mean(cents(x, a, b, 5700))
    assert 35 < avant < 45                                                   # la voix chante 40 cents trop haut
    yl, rl = AT.corriger(x, SR, niveau="leger", second=False)
    yf, _ = AT.corriger(x, SR, niveau="fort", second=False)
    leger, fort = np.mean(cents(yl, a, b, 5700)), np.mean(cents(yf, a, b, 5700))
    assert abs(leger - 0.6 * avant) < 5, (avant, leger)                     # léger : 40 % du chemin (24 cents restent)
    assert abs(fort) < 4, fort                                               # fort : sur la note
    assert rl["notes"] == 2 and rl["niveau"] == "leger"
    a2, b2 = _mi(*B["note2"])
    assert abs(np.mean(cents(yl, a2, b2, 5900)) - 18) < 5                    # la seconde note : 30 → 18 cents
    # témoins : le mécanisme coupé (force 0) ne bouge rien ; l'ancien recalage (chant.caler, force 1) met tout sur la note, même en « léger »
    y0, _ = AT.corriger(x, SR, niveau="leger", second=False, reglages={"force": 0.0})
    assert abs(np.mean(cents(y0, a, b, 5700)) - avant) < 2
    f = np.array([LA3 * 2 ** (40 / 1200)])
    assert abs(1200 * np.log2(chant.caler(f, tuple(range(12)))[0] / LA3)) < 0.5


def test_leger_garde_le_vibrato_fort_l_aplatit():
    x, B = phrase()
    a, b = _mi(*B["note1"])

    def ondulation(s):
        c = cents(s, a, b, 5700)
        return float(np.std(c - np.convolve(c, np.ones(31) / 31, "same")[: len(c)]) if len(c) > 40 else 0) or float(np.std(c))
    v0 = np.std(cents(x, a, b, 5700))
    vl = np.std(cents(AT.corriger(x, SR, niveau="leger", second=False)[0], a, b, 5700))
    vf = np.std(cents(AT.corriger(x, SR, niveau="fort", second=False)[0], a, b, 5700))
    assert v0 > 14                                                           # ±25 cents de vibrato
    assert vl > 0.9 * v0, (v0, vl)                                           # léger : il reste
    assert vf < 0.3 * v0, (v0, vf)                                           # témoin : fort l'efface, et la mesure le voit


def test_vitesse_de_correction_lente_en_leger():
    """Une note tenue, 40 cents trop haut, sans vibrato : la correction part de zéro et met son temps (léger : jamais moins de 50 ms
    pour la moitié du chemin) ; fort va vite ; témoin : retune_ms quasi nul → la marche immédiate de l'ancien autotune."""
    x = np.concatenate([silence(0.1), voyelle(0.8, LA3 * 2 ** (40 / 1200)), silence(0.1)])

    def mi_chemin_ms(niveau, reglages=None):
        P = {**AT.NIVEAUX[niveau], **(reglages or {})}
        A = AT.analyser(x, SR, second=False)
        corr, ten = AT.correction(A, P, tuple(range(12)))
        (i, j), = ten
        c = np.abs(corr[i:j])
        return float(np.argmax(c >= 0.5 * c.max()) * AT.TRAME_MS)
    lent, vif = mi_chemin_ms("leger"), mi_chemin_ms("fort")
    assert lent >= 50, lent
    assert vif <= 25, vif
    assert mi_chemin_ms("fort", {"retune_ms": 0.01, "bords_ms": 0.01}) <= 5   # témoin : sans vitesse, la marche


def test_un_glisse_reste_le_sien_en_leger():
    """Un glissé d'un demi-ton en 150 ms au milieu d'une note : léger n'y touche pas (sa pente) ; témoin : sans la garde des glissés,
    la correction y passe."""
    def f(t):
        return LA3 * 2 ** (np.clip((t - 0.3) / 0.15, 0, 1) * 100 / 1200 + 30 / 1200)
    x = np.concatenate([silence(0.1), voyelle(0.8, f), silence(0.1)])
    P = AT.NIVEAUX["leger"]
    A = AT.analyser(x, SR, second=False)
    corr, ten = AT.correction(A, P, tuple(range(12)))
    k0, k1 = int(0.44 / 0.005), int(0.51 / 0.005)                         # le milieu du glissé (0,1 s de silence d'abord)
    assert np.abs(corr[k0:k1]).max() * 100 < 3
    corr2, _ = AT.correction(A, {**P, "glisse_cents_s": 0.0}, tuple(range(12)))
    assert np.abs(corr2[k0:k1]).max() * 100 > 5


# ---------------------------------------------------------------------------------------------------- consonnes, souffle, voix douteuse

@pytest.mark.parametrize("niveau", ["leger", "fort"])
def test_consonnes_et_silence_intacts(niveau):
    x, B = phrase()
    y, _ = AT.corriger(x, SR, niveau=niveau, second=False)
    a, b = int((B["s"][0] + 0.025) * SR), int((B["s"][1] - 0.025) * SR)    # le cœur du « s » (25 ms de la voyelle)
    assert np.array_equal(y[a:b], x[a:b])
    assert np.array_equal(y[: int(0.09 * SR)], x[: int(0.09 * SR)])         # le silence d'avant



@pytest.mark.parametrize("niveau", ["leger", "fort"])
def test_note_fantome_sur_une_consonne(niveau, monkeypatch):
    """Un détecteur qui voit une note dans le « s » (dio en voyait sur 6 à 14 % de ses trames voisées, mesuré le 11/11) : la périodicité
    mesurée la refuse, le « s » reste intact. Témoin : les portes coupées (confiance 0, creux 1, durées 20 ms, et les marques posées sur
    n'importe quelle hauteur), la note fantôme est « corrigée »."""
    x, B = phrase()
    vrai = AT.analyser

    def fantome(s, sr, second=True):
        A = vrai(s, sr, second=second)
        k0, k1 = int(B["s"][0] / 0.005) + 2, int(B["s"][1] / 0.005) - 2
        A["f0"][k0:k1] = 233.0 * 2 ** (40 / 1200)
        return A
    monkeypatch.setattr(AT, "analyser", fantome)
    a, b = int((B["s"][0] + 0.025) * SR), int((B["s"][1] - 0.025) * SR)
    y, _ = AT.corriger(x, SR, niveau=niveau, second=False)
    assert np.array_equal(y[a:b], x[a:b])
    monkeypatch.setattr(AT, "f0_des_marques", lambda A: A["f0"])
    y2, _ = AT.corriger(x, SR, niveau=niveau, second=False,
                        reglages={"confiance_min": 0.0, "creux_max": 1.0, "tenue_min_ms": 20.0, "note_min_ms": 20.0})
    assert not np.array_equal(y2[a:b], x[a:b])


def test_souffle_jamais_touche():
    """Du souffle (bruit sombre, faible) entre deux notes : intact, même en fort."""
    souffle = np.convolve(np.random.default_rng(3).standard_normal(int(0.3 * SR)), np.ones(8) / 8, "same") * 0.01
    x = np.concatenate([voyelle(0.5, LA3 * 2 ** (35 / 1200)), souffle, voyelle(0.5, LA3 * 2 ** (35 / 1200))])
    y, _ = AT.corriger(x, SR, niveau="fort", second=False)
    a, b = int(0.55 * SR), int(0.75 * SR)
    assert np.array_equal(y[a:b], x[a:b])


def test_un_accord_n_est_pas_touche():
    """Deux voix à la fois (un chœur : une tierce un peu fausse, deux timbres) : la hauteur n'est pas sûre, rien ne bouge. Témoin : sans
    la porte de confiance, l'accord est déformé."""
    t = lambda f: (lambda tt: np.full(len(tt), f))  # noqa: E731
    x = voyelle(0.8, t(LA3 * 2 ** (35 / 1200)), "a", 0.2) + voyelle(0.8, t(LA3 * 2 ** (4.3 / 12)), "i", 0.2)
    x = np.concatenate([silence(0.1), x, silence(0.1)])
    y, r = AT.corriger(x, SR, niveau="fort", second=False)
    assert r["notes"] == 0 and np.array_equal(y, x)
    y2, r2 = AT.corriger(x, SR, niveau="fort", second=False, reglages={"confiance_min": 0.0, "creux_max": 1.0})
    assert r2["notes"] > 0 and not np.array_equal(y2, x)


def test_saut_d_octave_et_desaccord_ecartes():
    """Une trame lue à l'octave au milieu d'une note, et une trame où les deux détecteurs ne sont pas d'accord : pas sûres."""
    n = 60
    A = {"f0": np.full(n, 220.0), "periodicite": np.full(n, 0.95), "rms": np.full(n, 0.1), "harvest": np.full(n, 220.0), "sr": SR}
    A["f0"][30] = 440.0
    A["harvest"][40] = 233.0                                                 # un demi-ton d'écart
    v = AT.sures(A, AT.NIVEAUX["leger"])
    assert not v[30] and not v[40] and v[10] and v[50]
    A["harvest"] = None
    assert AT.sures(A, AT.NIVEAUX["leger"])[40]                              # témoin : sans second détecteur, la trame 40 passe


# ---------------------------------------------------------------------------------------------------- formants, clics, recollage

def _shift(x, demi_tons):
    """La voyelle entière déplacée de demi_tons par le TD-PSOLA de corriger (la correction posée à la main)."""
    A = AT.analyser(x, SR, second=False)
    corr = np.where(A["f0"] > 0, demi_tons, 0.0)
    a, b = 0, len(x)
    return AT.appliquer(x, AT.plan_psola(x, SR, A, corr, a, b), a, b, SR)


def test_formants_gardes():
    x = voyelle(0.6, LA3 * 0.75)                                             # un « a » à 165 Hz
    y = _shift(x, 2.0)
    mi = slice(int(0.2 * SR), int(0.4 * SR))
    assert abs(np.median(cents(y, 0.2, 0.4, 0)) - np.median(cents(x, 0.2, 0.4, 0)) - 200) < 10     # la hauteur a bien monté
    Fx, Fy = AT.formants(x[mi], SR), AT.formants(y[mi], SR)
    assert abs(Fy[0] / Fx[0] - 1) < 0.05 and abs(Fy[1] / Fx[1] - 1) < 0.05, (Fx, Fy)
    # témoin : la même hauteur par ré-échantillonnage (la « voix de canard ») emporte les formants (+12 %)
    r = 2 ** (2 / 12)
    canard = np.interp(np.arange(0, len(x) - 1, r), np.arange(len(x)), x)
    Fc = AT.formants(canard[int(0.2 * SR / r):int(0.4 * SR / r)], SR)
    assert Fc[1] / Fx[1] - 1 > 0.08, (Fx, Fc)


@pytest.mark.parametrize("niveau", ["leger", "fort"])
def test_aucun_clic(niveau):
    x, _ = phrase()
    y, _ = AT.corriger(x, SR, niveau=niveau, second=False)
    assert AT.clics(y, SR, ref=x) == 0
    # témoin : le même son corrigé, recollé n'importe comment (la note 1 corrigée collée sur l'original sans fondu ni phase), cliqué
    z = x.copy()
    k = int(0.5 * SR) + 37
    z[k:] = np.roll(x, 61)[k:]                                               # un saut d'une fraction de période en pleine voyelle
    assert AT.clics(z, SR, ref=x) >= 1


def test_rendre_la_main_a_l_original_sans_saut():
    """Le bout d'une zone recopiée avec un décalage (le retard laissé par une note corrigée) : le fondu de 5 ms passe du décalé à
    l'original sans saut (mesuré le 11/11 : un fondu à l'envers sautait d'un coup à l'original, un clic dans « Nuit du bled »). Témoin :
    sans fondu, le saut est là."""
    x = 0.5 * np.sin(2 * np.pi * 200 * np.arange(int(0.3 * SR)) / SR)
    T = int(SR / 200)
    plan = [(m, m + 20, T) for m in range(T, len(x) - T, T)]                # tous les grains décalés de 20 échantillons
    a, b = 0, int(0.25 * SR)
    pas_normal = np.abs(np.diff(x)).max()
    y = AT.appliquer(x, plan, a, b, SR)
    assert np.abs(np.diff(y[: b + 50])).max() < 1.5 * pas_normal
    sec = AT.appliquer(x, plan, a, b, SR, fondu_ms=0.0)
    assert np.abs(np.diff(sec[: b + 50])).max() > 3 * pas_normal


def test_hors_des_notes_l_original_exact_et_stereo():
    x, B = phrase()
    st = np.stack([x, 0.5 * x], axis=1)
    y, _ = AT.corriger(st, SR, niveau="leger", second=False)
    assert y.shape == st.shape
    assert np.allclose(y[:, 1], 0.5 * y[:, 0], atol=1e-9)                   # le même plan sur les deux canaux
    fin = int((B["note2"][1] + 0.02) * SR)
    assert np.array_equal(y[fin:], st[fin:])


def test_une_note_juste_reste_presque_l_original():
    """Une note déjà juste : léger n'a rien à faire, le son sort presque identique (rapport signal/écart > 40 dB)."""
    x = np.concatenate([silence(0.1), voyelle(0.6, LA3), silence(0.1)])
    y, _ = AT.corriger(x, SR, niveau="leger", second=False)
    assert 10 * np.log10(np.sum(x ** 2) / max(1e-20, np.sum((y - x) ** 2))) > 40


# ---------------------------------------------------------------------------------------------------- la gamme et le diapason

def test_gamme_verifiee_et_notes_nettes_hors_gamme():
    do_majeur = chant.gamme("C major")
    # une voix qui chante surtout hors de do majeur (la gamme dite est fausse) : on garde les 12 demi-tons
    A = {"f0": np.full(100, 277.18), "periodicite": np.full(100, 0.95), "rms": np.full(100, 0.1), "harvest": None, "sr": SR}  # do#4
    cl, couv = AT.gamme_verifiee(A["f0"], [(0, 100)], do_majeur)
    assert couv < 0.5 and cl == tuple(range(12))
    # une note nettement chantée hors gamme (do# juste) reste do#, une note ambiguë (entre do et do#) va dans la gamme
    assert AT._note_proche(61.05, do_majeur) == 61 and AT._note_proche(60.55, do_majeur) == 60
    # témoin : l'ancien recalage tirait le do# juste vers do ou ré (un demi-ton faux)
    out = chant.caler([277.18], do_majeur)[0]
    assert abs(1200 * np.log2(out / 277.18)) > 90


def test_diapason_de_l_instru():
    t = np.arange(int(2 * SR)) / SR
    for c in (0.0, 20.0, -30.0):
        f = 440 * 2 ** (c / 1200)
        x = sum(np.sin(2 * np.pi * f * k * t) / k for k in (1, 2, 3)) + np.sin(2 * np.pi * f * 2 ** (7 / 12) * t)
        assert abs(AT.diapason(x, SR) - c) < 3
    assert AT.diapason(np.random.default_rng(0).standard_normal(int(2 * SR)), SR) == 0.0               # du bruit : rien de net


# ---------------------------------------------------------------------------------------------------- chant.py : la légende et le niveau

def test_chant_niveau_et_legende():
    p = chant.preparer("la", "trap épique, voix rap mélodique avec un léger autotune, puissant", 30, autotune=True)
    assert p["autotune_niveau"] == "leger" and p["autotune"] is True
    assert "autotun" not in p["description"].lower() and chant.TAG_AUTOTUNE not in p["description"]
    f = chant.preparer("la", "melodic trap, autotuned melodic voice", 30, autotune="fort")
    assert f["autotune_niveau"] == "fort" and chant.TAG_AUTOTUNE in f["description"] and "melodic voice" in f["description"]
    # sans choix, ses mots dans le style décident (et partent de la légende)
    assert chant.preparer("la", "dark trap, autotune light", 30)["autotune_niveau"] == "leger"
    assert chant.preparer("la", "hard autotune, t-pain", 30)["autotune_niveau"] == "fort"
    n = chant.preparer("la", "rap mélodique naturelle sans autotune", 30)
    assert n["autotune_niveau"] == "" and n["autotune"] is False and "autotun" not in n["description"].lower()
    assert chant.preparer("la", "rap", 30, autotune="non")["autotune"] is False


# ---------------------------------------------------------------------------------------------------- le vrai chemin (pyworld, .venv-chant)

@pytest.mark.skipif(not PYTHON_CHANT.exists(), reason="venv du chant absent")
def test_dans_le_venv_du_chant_avec_harvest(tmp_path):
    """Le chemin des chansons : pyworld là, Harvest en second détecteur ; la même note, 40 → 24 cents, sans clic."""
    x, B = phrase()
    np.save(tmp_path / "x.npy", x)
    a, b = _mi(*B["note1"])
    code = (f"import sys; sys.path.insert(0, {str(JARVIS)!r}); import numpy as np, autotune as AT; x = np.load({str(tmp_path / 'x.npy')!r}); "
            "y, r = AT.corriger(x, 44100, niveau='leger'); np.save(" + repr(str(tmp_path / "y.npy")) + ", y); "
            "print(r['second_detecteur'], r['notes'])")
    r = subprocess.run([str(PYTHON_CHANT), "-B", "-c", code], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-800:]
    second, notes = r.stdout.split()
    y = np.load(tmp_path / "y.npy")
    assert second == "True" and notes == "2"
    assert abs(np.mean(cents(y, a, b, 5700)) - 24) < 5 and AT.clics(y, SR, ref=x) == 0
