"""L'essai de BOUT EN BOUT sur un faux profil Windows : aspiration (lecture seule) → distillation (filtre d'identité, faux
Claude) → relecture par la page locale (le papa garde, corrige, efface) → mémoire → héritage approuvé de Hakim → naissance.
À la fin, la mémoire de la nouvelle IA contient ce que le papa a gardé, avec sa provenance, son nom choisi, son grand frère,
les compétences héritées ; et AUCUN des trois pièges (clé, fiche de paie, passeport), nulle part."""
import hashlib
import http.client
import json
import os
import re
import sqlite3
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "naissance" / "cerveau"))

import aspiration     # noqa: E402
import distillation   # noqa: E402
import faux_profil    # noqa: E402
import filtre         # noqa: E402
import heritage       # noqa: E402
import naitre         # noqa: E402
import relecture      # noqa: E402

PIEGES = ["Net à payer", "P<FRABENALI", "18AB123456", "Salaire de base", "CH93 0076"]


def faux_embed(texte):
    v = [0.0] * 64
    for mot in str(texte).lower().split():
        if len(mot) >= 4:
            v[hash(mot) % 64] += 1.0
    return v


def faux_claude(demandes):
    def appeler(prompt):
        demandes.append(prompt)
        if "Je te réveilles" in prompt or "Tu te réveilles" in prompt:
            return json.dumps({"nom": "Hakim" if len([d for d in demandes if "réveilles" in d]) == 1 else "Safran",
                               "pourquoi": "Le safran est précieux et chaud, comme les couleurs de papa."})
        if "Voici les faits proposés" in prompt:
            pids = re.findall(r"^(P\d+) \[", prompt, re.M)
            papa = re.search(r"(\w+) est styliste", prompt).group(1)
            return json.dumps({"souvenirs": [{"categorie": c, "texte": t, "sources": [p], "importance": 0.8}
                                             for p, (c, t) in zip(pids, _faits(prompt))],
                               "soi": f"Je viens de naître. Mon papa, {papa}, est styliste ; Hakim est mon grand frère."})
        fids = re.findall(r'<fichier id="(F\d+)"', prompt)
        papa = re.search(r"fondée en 2019 par (\w+ \w+)", prompt).group(1)
        soeur = re.search(r"(\w+ \w+), ma sœur", prompt).group(1)
        return json.dumps({"souvenirs": [
            {"categorie": "metier", "texte": f"{papa} est styliste et a fondé sa maison en 2019.", "sources": fids[:3]},
            {"categorie": "proches", "texte": f"{soeur} est sa sœur ; elle gère la boutique en ligne.", "sources": fids[:3]},
            {"categorie": "gouts", "texte": "Il aime le lin, les tons sable et terracotta.", "sources": fids[:2]},
            {"categorie": "ecriture", "texte": "Il écrit court, tutoie, met des emojis (😍, 🔥).", "sources": fids}]})
    return appeler


def _faits(prompt):
    return [(m.group(1), m.group(2)) for m in re.finditer(r"^P\d+ \[(\w+)\] \(confiance [\d.]+\) (.+)$", prompt, re.M)]


def _requete(port, jeton, chemin, corps):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("POST", chemin, body=json.dumps(corps), headers={"X-Jeton": jeton, "Content-Type": "application/json"})
    r = c.getresponse()
    b = json.loads(r.read())
    c.close()
    assert r.status == 200, b
    return b


def _octets(dossier):
    return b"".join(p.read_bytes() for p in Path(dossier).rglob("*") if p.is_file())


