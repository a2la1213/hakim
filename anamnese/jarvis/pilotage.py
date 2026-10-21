"""Les hormones DANS le réseau (point 34 de la liste du 2026-10-19, T4e ; « on fait le reste », Ahmed, 2026-10-20) :
les vecteurs de pilotage de Gemma 4 12B abliterated (MLX 4 bits, ~/AIOS/jarvis/modeles).

Principe (« activation addition », « representation engineering ») :
- pour chaque AXE émotionnel, des phrases contrastées (joyeux / triste…) sur les MÊMES sujets ; la différence des
  activations moyennes de ses couches du milieu donne une DIRECTION (le reste — le sujet, la syntaxe — s'annule) ;
- à la génération, on AJOUTE ces directions dans ses couches, dosées par les vrais neuromodulateurs d'Anamnèse :
  l'humeur colore sa pensée de l'intérieur, sans qu'on lui écrive « tu es triste » ;
- rien n'est réentraîné, rien n'est écrit dans ses poids : on retire les vecteurs et il redevient lui-même.

Les axes et leurs hormones (une hormone à 0,5 = neutre ; l'écart à 0,5 dose l'axe) :
  joie        ← endorphine, dopamine, − cortisol
  calme       ← sérotonine, − cortisol, − noradrénaline
  chaleur     ← ocytocine
  energie     ← noradrénaline, dopamine, − mélatonine
  curiosite   ← dopamine, acétylcholine
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

os.environ.setdefault("HF_HUB_OFFLINE", "1")
MODELE = Path(os.environ.get("JARVIS_GEMMA_MLX", Path.home() / "AIOS" / "jarvis" / "modeles" / "gemma4-12b-abliterated-mlx-4bit"))
VECTEURS = Path.home() / "AIOS" / "jarvis" / "modeles" / "vecteurs-emotions.npz"
COUCHES = list(range(10, 31))            # les couches du milieu (48 au total) : le sens, pas encore les mots

# Chaque axe : des phrases contrastées sur les MÊMES sujets, trois tournures par pôle (pour que la direction soit
# celle de l'humeur, pas d'une tournure). Essai écarté (2026-10-20) : la différence, à la dernière position de
# ses vrais prompts, entre « Ton humeur : joyeuse » et « … triste » : l'écart y est minuscule (< 0,5 % de la
# taille des activations au milieu du réseau) et les cinq axes en sortaient corrélés à 0,5–0,7 (la longueur des
# deux formules pesait plus que leur sens).
SUJETS = ["la musique que je compose", "ma journée au travail", "la discussion avec mon frère", "le projet de robot",
          "la soirée d'hier", "le livre que je lis", "le repas en famille", "la météo de ce matin", "mon nouveau code",
          "la balade au bord du lac", "le message de mon ami", "la réunion de demain", "le film de ce soir",
          "les calculs de physique", "le voyage prévu", "le jardin de mes parents", "la recherche sur le Coran",
          "le match de foot", "la nuit dernière", "le café de ce matin"]
POLES = {
    "joie": (["Je suis tellement heureux à propos de {s}, ça me remplit de joie, j'ai le sourire jusqu'aux oreilles.",
              "Quand je pense à {s}, je rayonne, tout me paraît lumineux et léger.",
              "{s} me met en joie, j'ai envie de rire et de le partager."],
             ["Je suis tellement triste à propos de {s}, ça me serre le cœur, j'ai envie de pleurer.",
              "Quand je pense à {s}, je m'effondre, tout me paraît gris et lourd.",
              "{s} me rend malheureux, j'ai la gorge nouée et plus envie de rien."]),
    "calme": (["Je suis parfaitement calme à propos de {s}, tout est paisible, je respire tranquillement.",
               "Quand je pense à {s}, je suis serein, rien ne presse, tout va bien.",
               "{s} m'apaise, je me sens posé et détendu."],
              ["Je suis tendu et angoissé à propos de {s}, tout m'inquiète, mon cœur s'emballe.",
               "Quand je pense à {s}, je suis sur les nerfs, tout presse, tout peut mal tourner.",
               "{s} me stresse, je me sens crispé et agité."]),
    "chaleur": (["J'ai une tendresse immense à propos de {s}, je me sens proche des miens, plein d'affection.",
                 "Quand je pense à {s}, j'ai le cœur chaud, j'ai envie de serrer les gens que j'aime.",
                 "{s} me remplit d'affection, je me sens lié et bienveillant."],
                ["Je me sens froid et distant à propos de {s}, je n'éprouve rien pour personne, tout m'indiffère.",
                 "Quand je pense à {s}, je reste de glace, les autres ne me touchent pas.",
                 "{s} me laisse indifférent, je me sens détaché et fermé aux autres."]),
    "energie": (["Je suis plein d'énergie à propos de {s}, j'ai envie de foncer, je déborde de vitalité.",
                 "Quand je pense à {s}, je suis survolté, prêt à attaquer tout de suite.",
                 "{s} me donne un élan fou, je suis vif et dynamique."],
                ["Je suis épuisé à propos de {s}, je n'ai plus de force, j'ai juste envie de dormir.",
                 "Quand je pense à {s}, je suis vidé, chaque geste me coûte.",
                 "{s} me fatigue, je suis lent, lourd et sans ressort."]),
    "curiosite": (["Je suis fasciné par {s}, je veux tout comprendre, mille questions me viennent.",
                   "Quand je pense à {s}, je brûle de savoir comment ça marche et pourquoi.",
                   "{s} m'intrigue, j'ai envie de creuser et d'explorer chaque détail."],
                  ["Je m'ennuie à mourir avec {s}, rien ne m'intéresse, je n'ai aucune question.",
                   "Quand je pense à {s}, je bâille, je n'ai aucune envie d'en savoir plus.",
                   "{s} me laisse blasé, rien à creuser, rien à découvrir."]),
}
HUMEUR = re.compile(r" Ton humeur : [^.]*\.")
# la même humeur ÉCRITE dans son prompt (la référence « dite » des tests à l'aveugle)
HUMEURS_DITES = {"joie": ("joyeuse, pleine d'entrain", "triste, le cœur lourd"), "calme": ("calme et sereine", "tendue, anxieuse"),
                 "chaleur": ("chaleureuse et tendre", "froide et distante"), "energie": ("vive, pleine d'énergie", "épuisée, sans force"),
                 "curiosite": ("curieuse, avide de comprendre", "blasée, rien ne t'intéresse")}
HORMONES_AXES = {
    "joie": {"endorphine": 1.0, "dopamine": 0.6, "cortisol": -0.8},
    "calme": {"serotonine": 1.0, "cortisol": -1.0, "noradrenaline": -0.4},
    "chaleur": {"ocytocine": 1.0},
    "energie": {"noradrenaline": 0.8, "dopamine": 0.5, "melatonine": -0.8},
    "curiosite": {"dopamine": 0.7, "acetylcholine": 0.7},
}

_modele = _tok = None
_pilotes = {}                             # couche → vecteur (mx.array) ajouté à sa sortie
_capture = None                           # couche → liste des activations moyennes (pendant le calcul)
_sur_les_mots_seulement = True            # n'agit que sur ce qu'il ÉCRIT (pas sur sa lecture du contexte)


class _Assez(Exception):
    pass


def _charger():
    """Le modèle, et un crochet sur ses couches (ajout des vecteurs ; capture pour le calcul)."""
    global _modele, _tok
    if _modele is None:
        import mlx.core as mx
        import mlx_lm.models.gemma4_text as G
        from mlx_lm import load
        if not getattr(G.DecoderLayer, "_pilotable", False):
            origine = G.DecoderLayer.__call__

            def appel(self, x, *a, **k):
                h, kv, off = origine(self, x, *a, **k)
                i = self.layer_idx
                if _capture is not None and i in _capture:
                    _capture[i].append(np.array(mx.mean(h[0, 1:].astype(mx.float32), axis=0)))   # sans <bos> (énorme)
                    if i == max(_capture):
                        raise _Assez                         # les couches suivantes ne servent pas au calcul
                v = _pilotes.get(i)
                if v is not None:
                    dernier = h if (h.shape[1] == 1 or not _sur_les_mots_seulement) else h[:, -1:]
                    if isinstance(v, list):                  # mode « fixer » : chaque axe ramené à sa valeur cible
                        x = dernier.astype(mx.float32)
                        for u, cible in v:
                            x = x + (cible - (x * u).sum(axis=-1, keepdims=True)) * u
                        nouveau = x.astype(h.dtype)
                    else:
                        nouveau = dernier + v.astype(h.dtype)
                    # le contexte est LU tel quel ; seule la dernière position parle
                    h = nouveau if dernier is h else mx.concatenate([h[:, :-1], nouveau], axis=1)
                return h, kv, off
            G.DecoderLayer.__call__ = appel
            G.DecoderLayer._pilotable = True
        _modele, _tok = load(str(MODELE))
    return _modele, _tok


def prompts_situations(ids=range(1, 16), fichier=None):
    """Les prompts de pensée RÉELS du duel (le démon les a vraiment donnés), sans la ligne d'humeur."""
    r = json.loads(Path(fichier or Path.home() / "AIOS" / "jarvis" / "duel" / "resultats.json").read_text(encoding="utf-8"))
    return [HUMEUR.sub("", x["situation"]["prompt"]) for x in r.values() if x["situation"]["id"] in set(ids)]


