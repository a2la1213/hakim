"""Le corpus des chocs (demande de Hakim, accord d'Ahmed le 2026-10-23) : ce qui a été dit À Hakim du 21/10 au 23/10,
découpé par voix.

Convention du texte (jarvis/empreinte_vocale.py) : ce qui n'est pas étiqueté est d'Ahmed ; une autre voix est annoncée
(« [voix 2] … », ou son nom si elle est connue : « [Nora] … »), et le retour d'Ahmed aussi (« [Ahmed] … »). L'étiquette
de l'échange (voix = ahmed / autre / plusieurs / doute ; absente = message tapé) dit à qui appartient le début non étiqueté.

Sortie (privée, jamais versionnée) : eval/data/chocs/segments.jsonl, et des tranches lisibles pour les annotateurs.
Usage : .venv/bin/python eval/chocs/corpus.py
"""
import json
import re
import time
from pathlib import Path

ECHANGES = Path.home() / "AIOS" / "jarvis" / "echanges-a-memoriser.jsonl"
VOIX_CONNUES = Path.home() / "AIOS" / "jarvis" / "voix-connues.json"
SORTIE = Path(__file__).resolve().parents[1] / "data" / "chocs"
DEBUT = "2026-10-21 00:00"
FIN = "2026-10-23 09:15"
TRANCHE_SIGNES = 60_000


def _ms(s):
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M")) * 1000


def noms_connus():
    try:
        return [v["nom"] for v in json.loads(VOIX_CONNUES.read_text(encoding="utf-8")) if v.get("nom")]
    except (OSError, ValueError):
        return []


def auteur_du_debut(e):
    """À qui appartient le texte non étiqueté du début : (catégorie, sûr ?)."""
    v = e.get("voix")
    if not e.get("oral") and v is None:
        return "ahmed", True                     # tapé : c'est lui
    if v == "ahmed":
        return "ahmed", True
    if v == "autre":
        return "tiers", False                    # l'empreinte dit « pas Ahmed », sans savoir qui
    return "ahmed", False                        # plusieurs / doute : par convention Ahmed, sans certitude


def decouper(texte, noms):
    """[(étiquette ou None, texte)] dans l'ordre."""
    etiquettes = r"voix \d+|Ahmed" + "".join("|" + re.escape(n) for n in noms if n != "Ahmed")
    motif = re.compile(r"\[(" + etiquettes + r")\]\s*")
    out, pos, courante = [], 0, None
    for m in motif.finditer(texte):
        if m.start() > pos and texte[pos:m.start()].strip():
            out.append((courante, texte[pos:m.start()].strip()))
        courante, pos = m.group(1), m.end()
    if texte[pos:].strip():
        out.append((courante, texte[pos:].strip()))
    return out


def segments(debut=DEBUT, fin=FIN):
    noms = noms_connus()
    a, b = _ms(debut), _ms(fin)
    out = []
    for l in ECHANGES.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if not (a <= e.get("ts", 0) <= b) or e.get("de_lui_meme"):
            continue
        texte = str(e.get("ahmed") or "")
        if not texte.strip():
            continue
        lead, lead_sur = auteur_du_debut(e)
        for k, (etiq, t) in enumerate(decouper(texte, noms)):
            if etiq is None:
                qui, sur = lead, lead_sur
            elif etiq == "Ahmed":
                qui, sur = "ahmed", True
            else:
                qui, sur = "tiers", True
            out.append({"id": f"{int(e['ts'])}-{k}", "ts": e["ts"] / 1000, "voix_echange": e.get("voix"),
                        "oral": bool(e.get("oral")), "etiquette": etiq, "qui": qui, "qui_sur": sur, "texte": t})
    return out


def main():
    segs = segments()
    SORTIE.mkdir(parents=True, exist_ok=True)
    with (SORTIE / "segments.jsonl").open("w", encoding="utf-8") as h:
        for s in segs:
            h.write(json.dumps(s, ensure_ascii=False) + "\n")
    # les tranches pour les annotateurs : l'heure, l'identifiant, qui parle (tel que le système le croit), le texte
    tranches, cur, n = [], [], 0
    for s in segs:
        qui = s["etiquette"] or ("Ahmed (tapé)" if not s["oral"] else f"début d'échange, voix={s['voix_echange']}")
        ligne = f"[{s['id']}] {time.strftime('%d/%m %H:%M:%S', time.localtime(s['ts']))} — {qui} : {s['texte']}\n"
        if n + len(ligne) > TRANCHE_SIGNES and cur:
            tranches.append(cur)
            cur, n = [], 0
        cur.append(ligne)
        n += len(ligne)
    if cur:
        tranches.append(cur)
    for i, t in enumerate(tranches, 1):
        (SORTIE / f"tranche-{i:02d}.txt").write_text("".join(t), encoding="utf-8")
    print(f"{len(segs)} segments, {len(tranches)} tranches → {SORTIE}")
    qui = {}
    for s in segs:
        k = (s["qui"], s["qui_sur"])
        qui[k] = qui.get(k, 0) + 1
    print(qui)


if __name__ == "__main__":
    main()
