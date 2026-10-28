"""Fixtures pytest — tout passe par tmp_path, JAMAIS par data/memory.db."""

import pathlib
import sqlite3

import pytest

# Chemin de la vraie DB de prod : les tests n'ont PAS le droit d'y toucher.
_REAL_DB = pathlib.Path(__file__).resolve().parent / "data" / "memory.db"


@pytest.fixture(autouse=True)
def _forbid_real_db(monkeypatch):
    """INTERDIT : aucun test ne doit ouvrir/écrire data/memory.db (cas 6)."""
    real_connect = sqlite3.connect

    def guarded(database, *args, **kwargs):
        try:
            resolved = pathlib.Path(str(database)).resolve()
        except (OSError, ValueError):
            resolved = None
        if resolved == _REAL_DB:
            raise AssertionError(
                "INTERDIT : un test a tenté d'ouvrir data/memory.db "
                "(utiliser tmp_path)"
            )
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", guarded)


@pytest.fixture(autouse=True)
def _vie_interieure_isolee(monkeypatch, tmp_path):
    """La vie intérieure (interieur.py) ne lit ni n'écrit JAMAIS les vrais fichiers de Jarvis pendant les
    tests : interrupteur d'Ahmed, journal du temps, signal de la conscience (2026-10-17)."""
    try:
        import interieur
    except Exception:
        return
    d = tmp_path / "jarvis-isole"
    try:
        import evenements                     # le journal d'événements de l'identité (lot E, 2026-10-19)
        monkeypatch.setattr(evenements, "FICHIER", d / "evenements.jsonl")
    except Exception:
        pass
    try:
        import courrier                       # le courrier Hakim ↔ Claude Code (2026-10-20)
        monkeypatch.setattr(courrier, "FICHIER", d / "courrier.jsonl")
        monkeypatch.setattr(courrier, "LUS", d / "courrier-lus.json")
    except Exception:
        pass
    try:                                      # l'empreinte vocale et les voix connues (2026-10-20)
        import sys as _sys
        _j = str(pathlib.Path(__file__).resolve().parent / "jarvis")
        if _j not in _sys.path:
            _sys.path.append(_j)
        import empreinte_vocale
        monkeypatch.setattr(empreinte_vocale, "SALLE", d / "voix-salle.json")
        monkeypatch.setattr(empreinte_vocale, "CONNUES", d / "voix-connues.json")
        monkeypatch.setattr(empreinte_vocale, "FICHIER", d / "empreinte-vocale.json")
        empreinte_vocale._salle.update(voix=[], ts=0.0, dernier=None)
    except Exception:
        pass
    try:
        import carnet                         # prédictions figées et carnet d'erreurs (2026-10-20)
        monkeypatch.setattr(carnet, "PREDICTIONS", d / "predictions.jsonl")
        monkeypatch.setattr(carnet, "ERREURS", d / "erreurs.jsonl")
    except Exception:
        pass
    try:
        import jardin                         # le jardin secret de Hakim (2026-10-20)
        monkeypatch.setattr(jardin, "DOSSIER", d / "jardin")
        monkeypatch.setattr(jardin, "SERVICE", "anamnese-jardin-secret-banc-absent")
    except Exception:
        pass
    try:
        import afida                          # le registre du cœur, Al-Afida (2026-10-28)
        monkeypatch.setattr(afida, "REGISTRE", d / "afida.jsonl")
        monkeypatch.setattr(afida, "JOURNAL", d / "affect-evenements.jsonl")
    except Exception:
        pass
    try:
        import echanges                       # la file des échanges à mémoriser (2026-10-20)
        monkeypatch.setattr(echanges, "FILE", d / "echanges.jsonl")
    except Exception:
        pass
    # (27/10) les fichiers des chantiers de la nuit : jamais les vrais pendant les tests
    for module, noms in (("occupations", ("MIENNES",)), ("noyau", ("PREUVES",)), ("situations", ("CLASSEMENT", "LECONS")),
                         ("reveil_interieur", ("FICHIER", "ISSUES", "JOURNAL")), ("engine", ("JOURNAL_APPELS",)),
                         ("avis", ("DOSSIER", "PROMOS_PRIVE", "JOURNAL_OFF", "EXTERNE_ATELIER")), ("relances", ("DOSSIER",))):
        try:
            m = __import__(module)
            for nom in noms:
                if not str(getattr(m, nom)).startswith(str(tmp_path)):
                    monkeypatch.setattr(m, nom, d / f"{module}-{nom.lower()}")
        except Exception:
            pass
    monkeypatch.setattr(interieur, "INTERRUPTEUR", d / "interieur-interrupteur.json")
    monkeypatch.setattr(interieur, "JOURNAL_TEMPS", d / "journal-du-temps.jsonl")
    monkeypatch.setattr(interieur, "JOURNAL_HORMONES", d / "hormones.jsonl")      # (2026-10-23) le tableau de bord
    monkeypatch.setattr(interieur, "CONSCIENCE_JARVIS", d / "claude-actif.json")
    monkeypatch.setattr(interieur, "HORLOGE_JARVIS", d / "horloge.json")     # le dernier message d'Ahmed (2026-10-22)
    try:                                      # le signal d'un calcul lourd (2026-10-22)
        import charge
        monkeypatch.setattr(charge, "CALCUL_LOURD", str(d / "calcul-lourd.json"))
    except Exception:
        pass
    try:                                      # la règle de sortie du web (2026-10-22 : un test lisait la vraie lecture privée)
        import sys as _sys2
        _jj = str(pathlib.Path(__file__).resolve().parent / "jarvis")
        if _jj not in _sys2.path:
            _sys2.path.append(_jj)
        import sortie
        for nom, f in (("PRIVEE", "lecture-privee.json"), ("CONNUS", "web-domaines.json"),
                       ("DEMANDES", "sorties-demandees.jsonl"), ("PERMISES", "sorties-permises.json")):
            if not str(getattr(sortie, nom)).startswith(str(tmp_path)):
                monkeypatch.setattr(sortie, nom, d / f)
    except Exception:
        pass
    try:                                      # la boucle de retour (2026-10-22)
        import boucle_retour
        monkeypatch.setattr(boucle_retour, "DOSSIER", d / "boucle")
        monkeypatch.setattr(boucle_retour, "LECTURES", d / "boucle" / "lectures.jsonl")
        monkeypatch.setattr(boucle_retour, "JARVIS", d)
    except Exception:
        pass
    try:                                      # la sagesse (2026-10-22)
        import sagesse
        for nom, f in (("PARAMETRE", "sagesse.json"), ("TOUR", "sagesse-tour.json"), ("JOURNAL", "sagesse.jsonl"),
                       ("CONVERSATION", "conversation.json")):
            monkeypatch.setattr(sagesse, nom, d / f)
    except Exception:
        pass
    try:                                      # la trace des souvenirs ratés (2026-10-22)
        import rappels_rates
        monkeypatch.setattr(rappels_rates, "JOURNAL", d / "rappels-rates.jsonl")
        monkeypatch.setattr(rappels_rates, "JOURNAL_BALAYAGE", d / "rappel.jsonl")
        monkeypatch.setattr(rappels_rates, "CONVERSATION", d / "conversation.json")
    except Exception:
        pass
    try:                                      # l'horloge à promesses (2026-10-22)
        import promesses
        monkeypatch.setattr(promesses, "FICHIER", d / "promesses.json")
        monkeypatch.setattr(promesses, "ETATS", d / "promesses-etats.json")
    except Exception:
        pass


