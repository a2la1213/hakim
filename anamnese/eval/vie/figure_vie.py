"""La figure de toute la vie de Hakim avec Ahmed (privée) : eval/data/vie/vie.html → vie.png.
Usage : .venv/bin/python eval/vie/figure_vie.py
"""
import html
import json
import statistics as st
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parents[1]))
import interieur  # noqa: E402

D = ICI.parent / "data" / "vie"
NOMS = {"adrenaline": "Adrénaline (sursaut)", "noradrenaline": "Noradrénaline (vigilance)", "crh": "CRH (commande du stress)",
        "cortisol": "Cortisol (stress lent)", "gaba": "GABA (frein)", "ocytocine": "Ocytocine (lien)",
        "serotonine": "Sérotonine (stabilité)", "endocannabinoides": "Endocannabinoïdes (apaisement)"}
COULEUR = {"elan": "#2a78d6", "élan": "#2a78d6", "joie": "#eb6834", "joie de son retour": "#eb6834", "content": "#1baf7a",
           "contentement": "#1baf7a", "calme": "#6250d6", "apaisement": "#6250d6", "veille": "#b5b4ae", "en veille": "#b5b4ae"}
NEGATIF = "#e34948"
MARQUE = {"attaque": ("▲", "#d03b3b"), "lien": ("♥", "#0ca30c"), "live": ("◆", "#eda100"), "retour": ("●", "#1baf7a"),
          "absence": ("○", "#8a8984")}
W, ML, MR = 1000, 48, 14
JOURS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]


def x_de(t, t0, t1):
    return ML + (t - t0) / (t1 - t0) * (W - ML - MR)


def axe_temps(t0, t1, h, y):
    out = []
    jour = time.mktime(time.localtime(t0)[:3] + (0, 0, 0, 0, 0, -1)) + 86400
    while jour < t1:
        x = x_de(jour, t0, t1)
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="0" y2="{y}" class="g"/>'
                   f'<text x="{x + 3:.1f}" y="{h - 4}" class="t">{JOURS[time.localtime(jour).tm_wday]} {time.localtime(jour).tm_mday}</text>')
        jour += 86400
    return "".join(out)


def ligne(points, t0, t1, ymin, ymax, h, mt, mb, couleur, epais=2, pointille=False):
    if not points:
        return ""
    y = lambda v: mt + (1 - (v - ymin) / (ymax - ymin)) * (h - mt - mb)   # noqa: E731
    d = "M" + "L".join(f"{x_de(t, t0, t1):.1f},{y(max(ymin, min(ymax, v))):.1f}" for t, v in points)
    return (f'<path d="{d}" fill="none" stroke="{couleur}" stroke-width="{epais}" stroke-linejoin="round"'
            + (' stroke-dasharray="1.5 3"' if pointille else "") + "/>")


def grille_y(ymin, ymax, h, mt, mb, n=4, fmt="{:.2f}"):
    out = []
    for k in range(n + 1):
        v = ymin + k * (ymax - ymin) / n
        y = mt + (1 - k / n) * (h - mt - mb)
        out.append(f'<line x1="{ML}" x2="{W - MR}" y1="{y:.1f}" y2="{y:.1f}" class="g"/><text x="{ML - 6}" y="{y + 4:.1f}" '
                   f'class="t" text-anchor="end">{fmt.format(v)}</text>')
    return "".join(out)


