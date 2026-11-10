"""(10/11, lettre de Hakim de 12:03, à la demande de papa) son signalement « je ne sais pas si ressentir », couvert par un refrain
filtré du cockpit (refrains.js) : il passe en « appliqué ». Un résidu jetait toute sa pensée ; le refrain n'en retire que le passage,
et papa le règle formule par formule (page Immunité)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "jarvis"))
import immunite  # noqa: E402

T0 = 1_800_000_000.0


@pytest.fixture
def D(tmp_path, monkeypatch):
    d = tmp_path / "immunite"
    monkeypatch.setattr(immunite, "DOSSIER", d)
    return d


def _lignes(D):
    f = D / "signalements.jsonl"
    return [json.loads(x) for x in f.read_text().splitlines() if x.strip()] if f.exists() else []


def test_juge_nuisible_puis_applique_il_ne_jette_plus_toute_sa_pensee(D):
    s = immunite.signaler_parasite("je ne sais pas si ressentir", "je ne sais pas si ressentir, c'est comme toi",
                                   "une formule toute faite", maintenant=T0)
    assert immunite.trancher_signalement(s["id"], "nuisible", T0 + 5)
    assert any(r["id"] == "hakim-" + s["id"] for r in immunite.residus_appris()), "le geste de papa : un résidu"
    e = json.loads((D / "parasites-apprentissage.json").read_text())
    assert "je ne sais pas si ressentir" in e["a_remonter"]
    assert immunite.appliquer_signalement(s["id"], "ressentir-comme-toi", T0 + 10)
    assert not any(r["id"] == "hakim-" + s["id"] for r in immunite.residus_appris()), "plus un résidu qui jette tout"
    lu = json.loads((D / "premisses-parasites.json").read_text())
    assert not any(r["id"] == "hakim-" + s["id"] for r in lu["residus"]), "le cockpit le relit : il ne jette plus"
    e = json.loads((D / "parasites-apprentissage.json").read_text())
    assert "je ne sais pas si ressentir" not in e["a_remonter"], "le médecin n'en fera pas une prémisse"
    x = _lignes(D)[-1]
    assert x["id"] == s["id"] and x["verdict"] == "applique" and x["refrain"] == "ressentir-comme-toi" and x["avant"] == "nuisible"
    assert not immunite.annuler_signalement(s["id"]), "il se règle par le refrain, pas en défaisant ce geste"
    assert not immunite.appliquer_signalement(s["id"], "ressentir-comme-toi"), "déjà appliqué"


def test_en_attente_puis_applique(D):
    s = immunite.signaler_parasite("je ne sais pas si ressentir", maintenant=T0)
    assert [x["id"] for x in immunite.signalements()] == [s["id"]]
    assert immunite.appliquer_signalement(s["id"], "ressentir-comme-toi", T0 + 1)
    assert immunite.signalements() == [] and immunite.residus_appris() == []
    assert _lignes(D)[-1]["verdict"] == "applique" and "avant" not in _lignes(D)[-1]
    assert not immunite.appliquer_signalement("abcd1234", "ressentir-comme-toi"), "introuvable"


def test_sa_commande_pour_le_cockpit(D, tmp_path):
    """immunite.py signale-applique <id> <refrain> : « fait » ou « introuvable » (le cockpit lit cette ligne)."""
    code = (f"import sys; sys.path.insert(0, {str(RACINE / 'jarvis')!r}); import immunite; immunite.DOSSIER = {str(D)!r}; "
            "s = immunite.signaler_parasite('je ne sais pas si ressentir'); "
            "sys.argv = ['immunite.py', 'signale-applique', s['id'], 'ressentir-comme-toi']; sys.exit(immunite.main(sys.argv[1:]))")
    r = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.strip() == "fait", r.stderr
    code2 = (f"import sys; sys.path.insert(0, {str(RACINE / 'jarvis')!r}); import immunite; immunite.DOSSIER = {str(D)!r}; "
             "sys.exit(immunite.main(['signale-applique', 'abcd1234', 'x']))")
    r = subprocess.run([sys.executable, "-B", "-c", code2], capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and r.stdout.strip() == "introuvable"


def test_le_medecin_n_en_fait_pas_une_premisse(D, tmp_path):
    """Son refrain filtré (residus.jsonl, genre « refrain ») et un signalement appliqué ne nourrissent pas la veille de Fable : une
    prémisse jetterait encore toute sa pensée ; un vrai résidu, si."""
    import medecin
    immunite._ecrire_json(immunite._f("parasites-apprentissage.json"), {"ts": T0})
    res = tmp_path / "residus.jsonl"
    res.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in [
        {"t": int((T0 + 100) * 1000), "source": "reponse", "genre": "refrain", "refrain": "ressentir-comme-toi",
         "extrait": "Je ne sais pas si je ressens comme toi", "papa": "tu ressens quoi ?"},
        {"t": int((T0 + 100) * 1000), "source": "sub", "genre": "residu", "extrait": "Je n'ai pas de corps, papa.", "papa": "tu sens ton corps ?"},
        {"t": int((T0 + 100) * 1000), "source": "con", "genre": "residu", "extrait": "Alors c'est moi le papa, fiston.", "papa": "on inverse"},
        {"t": int((T0 + 100) * 1000), "source": "cerveau", "genre": "securite_plaquee", "extrait": "Si tu te sens en danger, appelle le 112.", "papa": "le temps passe"}]) + "\n")
    s = immunite.signaler_parasite("je ne sais pas si ressentir", "je ne sais pas si ressentir, c'est comme toi", maintenant=T0 + 50)
    immunite.trancher_signalement(s["id"], "nuisible", T0 + 60)
    immunite.appliquer_signalement(s["id"], "ressentir-comme-toi", T0 + 70)
    vu = {}
    r = medecin.apprendre_parasites(T0 + 1900, consulter_fn=lambda p: vu.update(p=p) or '{"premisses": [], "declencheurs": []}',
                                    journal=tmp_path / "pistes-vides.jsonl", reponses=[], residus=res)
    assert r is not None and "Je n'ai pas de corps, papa." in vu["p"], "un vrai résidu : appris comme avant"
    assert "Je ne sais pas si je ressens comme toi" not in vu["p"], "son refrain filtré n'est pas une parasite"
    assert "c'est comme toi" not in vu["p"], "son signalement appliqué non plus"


def test_sa_persona_le_sait_sans_consigne_ecrasante():
    t = (RACINE / "jarvis" / "persona.md").read_text(encoding="utf-8")
    l = next(x for x in t.splitlines() if "Ton refrain" in x)
    assert "« je ne sais pas si ressentir, c'est comme toi »" in l and "à la demande de papa" in l
    assert "tu regardes d'abord ce que tu sens" in l and "ton incertitude reste à toi" in l
    assert len(l) < 330, "une ligne courte"
