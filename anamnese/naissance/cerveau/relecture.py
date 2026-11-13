"""La RELECTURE OBLIGATOIRE (Ahmed, 13/11 : « rien ne devient mémoire avant son oui »).

Une page simple (relecture.html), servie sur le PC seulement (127.0.0.1 ; depuis Windows : http://localhost:4480, WSL2
relaie le port), protégée par un jeton dans l'adresse. Elle liste ce que l'IA a appris des fichiers ; pour chaque souvenir
le papa choisit : GARDER, CORRIGER (il réécrit, puis garde) ou EFFACER. Le premier « soi » de l'IA se relit pareil. En bas :
les fichiers mis de côté PAR PRUDENCE (un doute, sans avis sûr) qu'il peut réintégrer pour la prochaine aspiration, et le
nombre de fichiers secrets exclus d'office (jamais lus).

LA PORTE : retenues() ne laisse passer QUE les souvenirs gardés ou corrigés. Un souvenir sans décision, ou effacé, n'est
jamais écrit. importer() n'écrit rien d'autre que ce que la porte laisse passer, et le note (idempotent : un deuxième
« oui » n'écrit pas deux fois). Le témoin de test coupe la porte et voit passer ce qu'elle retient.
"""
import json
import os
import secrets
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ICI = Path(__file__).resolve().parent
RACINE_DEPOT = ICI.parents[1]
for _p in (str(ICI), str(RACINE_DEPOT), str(RACINE_DEPOT / "jarvis")):
    if _p not in sys.path:
        sys.path.append(_p)

DECISIONS = ("garder", "corriger", "effacer")
PORT = 4480