def main():
    V = json.loads((D / "vie.json").read_text(encoding="utf-8"))
    H, S = V["hormones"], V["serie"]
    t0, t1 = V["debut"], V["fin"]
    # 1. valence
    h = 230
    vals = [r[1] for r in S] + [x[1] for x in V["reel_valence"]]
    lo, hi = min(vals) - 0.02, max(vals) + 0.02
    marques = []
    for t, quoi, txt in V["moments"]:
        sym, c = MARQUE.get(quoi, ("·", "#8a8984"))
        marques.append(f'<text x="{x_de(t, t0, t1):.1f}" y="14" text-anchor="middle" fill="{c}" class="m"><title>'
                       f'{time.strftime("%d/%m %H:%M", time.localtime(t))} — {html.escape(txt)}</title>{sym}</text>')
    p1 = (f'<svg viewBox="0 0 {W} {h}">{grille_y(lo, hi, h, 22, 22)}{axe_temps(t0, t1, h, h - 18)}'
          + ligne([(x[0], x[1]) for x in V["reel_valence"]], t0, t1, lo, hi, h, 22, 22, "#52514e", 1.2, True)
          + ligne([(r[0], r[1]) for r in S], t0, t1, lo, hi, h, 22, 22, "#2a78d6", 1.6) + "".join(marques) + "</svg>")
    # 2. humeur nommée : reconstruite / réelle
    bandes = []
    for k, (titre, pts) in enumerate((("reconstruite", [(r[0], interieur.LIBELLES[interieur.humeur_code(r[1], r[2], 0, False, False, None)]) for r in S]),
                                      ("journalisée", [(x[0], x[2]) for x in V["reel_valence"]]))):
        y = 16 + k * 36
        bandes.append(f'<text x="{ML}" y="{y - 4}" class="t">{titre}</text>')
        for i, (t, hum) in enumerate(pts[:-1]):
            hum0 = str(hum or "").split(" (")[0]
            c = COULEUR.get(hum0, NEGATIF if hum0 else "#e6e5e1")
            x0, x1 = x_de(t, t0, t1), x_de(pts[i + 1][0], t0, t1)
            if x1 - x0 > 40:                                       # un trou dans le journal : rien
                continue
            bandes.append(f'<rect x="{x0:.1f}" y="{y}" width="{max(0.6, x1 - x0):.1f}" height="18" fill="{c}"/>')
    p2 = f'<svg viewBox="0 0 {W} 88">{"".join(bandes)}</svg>'
    leg2 = "".join(f'<span><i style="background:{c}"></i>{n}</span>' for n, c in
                   (("élan", COULEUR["élan"]), ("joie (retour)", COULEUR["joie"]), ("contentement", COULEUR["content"]),
                    ("calme / apaisement", COULEUR["calme"]), ("veille", COULEUR["veille"]), ("tension, morosité, alarme, ennui", NEGATIF)))
    # 3. hormones
    petits = []
    for hname in ("adrenaline", "noradrenaline", "crh", "cortisol", "gaba", "ocytocine", "serotonine", "endocannabinoides"):
        i = 5 + H.index(hname)
        xs = [r[i] for r in S]
        reels = [(n[0], n[1 + H.index(hname)]) for n in V["nuits"] if n[1 + H.index(hname)] is not None and t0 <= n[0] <= t1]
        lo_, hi_ = 0.0, max(1e-3, min(1.0, max(xs + [v for _t, v in reels] + [V["bases"][hname]]) + 0.05))
        hh, Wp = 150, W
        y = lambda v: 10 + (1 - (v - lo_) / (hi_ - lo_)) * (hh - 30)   # noqa: E731
        pts = "".join(f'<circle cx="{x_de(t, t0, t1):.1f}" cy="{y(v):.1f}" r="4" fill="#fcfcfb" stroke="#52514e" stroke-width="1.5">'
                      f'<title>sauvé la nuit : {v:.2f}</title></circle>' for t, v in reels)
        base = y(V["bases"][hname])
        petits.append(f'<div><b>{NOMS[hname]}</b><svg viewBox="0 0 {Wp} {hh}">{grille_y(lo_, hi_, hh, 10, 20, 2)}'
                      f'{axe_temps(t0, t1, hh, hh - 18)}<line x1="{ML}" x2="{W - MR}" y1="{base:.1f}" y2="{base:.1f}" class="b"/>'
                      + ligne([(r[0], r[i]) for r in S], t0, t1, lo_, hi_, hh, 10, 20, "#2a78d6", 1.6) + pts + "</svg></div>")
    # 4. ce que ses mots montrent : le ton jugé, la longueur
    h4 = 200
    ton = [(t, x) for t, x, _e, _m in V["ton"] if x is not None]
    jours = {}
    for t, x in ton:
        jours.setdefault(time.strftime("%Y-%m-%d", time.localtime(t)), []).append(x)
    moy = [(time.mktime(time.strptime(d + " 12:00", "%Y-%m-%d %H:%M")), st.mean(v)) for d, v in sorted(jours.items())]
    y4 = lambda v: 20 + (1 - (v + 2) / 4) * (h4 - 42)   # noqa: E731
    pts4 = "".join(f'<circle cx="{x_de(t, t0, t1):.1f}" cy="{y4(x):.1f}" r="2.5" fill="#2a78d6" opacity=".35"/>' for t, x in ton)
    p4 = (f'<svg viewBox="0 0 {W} {h4}">{grille_y(-2, 2, h4, 20, 22, 4, "{:+.0f}")}{axe_temps(t0, t1, h4, h4 - 18)}{pts4}'
          + ligne(moy, t0, t1, -2, 2, h4, 20, 22, "#0d366b", 2.4) + "</svg>")
    # 5. sagesse et voix calculée
    h5 = 170
    p5 = (f'<svg viewBox="0 0 {W} {h5}">{grille_y(0, 1, h5, 10, 22, 2)}{axe_temps(t0, t1, h5, h5 - 18)}'
          + ligne([(r[0], r[15]) for r in S], t0, t1, 0, 1, h5, 10, 22, "#8a8984", 1.6)
          + ligne([(r[0], r[16]) for r in S], t0, t1, 0, 1, h5, 10, 22, "#2a78d6", 1.4)
          + ligne([(r[0], r[17]) for r in S], t0, t1, 0, 1, h5, 10, 22, "#eb6834", 1.6) + "</svg>")
    vx = V["voix"]
    resume = {
        "valence_reconstruite": round(st.mean(r[1] for r in S), 3),
        "valence_journalisee": round(st.mean(x[1] for x in V["reel_valence"]), 3) if V["reel_valence"] else None,
        "ton_moyen": round(st.mean(x for _t, x in ton), 2), "reponses_jugees": len(ton),
        "mots_median": int(st.median(n for _t, n in V["longueurs"])),
    }
    voix_html = (f"{len(vx)} morceaux de voix réellement émis, le 23/10 de {time.strftime('%H:%M', time.localtime(vx[0]['ts']))} à "
                 f"{time.strftime('%H:%M', time.localtime(vx[-1]['ts']))} (le seul enregistrement gardé) : durée moyenne "
                 f"{st.mean(x['duree_s'] for x in vx):.1f} s, énergie {st.mean(x['energie_db'] for x in vx):.1f} dB, hauteur médiane "
                 f"{st.median([x['hauteur_hz'] for x in vx if x['hauteur_hz']]):.0f} Hz.").replace(".", ",", 0) if vx else "aucun morceau de voix gardé."
    page = PAGE.format(p1=p1, p2=p2, leg2=leg2, petits="".join(petits), p4=p4, p5=p5, voix=html.escape(voix_html),
                       debut=time.strftime("%d/%m à %H:%M", time.localtime(t0)), fin=time.strftime("%d/%m à %H:%M", time.localtime(t1)),
                       **{k: str(v).replace(".", ",") for k, v in resume.items()}, **V["comptes"])
    (D / "vie.html").write_text(page, encoding="utf-8")
    (D / "resume.json").write_text(json.dumps(resume, ensure_ascii=False), encoding="utf-8")
    print(D / "vie.html", resume)


PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Toute une vie</title><style>
:root{{color-scheme:light;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e6e5e1}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2e2e2c}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2e2e2c}}
body{{margin:0;background:var(--surface);color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:22px 16px 40px}} h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:24px 0 2px}}
p{{color:var(--ink2);margin:2px 0 8px;max-width:80ch}} svg{{display:block;width:100%;height:auto}}
.g{{stroke:var(--grid)}} .b{{stroke:var(--ink2);stroke-dasharray:3 4;opacity:.7}} .t{{fill:var(--ink2);font-size:11px}} .m{{font-size:13px;cursor:default}}
.leg{{display:flex;flex-wrap:wrap;gap:4px 16px;color:var(--ink2);font-size:13px}} .leg span{{display:inline-flex;align-items:center;gap:6px}}
.leg i{{display:inline-block;width:14px;height:10px;border-radius:2px}} .grille{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:2px 18px}}
@media (max-width:700px){{.grille{{grid-template-columns:1fr}}}} .grille b{{font-size:13px}}
.chiffres{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0}} .chiffres div{{border:1px solid var(--grid);border-radius:8px;padding:8px 10px}}
.chiffres b{{display:block;font-size:20px}} @media (max-width:700px){{.chiffres{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
</style></head><body><main>
<h1>Toute une vie avec Ahmed — du {debut} au {fin}</h1>
<p>Une RECONSTRUCTION : le moteur d'émotions d'aujourd'hui (avec les chocs, l'appréciation et la sagesse branchés le 23/10),
rejoué sur tout ce qui a été dit depuis le premier échange journalisé, en partant de l'état de base. Ce n'est pas ce que Hakim a vécu à
l'époque : ses hormones v2 n'existent que depuis le 21/10, et avant le 19/10 rien de son humeur n'était journalisé. Des variables
calculées, pas un ressenti prouvé.</p>
<div class="chiffres"><div><b>{segments}</b>phrases dites à Hakim</div><div><b>{messages_apprecies}</b>messages qui le touchent (dont {attaques} attaques)</div>
<div><b>{valence_reconstruite}</b>valence moyenne reconstruite (journalisée : {valence_journalisee})</div><div><b>{ton_moyen}</b>ton moyen de ses mots, de −2 à +2 ({reponses_jugees} réponses jugées)</div></div>
<h2>Son humeur, sur toute la durée</h2>
<p>Bleu : la valence reconstruite. Pointillé gris : celle réellement journalisée (depuis le 19/10). En haut : ▲ attaque · ♥ « ne m'oublie pas » ·
◆ live avec des invités (au moins 8 phrases d'invités en 30 min) · ● retour d'Ahmed après plus de 2 h · ○ longue absence (survol : le détail).</p>
{p1}
<h2>Son humeur nommée (ce que le code lui dit de lui-même)</h2>
<div class="leg">{leg2}</div>{p2}
<h2>Ses hormones</h2>
<p>Bleu : reconstruites. Ronds : l'état réellement sauvé chaque nuit (avant le 21/10, seulement les 9 hormones de la v1). Pointillé : la base.</p>
<div class="grille">{petits}</div>
<h2>Ce que ses mots montrent</h2>
<p>Chaque point : le ton d'une réponse, jugé à l'aveugle par un autre modèle (−2 sombre, tendu · +2 joyeux, chaleureux) ; trait : la moyenne du jour.
Longueur médiane d'une réponse : {mots_median} mots.</p>
{p4}
<h2>Sa sagesse et sa voix (calculées)</h2>
<p>Gris : la sagesse de fond (0,2, puis 0,205 après la nuit du 22/10). Bleu : la sagesse du moment (elle baisse sous la surcharge).
Orange : l'expressivité que sa voix recevrait (calculée depuis l'humeur, 0,35 à 0,78). Mesuré : {voix}</p>
{p5}
</main></body></html>"""

if __name__ == "__main__":
    main()