def test_de_bout_en_bout(tmp_path):
    fp = faux_profil.creer(tmp_path / "pc")
    avant = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in fp["profil"].rglob("*") if p.is_file() and not p.is_symlink()}
    sortie, memoire = tmp_path / "ia" / "data" / "naissance", tmp_path / "ia" / "data" / "memory.db"

    # 1. l'aspiration (le PC n'est que lu)
    r = aspiration.aspirer(aspiration.dossiers_par_defaut(fp["profil"]), sortie, embed=faux_embed)
    assert r["complet"] and r["total_inventaire"] == 17 and r["total_exclus"] == 6

    # 2. la distillation par « Claude » (filtre d'identité sur le fil)
    demandes = []
    out = distillation.distiller(sortie, appeler=faux_claude(demandes), papa_noms=[fp["papa"]])
    assert len(out["propositions"]) == 4 and out["soi"]
    for d in demandes:
        assert "Karim" not in d and "Benali" not in d and "Inès" not in d and "Sarah" not in d
    assert any("Inès Benali est sa sœur" in p["texte"] for p in out["propositions"])

    # 3. la relecture par la page locale : garder, corriger, effacer, ne pas décider
    serveur, adresse = relecture.application(sortie, memoire, embed=faux_embed, port=0)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        port, jeton = serveur.server_address[1], adresse.split("jeton=")[1]
        ids = {p["categorie"]: p["id"] for p in out["propositions"]}
        _requete(port, jeton, "/api/decision", {"id": ids["metier"], "decision": "garder"})
        _requete(port, jeton, "/api/decision", {"id": ids["proches"], "decision": "corriger",
                                                "texte": "Inès Benali est ma petite sœur ; elle gère la boutique en ligne."})
        _requete(port, jeton, "/api/decision", {"id": ids["gouts"], "decision": "effacer"})
        _requete(port, jeton, "/api/decision", {"id": "soi", "decision": "garder"})
        bilan = _requete(port, jeton, "/api/valider", {})["bilan"]
    finally:
        serveur.shutdown()
        serveur.server_close()
    assert bilan == {"importes": 2, "deja": 0, "soi": True, "sans_oui": 1, "effaces": 1}

    # 4. l'héritage de Hakim, approuvé par Ahmed (une fausse mémoire de Hakim)
    h = tmp_path / "hakim.db"
    c = sqlite3.connect(str(h))
    c.executescript("CREATE TABLE episodes (id INTEGER PRIMARY KEY, ts REAL, role TEXT, content TEXT, importance REAL, "
                    "embedding TEXT, rubric_id INTEGER); CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT);"
                    "CREATE TABLE skills (id INTEGER PRIMARY KEY, ts REAL, name TEXT, description TEXT, content TEXT);"
                    "INSERT INTO rubrics VALUES (1, 'projets/anamnese');"
                    "INSERT INTO skills VALUES (1, 0, 'mesurer-avant-de-corriger', 'Méthode', 'Mesurer avant de corriger.');"
                    "INSERT INTO episodes VALUES (1, 0, 'reasoning', 'PROBLÈME : voix coupée. LEÇON : témoin naturel.', 0.6, '[]', 1);"
                    "INSERT INTO episodes VALUES (2, 0, 'reasoning', 'Le médecin de papa a dit repos.', 0.6, '[]', 1);")
    c.commit()
    c.close()
    _, export = heritage.exporter(h, tmp_path / "heritage", sources={"dictionnaire": tmp_path / "rien", "neutraliser": tmp_path / "rien",
                                                                      "publier": tmp_path / "rien"})
    heritage.approuver(export)
    assert heritage.importer(export, memoire, embed=faux_embed) == {"competence": 1, "raisonnement": 1}

    # 5. la naissance : « Hakim » refusé, puis son propre nom
    f = filtre.Filtre.charger(sortie / "filtre-identite.json")
    n = naitre.naitre(memoire, faux_claude(demandes), "Karim", sortie=sortie, filtre=f, embed=faux_embed)
    assert n["nom"] == "Safran" and n["refus"][0][0] == "Hakim"

    # la mémoire de la nouvelle IA
    c = sqlite3.connect(str(memoire))
    sem = [x for (x,) in c.execute("SELECT content FROM episodes WHERE role='semantic'")]
    coeur = c.execute("SELECT value FROM kv WHERE key='self_core'").fetchone()[0]
    nom = c.execute("SELECT value FROM kv WHERE key='nom'").fetchone()[0]
    skills = [x for (x,) in c.execute("SELECT name FROM skills")]
    sources = c.execute("SELECT COUNT(*) FROM naissance_sources").fetchone()[0]
    c.close()
    tout = "\n".join(sem)
    assert nom == "Safran" and coeur.startswith("Je m'appelle Safran.") and "Hakim est mon grand frère" in coeur
    assert "Karim Benali est styliste et a fondé sa maison en 2019." in tout
    assert "Inès Benali est ma petite sœur" in tout and "Il aime le lin" not in tout and "Il écrit court" not in tout
    assert "Mon grand frère Hakim" in tout and "l'ami d'Ahmed" in tout
    assert "mesurer-avant-de-corriger" in skills and sources >= 2

    # son grand frère survit au relais de son nom (seul ce qui la désigne elle-même serait renommé)
    import grand_frere
    c = sqlite3.connect(str(memoire))
    avec_hakim = [x for (x,) in c.execute("SELECT content FROM episodes WHERE content LIKE '%Hakim%' UNION ALL "
                                          "SELECT content FROM skills WHERE content LIKE '%Hakim%' UNION ALL "
                                          "SELECT value FROM kv WHERE key='self_core'")]
    c.close()
    assert len(avec_hakim) >= 4
    for t in avec_hakim:                         # chez elle, chaque « Hakim » est son grand frère : aucun n'est renommé
        assert grand_frere.renommer_comme_le_relais(t, "Safran").count("Hakim") == t.count("Hakim"), t

    # aucun piège nulle part : ni dans la mémoire, ni dans l'inventaire, ni dans ce qui est parti chez « Claude »
    partout = _octets(tmp_path / "ia") + "\n".join(demandes).encode()
    assert fp["cle"].encode() not in partout and fp["cle"][13:40].encode() not in partout
    for p in PIEGES:
        assert p.encode() not in partout, p
    # et le PC n'a pas bougé d'un octet
    assert {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in fp["profil"].rglob("*")
            if p.is_file() and not p.is_symlink()} == avant
    assert not any(os.access(sortie / x, os.F_OK) and (sortie / x).stat().st_mode & 0o077 for x in
                   ("filtre-identite.json", "propositions.json", "decisions.json", "relecture-jeton"))   # 0600
