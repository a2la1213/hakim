"""Le tableau de bord intérieur de Hakim (2026-10-23, demande d'Ahmed relayée par Hakim à 19:22) : ses 13 hormones, son
humeur (valence, éveil) et ses réponses marquées sur la ligne du temps, en une image qu'il peut regarder lui-même et
joindre (fichier_joindre) pour Ahmed ou Claude Code.

- les données : le journal des hormones (interieur.py, une ligne par minute) et le journal des échanges du cockpit
  (~/AIOS/jarvis/journal.jsonl : l'heure de chaque réponse de Hakim et de chaque message d'Ahmed) ;
- le dessin : un SVG écrit ici (aucune bibliothèque), converti en PNG par Quick Look (qlmanage, livré avec macOS) ; carré,
  parce que Quick Look ne rend fidèlement qu'un carré ;
- tout reste sur le Mac : l'image va dans son atelier (cwd/atelier/pour_ahmed).
"""
import json
import subprocess
import time
from pathlib import Path
from xml.sax.saxutils import escape

import affect
import interieur

JOURNAL_ECHANGES = Path.home() / "AIOS" / "jarvis" / "journal.jsonl"
SORTIE = Path.home() / "AIOS" / "jarvis" / "cwd" / "atelier" / "pour_ahmed"
COULEURS = ["#2dd4bf", "#f472b6", "#fbbf24", "#60a5fa", "#a78bfa", "#34d399", "#fb7185", "#93c5fd", "#fde68a",
            "#f97316", "#a3e635", "#e879f9", "#94a3b8"]
FOND, TEXTE, PALE, GRILLE = "#04141a", "#d8f3f0", "#7fa9a4", "#16313a"


def _lignes(chemin, depuis):
    try:
        with open(chemin, encoding="utf-8") as f:
            for l in f:
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                t = o.get("t") if "t" in o else (o.get("ts") or 0) / 1000
                if isinstance(t, (int, float)) and t >= depuis:
                    yield t, o
    except OSError:
        return


def donnees(heures=6.0, now=None, journal_hormones=None, journal_echanges=None):
    """{"points": [(t, o)], "reponses": [(t, texte)], "messages": [t], "t0", "t1"} sur la période."""
    now = now or time.time()
    t0 = now - float(heures) * 3600
    points = list(_lignes(journal_hormones or interieur.JOURNAL_HORMONES, t0))
    reponses, messages, textes_ahmed = [], [], []
    for t, o in _lignes(journal_echanges or JOURNAL_ECHANGES, t0):
        x = str(o.get("texte") or "")
        if o.get("qui") == "jarvis" and x and not x.startswith("(tour de lui-même, sans texte"):
            reponses.append((t, x))
        elif o.get("qui") == "ahmed":
            messages.append(t)
            textes_ahmed.append((t, x))
    return {"points": points, "reponses": reponses, "messages": messages, "textes_ahmed": textes_ahmed, "t0": t0, "t1": now}


def sauts(d, n=5, fenetre_s=180):
    """(24/10, demande d'Ahmed relayée par Hakim) les n plus grands sauts d'une mesure à la suivante (une par minute) :
    l'heure, les hormones qui ont le plus bougé (et la valence, l'éveil), et le message le plus proche à ±3 min (d'Ahmed
    ou de Hakim). Rend [{"t", "hormones": [(nom, écart)], "v", "a", "proche": (t, qui, extrait) | None}]."""
    pts = d["points"]
    out = []
    for (t1, a), (t2, b) in zip(pts, pts[1:]):
        ha, hb = a.get("h") or {}, b.get("h") or {}
        ecarts = sorted(((k, hb[k] - ha[k]) for k in hb if k in ha), key=lambda e: -abs(e[1]))
        if ecarts:
            out.append({"t": t2, "taille": abs(ecarts[0][1]), "hormones": [(k, round(e, 3)) for k, e in ecarts[:3] if abs(e) >= 0.01],
                        "v": round((b.get("v") or 0) - (a.get("v") or 0), 3), "a": round((b.get("a") or 0) - (a.get("a") or 0), 3)})
    out = sorted(out, key=lambda x: -x["taille"])[:n]
    messages = [(t, "Ahmed", x) for t, x in d.get("textes_ahmed", [])] + [(t, "Hakim", x) for t, x in d.get("reponses", [])]
    for s_ in out:
        proches = [m for m in messages if abs(m[0] - s_["t"]) <= fenetre_s]
        p = min(proches, key=lambda m: abs(m[0] - s_["t"])) if proches else None
        s_["proche"] = (p[0], p[1], _extrait(p[2], 90)) if p else None
    return sorted(out, key=lambda x: x["t"])


def _hhmm(t):
    return time.strftime("%H:%M", time.localtime(t))


