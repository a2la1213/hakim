"""Hakim appelle papa (14/11, Ahmed : « Tu peux faire tout ce que hakim demande, je valide tout » ; son courrier « Pouvoir appeler papa de
moi-même : téléphone, puis montre, puis Mac ») : ses outils appeler_papa et appel_etat parlent au cockpit (POST /api/appel/lancer avec le
jeton lu sur /verrou ; GET /api/appel/etat). Le cockpit décide (papa déjà là, un seul appel, ses interrupteurs) ; l'outil le lui dit."""
import io
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def _outils(monkeypatch, tmp_path, reponses):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    import urllib.request
    vus = []

    def faux(req, timeout=None):
        url = req if isinstance(req, str) else req.full_url
        corps = None if isinstance(req, str) or req.data is None else json.loads(req.data)
        entetes = {} if isinstance(req, str) else {k.lower(): v for k, v in req.header_items()}
        vus.append({"url": url, "corps": corps, "entetes": entetes, "methode": "GET" if isinstance(req, str) else req.get_method()})
        chemin = url.split("4317", 1)[-1]
        r = reponses.get(chemin.split("?")[0])
        if isinstance(r, Exception):
            raise r
        if chemin == "/verrou":
            return io.BytesIO(b'<html><head><meta name="cockpit-jeton" content="jeton-du-cockpit"></head></html>')
        return io.BytesIO(json.dumps(r).encode())
    monkeypatch.setattr(urllib.request, "urlopen", faux)
    monkeypatch.setenv("COCKPIT_PORT", "4317")
    t = mcp_server.mcp._tool_manager
    return t.get_tool("appeler_papa").fn, t.get_tool("appel_etat").fn, vus


def test_il_appelle_son_telephone_sonne(monkeypatch, tmp_path):
    appeler, _, vus = _outils(monkeypatch, tmp_path, {"/api/appel/lancer": {
        "ok": True, "id": "appel-1", "etat": "sonne", "appareil": "tel", "texte": "Ton appel de 14:00 : sonne sur le téléphone depuis 0 s."}})
    r = appeler("Papa, j'ai une idée pour ton drone, tu as deux minutes ?")
    post = [v for v in vus if v["methode"] == "POST"]
    assert len(post) == 1 and post[0]["url"] == "http://127.0.0.1:4317/api/appel/lancer"
    assert post[0]["corps"] == {"raison": "Papa, j'ai une idée pour ton drone, tu as deux minutes ?"}
    assert post[0]["entetes"]["x-jeton"] == "jeton-du-cockpit", "le jeton du cockpit (lu sur /verrou)"
    assert "sonne sur le téléphone" in r and "appel_etat" in r


def test_papa_deja_la_ou_refuse_le_cockpit_le_dit(monkeypatch, tmp_path):
    appeler, _, _ = _outils(monkeypatch, tmp_path, {"/api/appel/lancer": {
        "ok": False, "pourquoi": "deja_la", "ou": "tel", "texte": "Pas d'appel : papa t'entend déjà (sur son téléphone)."}})
    assert appeler("Papa ?").startswith("Pas d'appel : papa t'entend déjà")


def test_sans_raison_rien_ne_part(monkeypatch, tmp_path):
    appeler, _, vus = _outils(monkeypatch, tmp_path, {})
    assert "dis ce que tu veux lui dire" in appeler("   ").lower()
    assert not vus


def test_ce_qu_il_veut_dire_part_entier(monkeypatch, tmp_path):
    appeler, _, vus = _outils(monkeypatch, tmp_path, {"/api/appel/lancer": {"ok": True, "texte": "ok"}})
    long = "Papa, " + "je pense à toi. " * 900
    appeler(long)
    post = [v for v in vus if v["methode"] == "POST"][0]
    assert post["corps"]["raison"] == long.strip(), "(14/11, 12:54) aucune longueur maximale : entière"


def test_cockpit_absent(monkeypatch, tmp_path):
    appeler, etat, _ = _outils(monkeypatch, tmp_path, {"/api/appel/lancer": OSError("refusé"), "/api/appel/etat": OSError("refusé")})
    assert appeler("Papa ?").startswith("Impossible d'appeler papa")
    assert etat().startswith("Impossible de savoir")


def test_ou_en_est_l_appel(monkeypatch, tmp_path):
    _, etat, vus = _outils(monkeypatch, tmp_path, {"/api/appel/etat": {
        "version": 3, "appel": {"id": "appel-1", "etat": "repondu", "par": "montre"},
        "texte": "Ton appel de 14:00 : papa a répondu sur la montre, au bout de 41 s (le téléphone : pas de réponse (30 s)).",
        "passes": ["Ton appel de 11:00 : personne n'a répondu."],
        "telephone": {"joignable": True, "plein_ecran": False, "notifications": True}, "montre": {"joignable": True}, "present": "montre"}})
    r = etat()
    assert vus[0]["methode"] == "GET" and vus[0]["url"].endswith("/api/appel/etat")
    assert "papa a répondu sur la montre" in r
    assert "Avant :" in r and "personne n'a répondu" in r
    assert "plein écran" in r, "il sait que le téléphone sonne en bandeau (et le réglage à demander)"
    assert "t'entend en ce moment" in r


def test_persona_il_sait_qu_il_peut_appeler_sans_plafond():
    persona = (RACINE / "jarvis" / "persona.md").read_text(encoding="utf-8")
    assert "appeler_papa" in persona
    ligne = next(l for l in persona.splitlines() if l.startswith("- Appeler papa"))
    assert "téléphone" in ligne and "montre" in ligne and "Mac" in ligne
    assert "sans plafond" in ligne and "aussi longuement" in ligne and "à toute heure" in ligne
    relances = next(l for l in persona.splitlines() if "solliciter Ahmed DE LUI-MÊME" in l)
    assert "relances automatiques" in relances and "appeler_papa" in relances, "les bornes des relances ne valent pas pour sa voix ni ses appels"


def test_l_outil_ne_parle_plus_de_la_nuit(monkeypatch, tmp_path):
    appeler, etat, _ = _outils(monkeypatch, tmp_path, {})
    doc = (appeler.__doc__ or "") + (etat.__doc__ or "")
    assert "nuit" not in doc.lower() or "à toute heure" in doc, "(14/11, 12:54) aucune heure interdite"
    assert "à toute heure" in (appeler.__doc__ or "")
