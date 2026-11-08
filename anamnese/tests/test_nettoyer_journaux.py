"""Le nettoyage des journaux déjà écrits (validé par Ahmed le 2026-10-20) : seules les chaînes à secret changent, les
autres lignes sont recopiées à l'identique, et le curseur du démon suit les fins de ligne."""
import json

import nettoyer_journaux as N


def test_nettoyer_octets():
    lignes = [{"ts": 1792440000000, "texte": "bonjour"},
              {"ts": 1792440000001, "texte": "mon mot de passe c'est Soleil2024"},
              {"ts": 1792440000002, "texte": "export GEMINI_API_KEY=AIzaSyA1234567890abcdefghijklmnopqrstuv"}]
    brut = "".join(json.dumps(l, ensure_ascii=False, separators=(",", ":")) + "\n" for l in lignes).encode()
    neuf, n, fins = N.nettoyer_octets(brut + b'{"incomplet"')
    assert n == 2
    sortie = neuf.decode().splitlines()
    assert sortie[0] == json.dumps(lignes[0], separators=(",", ":"))           # intacte
    assert "Soleil2024" not in sortie[1] and "AIzaSy" not in sortie[2] and sortie[3] == '{"incomplet"'
    premiere = len(json.dumps(lignes[0], separators=(",", ":"))) + 1
    assert fins[premiere] == premiere and fins[len(brut)] == len(neuf) - len(b'{"incomplet"')