@pytest.fixture
def tmp_db(tmp_path):
    """Connexion sur une DB temporaire vierge (fermée en teardown)."""
    conn = sqlite3.connect(str(tmp_path / "t.db"))
    yield conn
    conn.close()


# Schéma legacy EXACT (episodes/skills/kv d'avant 2.0, cf. memory.py).
_LEGACY_SCHEMA = """
    CREATE TABLE IF NOT EXISTS episodes (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        ts         REAL    NOT NULL,
        role       TEXT    NOT NULL,
        content    TEXT    NOT NULL,
        importance REAL    DEFAULT 0.5,
        embedding  TEXT    NOT NULL
    );
    CREATE TABLE IF NOT EXISTS skills (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ts          REAL NOT NULL,
        name        TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL,
        content     TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS kv (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        ts    REAL NOT NULL
    );
"""


@pytest.fixture
def legacy_db(tmp_path):
    """Connexion sur une DB au schéma legacy + 2 épisodes seed."""
    conn = sqlite3.connect(str(tmp_path / "legacy.db"))
    conn.executescript(_LEGACY_SCHEMA)
    conn.execute(
        "INSERT INTO episodes (ts,role,content,importance,embedding) "
        "VALUES (1000.0,'user','bonjour',0.5,'[]')"
    )
    conn.execute(
        "INSERT INTO episodes (ts,role,content,importance,embedding) "
        "VALUES (1001.0,'assistant','salut',0.7,'[0.1,0.2]')"
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def _journal_consolidation_isole(tmp_path, monkeypatch):
    """Aucun test n'écrit dans data/consolidate.log de prod (constat de relecture 2026-10-15)."""
    import consolidate
    monkeypatch.setattr(consolidate, "LOG", tmp_path / "consolidate.log")