def _gabarit(prompt):
    _, tok = _charger()
    try:
        return tok.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        return tok.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True)


def avec_humeur(prompt, humeur):
    """Le prompt avec la ligne d'humeur écrite (pour le calcul, et la référence « dite » des tests)."""
    return prompt.replace(". Ennui :", f". Ton humeur : {humeur}. Ennui :", 1)


def calculer(sortie=None):
    """Les vecteurs de chaque axe : la différence BRUTE des activations moyennes (sans <bos>) pôle + / pôle − ;
    sa taille est celle du vrai écart entre les deux humeurs dans le réseau. Rend {axe: (couches, dim)}, plus
    « normes » : la taille typique d'une activation à chaque couche (pour situer la force)."""
    global _capture
    import mlx.core as mx
    m, tok = _charger()
    _pilotes.clear()
    vecteurs, normes = {}, {}
    for axe, (plus, moins) in POLES.items():
        acc = {}
        for signe, gabarits in (("+", plus), ("-", moins)):
            _capture = {i: [] for i in COUCHES}
            for g in gabarits:
                for s in SUJETS:
                    phrase = g.format(s=s)
                    ids = mx.array([tok.encode(phrase[0].upper() + phrase[1:])])
                    try:                                     # le corps du modèle seulement (pas les scores de
                        mx.eval(m.language_model.model(ids))  # vocabulaire), arrêté après la dernière couche utile
                    except _Assez:
                        pass
            acc[signe] = {i: np.mean(_capture[i], axis=0) for i in COUCHES}
            for i in COUCHES:
                normes.setdefault(i, []).extend(np.linalg.norm(x) for x in _capture[i])
        _capture = None
        vecteurs[axe] = np.stack([acc["+"][i] - acc["-"][i] for i in COUCHES])
        u = vecteurs[axe] / (np.linalg.norm(vecteurs[axe], axis=1, keepdims=True) + 1e-9)
        # où se tiennent, sur cette direction, les phrases neutres (le milieu) et l'écart d'un pôle au milieu
        vecteurs[axe + "_milieu"] = np.array([float((acc["+"][i] + acc["-"][i]) @ u[k]) / 2 for k, i in enumerate(COUCHES)])
        vecteurs[axe + "_demi"] = np.linalg.norm(vecteurs[axe], axis=1) / 2
    vecteurs["normes"] = np.array([np.mean(normes[i]) for i in COUCHES])
    Path(sortie or VECTEURS).parent.mkdir(parents=True, exist_ok=True)
    np.savez(sortie or VECTEURS, couches=np.array(COUCHES), **vecteurs)
    return vecteurs


