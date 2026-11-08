"""La figure des corrélations (privée) : eval/data/vie/correlations.html → .png. Usage : .venv/bin/python eval/vie/figure_correlations.py"""
import json
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "data" / "vie"
LIGNES = [("valence", "Valence (humeur)"), ("eveil", "Éveil"), ("humeur", "Humeur nommée (rang)"), ("emotion", "Émotion dominante (rang)"),
          ("adrenaline", "Adrénaline"), ("cortisol", "Cortisol"), ("ocytocine", "Ocytocine"), ("serotonine", "Sérotonine")]
COLS = [("ton", "Ton de ses mots"), ("energie", "Énergie de ses mots"), ("longueur", "Longueur")]


def couleur(r):
    if r is None:
        return "var(--vide)"
    a = min(1.0, abs(r) / 0.6)
    return f"rgba(42,120,214,{0.08 + 0.6 * a:.2f})" if r >= 0 else f"rgba(227,73,72,{0.08 + 0.6 * a:.2f})"


def cellule(c):
    if not c or c.get("r") is None:
        return '<td class="v">—</td>'
    faible = c["ic"][0] <= 0 <= c["ic"][1]
    return (f'<td style="background:{couleur(c["r"])}"><b>{c["r"]:+.2f}</b><small>[{c["ic"][0]:+.2f} ; {c["ic"][1]:+.2f}] · n={c["n"]}'
            f'{" · ≈ 0" if faible else ""}</small></td>').replace(".", ",")


def tableau(M, src, suffixe=""):
    lignes = []
    for k, nom in LIGNES:
        if not any(f"{src}_{k}{suffixe}|{c}" in M for c, _ in COLS):
            continue
        lignes.append(f"<tr><th>{nom}</th>" + "".join(cellule(M.get(f"{src}_{k}{suffixe}|{c}")) for c, _n in COLS) + "</tr>")
    return "<table><tr><th></th>" + "".join(f"<th>{n}</th>" for _c, n in COLS) + "</tr>" + "".join(lignes) + "</table>"


def main():
    C = json.loads((D / "correlations.json").read_text(encoding="utf-8"))
    M = C["matrice"]
    acc = C["accord_reconstruit_journalise"]
    voix = "".join(f"<tr><th>{x}</th>" + "".join(cellule(C['voix'].get(f'{x}|{y}')) for y in ("duree", "energie_db", "hauteur")) + "</tr>"
                   for x in ("valence", "eveil"))
    page = PAGE.format(reel=tableau(M, "reel"), reco=tableau(M, "reco"), prec=tableau(M, "reel", "_prec"),
                       a1=cellule(acc["avant le 21/10 (moteur v1)"]), a2=cellule(acc["depuis le 21/10 (moteur v2)"]), voix=voix,
                       n=C["n_reponses"], ve=C["voix_etendue_etat"])
    (D / "correlations.html").write_text(page, encoding="utf-8")
    print(D / "correlations.html")


PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ce qui suit son état</title><style>
:root{{color-scheme:light;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e6e5e1;--vide:#f0efec}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2e2e2c;--vide:#383835}}}}
:root[data-theme="dark"]{{color-scheme:dark;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2e2e2c;--vide:#383835}}
body{{margin:0;background:var(--surface);color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1000px;margin:0 auto;padding:22px 16px 36px}} h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:22px 0 4px}}
p{{color:var(--ink2);margin:2px 0 8px;max-width:82ch}} table{{border-collapse:separate;border-spacing:3px;width:100%}}
th{{text-align:left;font-weight:600;font-size:13px;color:var(--ink2);padding:4px 6px}} td{{padding:6px 8px;border-radius:6px;font-size:13px}}
td b{{display:block;font-size:16px}} td small{{color:var(--ink2)}} .v{{background:var(--vide);color:var(--ink2)}}
ul{{color:var(--ink2);max-width:82ch}} li{{margin:4px 0}}
</style></head><body><main>
<h1>Ce qui suit son état, et ce qui ne le suit pas</h1>
<p>Corrélations de Spearman entre l'état de Hakim au moment d'une réponse et ce qui sort de lui ; entre crochets, l'intervalle à 95 %.
Bleu : ça monte ensemble ; rouge : en sens inverse ; « ≈ 0 » : l'intervalle contient zéro. {n} réponses jugées à l'aveugle (ton de −2 à +2, énergie de 0 à 2).</p>
<h2>1. Le modèle reconstruit-il bien son état ?</h2>
<p>La valence reconstruite contre la valence réellement journalisée :</p>
<table><tr><th>Avant le 21/10 (l'ancien moteur, v1)</th>{a1}<th>Depuis le 21/10 (le moteur actuel, v2)</th>{a2}</tr></table>
<p><b>Oui, depuis que les moteurs sont les mêmes.</b> Le 0,19 de la première figure venait surtout de la période d'avant le 21/10.</p>
<h2>2. Ses mots suivent-ils son état réel (journalisé) ?</h2>
{reel}
<h2>3. Et l'état reconstruit, sur toute sa vie ?</h2>
{reco}
<h2>4. Avec un tour de retard (son état au tour précédent)</h2>
{prec}
<h2>5. Sa voix (30 morceaux)</h2>
<table><tr><th></th><th>Durée</th><th>Énergie (dB)</th><th>Hauteur (Hz)</th></tr>{voix}</table>
<p>Les 30 morceaux tiennent en 8 minutes, le 23/10 : sa valence n'y varie que de {ve[valence][0]} à {ve[valence][1]}, et son éveil de {ve[eveil][0]} à {ve[eveil][1]}.
On ne peut rien conclure : trop peu de morceaux, et un état presque constant.</p>
<h2>Pourquoi c'est faible</h2>
<ul>
<li><b>Ce n'est pas le modèle (voir 1)</b> : depuis le 21/10, l'état reconstruit suit le journalisé à 0,78.</li>
<li><b>Ses mots ne suivent presque pas son état</b> : ton contre valence réelle à 0,09, contre l'éveil à 0,12, contre les hormones à |0,12| au plus ; tous ces intervalles contiennent zéro. Avec un tour de retard, ce n'est pas mieux (0,08). Raisons probables : jusqu'au 22/10, son état ne lui arrivait que comme une ligne d'ambiance qu'il pouvait ignorer ; le [Réflexe et contrôle] n'existe que depuis le 22/10, et seulement quand l'humeur est marquée ; son humeur était presque toujours haute ; et ses mots répondent surtout au contenu du message d'Ahmed.</li>
<li><b>L'énergie de ses mots suit un peu sa valence</b> (0,17, intervalle au-dessus de zéro) : c'est le seul lien net, mais il est faible.</li>
<li><b>La longueur suit la valence (0,27)</b>, mais c'est sans doute un effet du temps : ses réponses ont raccourci le 22/10 (la règle « première phrase courte »), et sa valence a baissé le 23/10. Ce n'est probablement pas une humeur qui raccourcit ses phrases.</li>
<li><b>Sa voix</b> : l'expressivité et le débit dépendent déjà de son humeur, mais son humeur variait peu, et rien n'était mesuré avant ce matin.</li>
</ul>
<h2>Ce que les pistes de Hakim y changeraient</h2>
<ul>
<li><b>Le style</b> : des consignes concrètes (longueur des phrases, humour, chaleur, exclamations), calculées depuis son état à chaque tour, au lieu d'une ambiance : c'est ce qui manque pour que le ton suive.</li>
<li><b>La voix</b> : garder trois nombres par morceau, le débit lié à l'éveil en continu. Pour la hauteur seule, on n'a pas de vrai réglage : le débit la bouge de ±6 %.</li>
<li><b>La mesure</b> : le même tableau chaque semaine, sur des jours neufs, avec un objectif fixé avant.</li>
</ul>
</main></body></html>"""

if __name__ == "__main__":
    main()