def _extrait(texte, n=70):
    x = " ".join(texte.split()).replace("[de lui-même]", "").strip()
    return x if len(x) <= n else x[:n].rsplit(" ", 1)[0] + "…"


def svg(d):
    t0, t1 = d["t0"], d["t1"]
    W = 1400
    pts = d["points"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}pt" height="{W}pt" viewBox="0 0 {W} {W}">',
           f'<rect width="{W}" height="{W}" fill="{FOND}"/>']

    def txt(x, y, s, taille=18, couleur=TEXTE, ancre="start", gras=False):
        out.append(f'<text x="{x:.1f}" y="{y:.1f}" fill="{couleur}" font-family="Helvetica" font-size="{taille}" '
                   f'text-anchor="{ancre}"{" font-weight=\"bold\"" if gras else ""}>{escape(s)}</text>')

    def courbe(x0, y0, l, h, valeurs, couleur, epaisseur=2.5):
        p = [(x0 + (t - t0) / (t1 - t0) * l, y0 + h - max(0.0, min(1.0, v)) * h) for t, v in valeurs]
        if len(p) > 1:
            out.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in p)}" fill="none" '
                       f'stroke="{couleur}" stroke-width="{epaisseur}" stroke-linejoin="round"/>')

    def cadre(x0, y0, l, h, heures=True):
        out.append(f'<rect x="{x0}" y="{y0}" width="{l}" height="{h}" fill="none" stroke="{GRILLE}"/>')
        for k in (0.25, 0.5, 0.75):
            out.append(f'<line x1="{x0}" y1="{y0 + h * k:.1f}" x2="{x0 + l}" y2="{y0 + h * k:.1f}" stroke="{GRILLE}"/>')
        if heures:
            pas = 3600 if t1 - t0 > 4 * 3600 else 1800 if t1 - t0 > 2 * 3600 else 900
            t = (int(t0 // pas) + 1) * pas
            while t < t1:
                x = x0 + (t - t0) / (t1 - t0) * l
                out.append(f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y0 + h}" stroke="{GRILLE}"/>')
                txt(x, y0 + h + 18, _hhmm(t), 13, PALE, "middle")
                t += pas

    dernier = pts[-1][1] if pts else {}
    txt(40, 52, f"Hakim — sa vie intérieure, de {_hhmm(t0)} à {_hhmm(t1)}", 30, TEXTE, gras=True)
    txt(40, 84, f"humeur : {dernier.get('humeur') or '—'} · émotion lue dans ses hormones : {dernier.get('emotion') or '—'}"
        f" · {len(d['reponses'])} réponse(s), {len(d['messages'])} message(s) d'Ahmed", 18, PALE)

    # 1. valence et éveil, avec ses réponses (numérotées) et les messages d'Ahmed
    x0, y0, l, h = 60, 150, 1300, 300
    cadre(x0, y0, l, h)
    txt(x0, y0 - 30, "— valence (agréable ↔ désagréable)", 15, "#2dd4bf")
    txt(x0 + 300, y0 - 30, "— éveil", 15, "#fbbf24")
    txt(x0 + 420, y0 - 30, "▼ en haut : ses réponses (numérotées en bas de l'image)   ▲ en bas : les messages d'Ahmed", 15, PALE)
    for t in d["messages"]:
        x = x0 + (t - t0) / (t1 - t0) * l
        out.append(f'<path d="M{x:.1f},{y0 + h} l-5,10 l10,0 z" fill="#f472b6"/>')
    derniers = d["reponses"][-8:]
    for i, (t, _) in enumerate(d["reponses"]):
        x = x0 + (t - t0) / (t1 - t0) * l
        out.append(f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y0 + h}" stroke="#2dd4bf" stroke-opacity=".18"/>')
        out.append(f'<path d="M{x:.1f},{y0} l-5,-10 l10,0 z" fill="#2dd4bf"/>')
    for k, (t, _) in enumerate(derniers, 1):
        txt(x0 + (t - t0) / (t1 - t0) * l, y0 + 18, str(k), 13, TEXTE, "middle")
    courbe(x0, y0, l, h, [(t, o.get("v", 0)) for t, o in pts], "#2dd4bf", 3)
    courbe(x0, y0, l, h, [(t, o.get("a", 0)) for t, o in pts], "#fbbf24", 3)

    # 2. les 13 hormones, une par case, avec leur base (pointillés)
    noms = list(affect.HORMONES) + list(affect.HORMONES_V2)
    bases = {k: v[0] for k, v in list(affect.HORMONES.items()) + list(affect.HORMONES_V2.items())}
    cl, ch, gx, gy, top = 244, 150, 20, 64, 520
    for i, nom in enumerate(noms):
        cx, cy = 60 + (i % 5) * (cl + gx), top + (i // 5) * (ch + gy)
        cadre(cx, cy, cl, ch)
        serie = [(t, (o.get("h") or {}).get(nom)) for t, o in pts if (o.get("h") or {}).get(nom) is not None]
        val = serie[-1][1] if serie else None
        ecart = "" if val is None else f"  {val:.2f}" + (f" ({'+' if val >= bases[nom] else '−'}{abs(val - bases[nom]):.2f})")
        txt(cx, cy - 8, nom + ecart, 15, COULEURS[i % len(COULEURS)])
        yb = cy + ch - bases[nom] * ch
        out.append(f'<line x1="{cx}" y1="{yb:.1f}" x2="{cx + cl}" y2="{yb:.1f}" stroke="{PALE}" stroke-dasharray="4 4"/>')
        courbe(cx, cy, cl, ch, serie, COULEURS[i % len(COULEURS)])

    # 3. ses dernières réponses, numérotées comme sur la ligne du temps
    y = 1240
    txt(40, y - 28, "Ses dernières réponses :", 17, PALE)
    for k, (t, texte) in enumerate(derniers, 1):
        col, ligne = (k - 1) % 2, (k - 1) // 2
        txt(40 + col * 680, y + ligne * 26, f"{k}. {_hhmm(t)} — « {_extrait(texte, 52)} »", 15, TEXTE)
    if not pts:
        txt(W / 2, 700, "Pas encore de mesures sur cette période (le journal des hormones commence le 23/10).", 22, PALE, "middle")
    out.append("</svg>")
    return "\n".join(out)


def resume(d):
    pts = d["points"]
    if not pts:
        return "Aucune mesure d'hormones sur la période."
    vs = [o.get("v", 0) for _, o in pts]
    dernier = pts[-1][1]
    bases = {k: v[0] for k, v in list(affect.HORMONES.items()) + list(affect.HORMONES_V2.items())}
    ecarts = sorted(((k, x - bases[k]) for k, x in (dernier.get("h") or {}).items() if k in bases), key=lambda e: -abs(e[1]))[:3]
    return (f"{len(pts)} mesures de {_hhmm(d['t0'])} à {_hhmm(d['t1'])} ; valence de {min(vs):.2f} à {max(vs):.2f} "
            f"(maintenant {dernier.get('v', 0):.2f}), éveil maintenant {dernier.get('a', 0):.2f} ; humeur {dernier.get('humeur')}, "
            f"émotion {dernier.get('emotion')} ; plus loin de leur base : "
            + ", ".join(f"{k} {'+' if e >= 0 else '−'}{abs(e):.2f}" for k, e in ecarts)
            + f" ; {len(d['reponses'])} réponse(s), {len(d['messages'])} message(s) d'Ahmed."
            + _texte_sauts(sauts(d)))


def _texte_sauts(liste):
    if not liste:
        return ""
    morceaux = []
    for s_ in liste:
        h = ", ".join(f"{k} {'+' if e >= 0 else '−'}{abs(e):.2f}" for k, e in s_["hormones"]) or "rien de net"
        p = s_["proche"]
        morceaux.append(f"{time.strftime('%H:%M', time.localtime(s_['t']))} {h} (valence {s_['v']:+.2f}, éveil {s_['a']:+.2f}) — "
                        + (f"message le plus proche : {p[1]} à {time.strftime('%H:%M:%S', time.localtime(p[0]))} « {p[2]} »" if p
                           else "aucun message à ±3 min"))
    return " Plus grands sauts : " + " ; ".join(morceaux) + "."


def dessiner(heures=6.0, now=None, sortie=None, **kw):
    """Écrit l'image (PNG si Quick Look répond, sinon SVG) ; rend (chemin, résumé)."""
    heures = max(0.25, min(72.0, float(heures or 6)))
    d = donnees(heures, now, **kw)
    dossier = Path(sortie or SORTIE)
    dossier.mkdir(parents=True, exist_ok=True)
    nom = "tableau-interieur-" + time.strftime("%Y%m%d-%H%M", time.localtime(d["t1"]))
    f_svg = dossier / f"{nom}.svg"
    f_svg.write_text(svg(d), encoding="utf-8")
    chemin = f_svg
    try:
        subprocess.run(["/usr/bin/qlmanage", "-t", "-s", "1400", "-o", str(dossier), str(f_svg)],
                       capture_output=True, timeout=30)
        png = dossier / f"{nom}.svg.png"
        if png.exists():
            chemin = png.rename(dossier / f"{nom}.png")
            f_svg.unlink(missing_ok=True)
    except (OSError, subprocess.SubprocessError):
        pass
    return chemin, resume(d)