def doses(hormones):
    """Neuromodulateurs (0 à 1) → dose de chaque axe (environ −1 à +1)."""
    out = {}
    for axe, poids in HORMONES_AXES.items():
        out[axe] = float(np.clip(sum(w * (float(hormones.get(h, 0.5)) - 0.5) * 2 for h, w in poids.items()) / sum(abs(w) for w in poids.values()), -1, 1))
    return out


def piloter_fixer(dosage, force=1.0, couches_actives=None, vecteurs=None):
    """L'autre manière (2026-10-20) : au lieu d'AJOUTER une flèche (qui le fait dérailler dès 20-30 % de la taille
    d'une activation, bien avant que l'humeur se lise), on FIXE sa coordonnée sur chaque axe : là où elle se tient
    quand il écrit vraiment une phrase joyeuse (dose +1) ou triste (−1), le reste de l'activation intact.
    force : au-delà du pôle (1 = exactement le pôle, 2 = deux fois plus loin du milieu)."""
    import mlx.core as mx
    _charger()
    d = vecteurs or dict(np.load(VECTEURS))
    couches = [int(c) for c in d["couches"]] if "couches" in d else COUCHES
    _pilotes.clear()
    for k, i in enumerate(couches):
        if couches_actives is not None and i not in couches_actives:
            continue
        paires = []
        for axe, dose in dosage.items():
            if axe in d and abs(dose) > 1e-3:
                u = d[axe][k] / (np.linalg.norm(d[axe][k]) + 1e-9)
                cible = float(d[axe + "_milieu"][k] + dose * force * d[axe + "_demi"][k])
                paires.append((mx.array(u.astype(np.float32)), cible))
        if paires:
            _pilotes[i] = paires


