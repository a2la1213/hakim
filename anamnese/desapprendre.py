"""Désapprendre (proposé par Hakim après une revue tierce, validé par Ahmed le 2026-10-20) : retirer un souvenir ET tout
ce qui en dérive — les faits distillés la nuit, les synthèses du démon, et ce qui dérive d'eux — en suivant les liens de
provenance (insight_edges : chaque dérivé pointe vers ses sources).

- Chaque retrait passe par le registre : l'entrée « désapprendre » est ANNULABLE (`anamnese annuler <entrée> --oui`
  recrée les souvenirs, leurs rubriques et leurs liens).
- Une simulation montre d'abord ce qui partirait. Par texte (« tout ce qui contient backup.example.net ») : les
  souvenirs dont le contenu le contient, plus leur descendance.
- Limite dite : un souvenir qui a RECOPIÉ un fait sans citer sa source (avant le 2026-10-20, les sources n'étaient pas
  exigées la nuit) n'a pas de lien — la recherche par texte est faite pour lui.
"""
import registre


def descendance(conn, ids):
    """Les ids donnés et tous leurs dérivés (largeur d'abord), dans l'ordre de découverte."""
    vus, file = [], list(dict.fromkeys(int(i) for i in ids))
    while file:
        x = file.pop(0)
        if x in vus:
            continue
        vus.append(x)
        if registre._table(conn, "insight_edges"):
            file.extend(r[0] for r in conn.execute("SELECT insight_id FROM insight_edges WHERE source_id=?", (x,)))
    return [x for x in vus if conn.execute("SELECT 1 FROM episodes WHERE id=?", (x,)).fetchone()]


def par_texte(conn, texte, limite=200):
    t = str(texte or "").strip()
    if len(t) < 6:
        raise ValueError("un texte d'au moins 6 caractères (sinon trop de souvenirs seraient pris)")
    return [r[0] for r in conn.execute("SELECT id FROM episodes WHERE instr(lower(content), lower(?)) > 0 ORDER BY id LIMIT ?",
                                       (t, limite))]


def apercu(conn, ids):
    out = []
    for x in ids:
        r = conn.execute("SELECT role, substr(content, 1, 140) FROM episodes WHERE id=?", (x,)).fetchone()
        if r:
            out.append({"id": x, "role": r[0], "debut": " ".join(str(r[1] or "").split())})
    return out


def desapprendre(conn, ids, raison="", simulation=True):
    """{"ids", "apercu", "registre"} ; simulation=True ne touche à rien."""
    tous = descendance(conn, ids)
    res = {"ids": tous, "apercu": apercu(conn, tous), "registre": None}
    if simulation or not tous:
        return res
    rid = registre.ouvrir(conn, "désapprendre", resume=f"désapprendre {len(tous)} souvenir(s) : {str(raison)[:300]}")
    try:
        for x in reversed(tous):                     # les dérivés d'abord : l'annulation recrée les sources avant eux
            ligne = registre._supprimer_episode(conn, x)
            registre.noter(conn, "episode", str(x), ligne, None, rid=rid)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        registre.fermer(conn, rid)
    res["registre"] = rid
    return res
