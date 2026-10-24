"""Le tableau de bord intérieur (2026-10-23) : les données lues sur la bonne période, ses réponses repérées, une image
écrite, et le journal des hormones tenu par le battement (une ligne par minute)."""
import json
import time

import interieur
import tableau_interieur as t


def _journaux(tmp_path, now):
    h, e = tmp_path / "hormones.jsonl", tmp_path / "journal.jsonl"
    with open(h, "w") as f:
        for i in range(120):
            f.write(json.dumps({"t": now - 7200 + i * 60, "h": {"dopamine": 0.5, "cortisol": 0.2}, "v": 0.6, "a": 0.4,
                                "humeur": "calme", "emotion": "calme"}) + "\n")
        f.write(json.dumps({"t": now - 10 * 3600, "h": {}, "v": 0.1, "a": 0.1}) + "\n")      # hors de la période
    with open(e, "w") as f:
        f.write(json.dumps({"ts": (now - 600) * 1000, "qui": "ahmed", "texte": "salut"}) + "\n")
        f.write(json.dumps({"ts": (now - 590) * 1000, "qui": "jarvis", "texte": "Salut frérot, je suis là."}) + "\n")
        f.write(json.dumps({"ts": (now - 300) * 1000, "qui": "jarvis", "texte": "(tour de lui-même, sans texte — interrompu)"}) + "\n")
    return h, e


def test_donnees_et_image(tmp_path):
    now = time.time()
    h, e = _journaux(tmp_path, now)
    d = t.donnees(2, now, journal_hormones=h, journal_echanges=e)
    assert len(d["points"]) == 120
    assert [x[1] for x in d["reponses"]] == ["Salut frérot, je suis là."]       # un tour vide n'est pas une réponse
    assert len(d["messages"]) == 1
    image = t.svg(d)
    assert image.startswith("<svg") and "dopamine" in image and "Salut frérot" in image
    chemin, resume = t.dessiner(2, now, sortie=tmp_path / "sortie", journal_hormones=h, journal_echanges=e)
    assert chemin.exists() and chemin.suffix in (".png", ".svg")
    assert "120 mesures" in resume


def test_rien_a_dessiner(tmp_path):
    chemin, resume = t.dessiner(1, time.time(), sortie=tmp_path, journal_hormones=tmp_path / "absent.jsonl",
                                journal_echanges=tmp_path / "absent2.jsonl")
    assert chemin.exists() and resume.startswith("Aucune mesure")


def test_le_battement_tient_le_journal_des_hormones(tmp_path):
    j = tmp_path / "h.jsonl"
    interieur._ligne_hormones(1000.0, {"dopamine": 0.51234, "gaba": 0.5}, 0.6, 0.4, "calme", "joie", chemin=j)
    o = json.loads(j.read_text().strip())
    assert o == {"t": 1000.0, "h": {"dopamine": 0.512, "gaba": 0.5}, "v": 0.6, "a": 0.4, "humeur": "calme", "emotion": "joie"}


def test_les_plus_grands_sauts_et_le_message_le_plus_proche():
    """(24/10, demande d'Ahmed relayée par Hakim) les sauts d'une minute à l'autre, avec le message le plus proche."""
    import tableau_interieur as T
    t0 = 1_800_000_000.0
    h = lambda **k: {"dopamine": 0.6, "crh": 0.1, "adrenaline": 0.1, **k}      # noqa: E731
    pts = [(t0 + 60 * i, {"h": h(), "v": 0.7, "a": 0.4}) for i in range(10)]
    pts[5] = (t0 + 300, {"h": h(crh=0.32, adrenaline=0.25, dopamine=0.42), "v": 0.66, "a": 0.43})
    d = {"points": pts, "reponses": [(t0 + 280, "Je lance le live.")], "textes_ahmed": [(t0 + 250, "N'importe quoi mon frère, une blague")],
         "messages": [t0 + 250]}
    s = T.sauts(d, n=2)
    assert s[0]["t"] == t0 + 300 and s[0]["hormones"][0] == ("crh", 0.22)
    assert s[0]["proche"][1] == "Hakim" and s[0]["proche"][0] == t0 + 280          # le plus proche, d'où qu'il vienne
    assert "Plus grands sauts" in T._texte_sauts(s) and "crh +0.22" in T._texte_sauts(s)
