"""Le pont léger entre le cockpit et chocs.py (quelques dizaines de ms : ni modèle, ni embeddings).
  chocs_cli.py reflexe   < {"cle", "texte", "oral", "voix"}   → {"vus", "faits", "humeur", "humeur_code", "arousal"}
  chocs_cli.py balise    < {"cle", "reponse"}                 → {"issue", "faits", …}
  chocs_cli.py etat | on | off             (les chocs)
  chocs_cli.py style-on | style-off       (le style du moment, style.py)
Jamais bloquant pour le cockpit : en cas d'erreur, une ligne JSON {"erreur": …} et le code 0.
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import chocs  # noqa: E402


class Mem:
    def __init__(self, chemin=None):
        self.db = sqlite3.connect(str(chemin or config.DB_PATH), timeout=5)
        self.db.execute("PRAGMA busy_timeout = 5000")

    def kv_get(self, key, default=None):
        row = self.db.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def kv_set(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES (?,?,?)", (key, value, time.time()))
        self.db.commit()


def main(argv, entree=None, mem=None):
    cmd = argv[1] if len(argv) > 1 else "etat"
    mem = mem or Mem()
    if cmd in ("on", "off"):
        mem.kv_set(chocs.CLE_ACTIF, "1" if cmd == "on" else "0")
    if cmd in ("style-on", "style-off"):
        mem.kv_set("style_actif", "1" if cmd == "style-on" else "0")
        cmd = "etat"
    if cmd in ("on", "off", "etat"):
        st = chocs._etat(mem)
        return {"actif": chocs.actif(mem), "style": mem.kv_get("style_actif") == "1", "v2": chocs.affect.v2_actif(mem),
                "sagesse_fond": chocs.sagesse_fond(),
                "reprises_en_attente": len(st.get("regulations", [])), "attaques_30min": len(st.get("attaques", []))}
    q = json.loads(entree if entree is not None else sys.stdin.read() or "{}")
    cle = str(q.get("cle") or "")[:60]
    if cmd == "reflexe":
        r = chocs.reflexe(mem, cle, str(q.get("texte") or "")[:20000], bool(q.get("oral")), q.get("voix"))
        if r.get("actif"):
            r.update(chocs.humeur(mem))
        try:                                     # (2026-10-23) le style du moment, APRÈS le réflexe : un choc s'y lit
            import style
            s = style.consigne(mem)
            if s:
                r["style"] = s
                chocs.journaliser(mem, {"type": "style", "cle": cle, **s})     # pour la mesure (eval/voix_mots)
        except Exception as e:
            r["style_erreur"] = f"{type(e).__name__}: {e}"[:200]
        return r
    if cmd == "balise":
        return chocs.appliquer_balise(mem, cle, chocs.lire_balise(q.get("reponse")))
    return {"erreur": f"commande inconnue : {cmd}"}


if __name__ == "__main__":
    try:
        print(json.dumps(main(sys.argv), ensure_ascii=False))
    except Exception as e:                       # le cockpit ne doit jamais tomber à cause d'un choc
        print(json.dumps({"erreur": f"{type(e).__name__}: {e}"[:300]}, ensure_ascii=False))