def _lire(chemin, defaut):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def _ecrire(chemin, objet):
    chemin = Path(chemin)
    tmp = chemin.with_name(f".{chemin.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(objet, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, chemin)


def propositions(sortie):
    return _lire(Path(sortie) / "propositions.json", {"propositions": [], "soi": None})


def elements(sortie):
    """Tous les éléments à relire : le « soi » d'abord, puis les souvenirs."""
    p = propositions(sortie)
    return ([p["soi"]] if p.get("soi") else []) + list(p.get("propositions") or [])


def decisions(sortie):
    return _lire(Path(sortie) / "decisions.json", {})


def decider(sortie, eid, decision, texte=None):
    """Note la décision du papa pour un élément (decision None : la retire)."""
    ids = {e["id"] for e in elements(sortie)}
    if eid not in ids:
        raise KeyError(eid)
    if decision is not None and decision not in DECISIONS:
        raise ValueError(decision)
    texte = (str(texte).strip() if texte is not None else None)
    if decision == "corriger" and not texte:
        raise ValueError("une correction a besoin de son texte")
    d = decisions(sortie)
    if decision is None:
        d.pop(eid, None)
    else:
        d[eid] = {"decision": decision, "quand": time.time(), **({"texte": texte[:2000]} if decision == "corriger" else {})}
    _ecrire(Path(sortie) / "decisions.json", d)
    return d.get(eid)


def retenues(elements_, decisions_):
    """LA PORTE : [(élément, texte final)] pour les seuls éléments gardés ou corrigés par le papa."""
    out = []
    for e in elements_:
        d = decisions_.get(e["id"]) or {}
        if d.get("decision") == "garder":
            out.append((e, e["texte"]))
        elif d.get("decision") == "corriger" and str(d.get("texte") or "").strip():
            out.append((e, str(d["texte"]).strip()))
    return out


def _defaut_embed():
    import embeddings
    return embeddings.embed


def importer(sortie, db_path, embed=None, maintenant=None):
    """Écrit dans la mémoire de l'IA ce que la porte laisse passer, et rien d'autre. Rend le bilan."""
    import identity
    import memory
    sortie = Path(sortie)
    embed = embed or _defaut_embed()
    tous = elements(sortie)
    decs = decisions(sortie)
    passe = retenues(tous, decs)
    mem = memory.Memory(db_path)
    mem.db.execute("CREATE TABLE IF NOT EXISTS naissance_sources (episode_id INTEGER, element TEXT, affiche TEXT, chemin TEXT, "
                   "quand REAL)")
    deja = set(json.loads(mem.kv_get("naissance_importes", "[]") or "[]"))
    jour = datetime.fromtimestamp(maintenant or time.time()).strftime("%d/%m/%Y")
    bilan = {"importes": 0, "deja": 0, "soi": False, "sans_oui": 0, "effaces": 0}
    for e in tous:
        d = (decs.get(e["id"]) or {}).get("decision")
        if d is None:
            bilan["sans_oui"] += 1
        elif d == "effacer":
            bilan["effaces"] += 1
    for e, texte in passe:
        if e["id"] in deja:
            bilan["deja"] += 1
            continue
        if e["id"] == "soi":
            ok, raison = identity.set_core(mem, texte, force=True)
            bilan["soi"] = bool(ok)
        else:
            sources = [s.get("affiche") for s in e.get("sources") or [] if s.get("affiche")]
            contenu = (f"[Appris du PC de papa, relu et validé par papa le {jour}] {texte}"
                       + (f" (d'après : {' ; '.join(sources[:4])})" if sources else ""))
            eid = mem.add("semantic", contenu, importance=float(e.get("importance") or 0.6), embedding=list(embed(texte)))
            for s in e.get("sources") or []:
                mem.db.execute("INSERT INTO naissance_sources VALUES (?,?,?,?,?)",
                               (eid, e["id"], s.get("affiche") or "", s.get("chemin") or "", time.time()))
            bilan["importes"] += 1
        deja.add(e["id"])
    mem.kv_set("naissance_importes", json.dumps(sorted(deja)))
    mem.db.commit()
    mem.db.close()
    _ecrire(sortie / "import.json", {**bilan, "quand": time.time()})
    return bilan


# ---- les fichiers mis de côté par prudence, réintégrables (jamais un secret certain)
def reintegres(sortie):
    return list(_lire(Path(sortie) / "reintegres.json", []))


def reintegrer(sortie, affiche):
    import aspiration
    ex = {x["affiche"]: x for x in aspiration.exclusions(sortie)}
    x = ex.get(affiche)
    if not x or x["niveau"] != "doute":
        raise ValueError("seul un fichier mis de côté par doute se réintègre")
    r = reintegres(sortie)
    if affiche not in r:
        r.append(affiche)
        _ecrire(Path(sortie) / "reintegres.json", r)
    return r


def etat(sortie):
    import aspiration
    p = propositions(sortie)
    exclus = aspiration.exclusions(sortie)
    r = set(reintegres(sortie))
    return {"papa": p.get("papa") or [], "soi": p.get("soi"), "propositions": p.get("propositions") or [],
            "decisions": decisions(sortie), "fichiers_lus": p.get("fichiers_lus", 0), "inventaire": p.get("inventaire", 0),
            "prudence": [{"affiche": x["affiche"], "genre": x["genre"], "par": x["par"], "reintegre": x["affiche"] in r}
                         for x in exclus if x["niveau"] == "doute"],
            "secrets_exclus": sum(1 for x in exclus if x["niveau"] == "certain"),
            "importe": _lire(Path(sortie) / "import.json", None)}


# ---- le serveur de la page
def jeton(sortie):
    f = Path(sortie) / "relecture-jeton"
    try:
        return f.read_text().strip()
    except OSError:
        j = secrets.token_urlsafe(18)
        f.write_text(j)
        os.chmod(f, 0o600)
        return j


def application(sortie, db_path, embed=None, port=PORT):
    sortie = Path(sortie)
    cle = jeton(sortie)
    page = (ICI / "relecture.html").read_text(encoding="utf-8")

    class Page(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _hote_ok(self):
            h = (self.headers.get("Host") or "").split(":")[0]
            return h in ("localhost", "127.0.0.1", "[::1]")

        def _jeton_ok(self):
            q = parse_qs(urlparse(self.path).query)
            return secrets.compare_digest(self.headers.get("X-Jeton") or (q.get("jeton") or [""])[0], cle)

        def _repondre(self, code, corps, type_="application/json; charset=utf-8"):
            b = corps if isinstance(corps, bytes) else json.dumps(corps, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", type_)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                                        "script-src 'self' 'unsafe-inline'; connect-src 'self'")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if urlparse(self.path).path == "/favicon.ico":         # le navigateur la demande sans jeton : rien à montrer
                return self._repondre(204, b"", "image/x-icon")
            if not self._hote_ok() or not self._jeton_ok():
                return self._repondre(403, {"erreur": "adresse incomplète : ouvrez le lien donné au lancement"})
            chemin = urlparse(self.path).path
            if chemin == "/":
                return self._repondre(200, page.encode("utf-8"), "text/html; charset=utf-8")
            if chemin == "/api/etat":
                return self._repondre(200, etat(sortie))
            return self._repondre(404, {"erreur": "inconnu"})

        def do_POST(self):
            if not self._hote_ok() or not self._jeton_ok():
                return self._repondre(403, {"erreur": "refusé"})
            try:
                n = min(int(self.headers.get("Content-Length") or 0), 200_000)
                corps = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except ValueError:
                return self._repondre(400, {"erreur": "illisible"})
            chemin = urlparse(self.path).path
            try:
                if chemin == "/api/decision":
                    return self._repondre(200, {"ok": True, "decision": decider(sortie, str(corps.get("id")), corps.get("decision"),
                                                                                 corps.get("texte"))})
                if chemin == "/api/reintegrer":
                    return self._repondre(200, {"ok": True, "reintegres": reintegrer(sortie, str(corps.get("affiche")))})
                if chemin == "/api/valider":
                    return self._repondre(200, {"ok": True, "bilan": importer(sortie, db_path, embed=embed)})
            except (KeyError, ValueError) as e:
                return self._repondre(400, {"erreur": str(e)[:200]})
            return self._repondre(404, {"erreur": "inconnu"})

    serveur = ThreadingHTTPServer(("127.0.0.1", port), Page)
    return serveur, f"http://localhost:{serveur.server_address[1]}/?jeton={cle}"


def servir(sortie, db_path, port=PORT):
    serveur, adresse = application(sortie, db_path, port=port)
    print(f"Relecture ouverte : {adresse}\n(ouvrez ce lien dans le navigateur de Windows ; Ctrl+C pour fermer)", flush=True)
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        serveur.server_close()