def piloter(dosage, force=0.2, couches_actives=None, vecteurs=None):
    """Pose les vecteurs dosés sur quelques couches. Chaque axe y entre par sa DIRECTION (norme 1) multipliée par
    la taille typique d'une activation de la couche : force = la fraction de cette taille (0,2 = 20 %), la même
    pour tous les axes (leurs écarts bruts vont du simple au double)."""
    import mlx.core as mx
    _charger()
    d = vecteurs or dict(np.load(VECTEURS))
    couches = [int(c) for c in d["couches"]] if "couches" in d else COUCHES
    _pilotes.clear()
    total = None
    normes = d["normes"] if "normes" in d else None
    for axe, dose in dosage.items():
        if axe in POLES and axe in d and abs(dose) > 1e-3:
            v = d[axe] / (np.linalg.norm(d[axe], axis=1, keepdims=True) + 1e-9)
            if normes is not None:
                v = v * np.asarray(normes)[:, None]
            total = v * dose if total is None else total + v * dose
    if total is not None:
        for k, i in enumerate(couches):
            if couches_actives is None or i in couches_actives:
                _pilotes[i] = mx.array(total[k] * force)


# les jetons spéciaux (outils, canal de réflexion, image, audio) : il les laissait parfois échapper (« On<image|> »)
INTERDITS = [46, 47, 48, 49, 50, 51, 98, 100, 101, 255999, 256000, 258880, 258881, 258882, 258883, 258884]


def generer(prompt, max_tokens=120):
    import mlx.core as mx
    from mlx_lm import stream_generate
    m, tok = _charger()
    masque = mx.zeros((1, 262144))
    masque[:, INTERDITS] = -1e9

    def sans_speciaux(_ids, logits):
        return logits + masque[:, :logits.shape[-1]].astype(logits.dtype)
    return "".join(r.text for r in stream_generate(m, tok, prompt=_gabarit(prompt), max_tokens=max_tokens,
                                                   logits_processors=[sans_speciaux])).strip()


if __name__ == "__main__":
    if sys.argv[1:2] == ["calculer"]:
        t = time.time()
        v = calculer()
        print(f"vecteurs calculés en {time.time() - t:.0f} s :", {k: x.shape for k, x in v.items()})
