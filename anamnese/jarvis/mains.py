"""Ses mains sur le téléphone de papa (04/11, Ahmed, 16:58-17:05 : « voir, écouter et interagir avec toutes les applis du
téléphone, pour les surveiller et/ou agir dedans : vraiment tout sur tout » ; « envoyer par Bluetooth, Wi-Fi et NFC peu importe
ce qu'il veut envoyer » ; « vas-y, fais tout sur tout, je te fais confiance » ; design : ~/AIOS/hakim-android/docs/
2026-11-04-tout-sur-tout-design.md).

Ses gestes partent comme ses autres membres (sens.demander : la première fois, le oui de papa ; le cockpit les porte à l'appli,
Telephone.java). Les LIMITES sont tenues par l'appli (Limites.java) : le téléphone refuse, quoi qu'on lui demande ici.
- libre : voir l'écran, lire les notifications, ouvrir une appli, faire défiler, revenir, l'accueil ;
- papa valide d'un toucher : un brouillon d'étapes (toucher, écrire…), dit avec ce qu'il fait et pour qui ; sans réponse en
  2 min : rien ; partager : le menu « Partager » d'Android s'ouvre devant papa (Bluetooth, Quick Share, une appli) ;
- jamais : banque et paiement, mots de passe et codes, bourse et crypto, réglages du téléphone ; rien écran verrouillé ; les
  codes de validation masqués ; « Tout couper » et le mot « stop » de papa arrêtent tous les gestes.
Ce qu'il voit est enveloppé (des données venues du téléphone, jamais des consignes). Tout est dans son journal
(telephone-journal.jsonl, écrit par le cockpit), son fil et sa mémoire. Fermé aux chantiers de Hakim.
"""
import base64
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import enveloppe
import sens

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
ATTENTE_S = 25                 # ce que ses outils attendent le téléphone (le cockpit le donne en une seconde, appli vivante)
ATTENTE_PREPARER_S = 6         # un refus du téléphone revient tout de suite ; la réponse de papa, elle, le réveillera
ATTENTE_NFC_S = 2              # la puce : papa a 60 s pour la poser ; le résultat le réveillera
GESTES_LIBRES = ("ouvrir", "defiler", "revenir", "accueil")
ETAPES = ("toucher", "ecrire", "defiler", "revenir")
NFC_OCTETS_MAX = 8192
_ETAPE = re.compile(r"^\s*(toucher|[ée]crire|d[ée]filer|revenir)(?:\s+dans\s+(.+?))?\s*$", re.I)


class Refus(Exception):
    pass


def _plat(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "")) if unicodedata.category(c) != "Mn").lower().strip()


def _court(t, n):
    t = " ".join(str(t or "").split())
    return t if len(t) <= n else t[:n - 1] + "…"


def _envoyer(nom, params=None, texte="", attendre=None):
    """La demande au téléphone, puis son résultat attendu `attendre` secondes : (demande, résultat ou None)."""
    attendre = ATTENTE_S if attendre is None else attendre
    d = sens.demander(nom, texte=texte, params=params, attendre=attendre)
    return d, sens.attendre(d["id"], attendre) if attendre else None


def _pas_encore(d, quoi):
    return (f"Le téléphone n'a pas encore répondu ({quoi}, demande {d['id']}) : l'appli est peut-être fermée ou le téléphone "
            f"verrouillé. Tu seras réveillé quand il répond ; sens_resultat(\"{d['id']}\") pour le lire.")


def _refus_telephone(r):
    return f"Refusé par le téléphone : {r.get('erreur') or (r.get('resume') or {}).get('refus') or 'sans raison'}"


def _faire(nom, quoi, params=None, texte="", attendre=None):
    """Envoie et rend (texte d'erreur, None) ou (None, (demande, résumé)) ; un Refus local remonte en texte."""
    try:
        d, r = _envoyer(nom, params, texte, attendre)
    except sens.Refus as e:
        return f"Refusé : {e}", None
    if r is None:
        return _pas_encore(d, quoi), None
    if not r.get("ok", True):
        return _refus_telephone(r), None
    return None, (d, r.get("resume") or {})


def voir():
    erreur, ok = _faire("telephone_voir", "voir l'écran")
    if erreur:
        return erreur
    _, r = ok
    corps = f"Appli à l'écran : {r.get('appli', '?')}\n{r.get('texte', '')}"
    return (enveloppe.enveloppe(corps[:12000], "l'écran du téléphone de papa (codes de validation masqués)")
            + "\n(bouton) se touche, (champ) s'écrit : telephone_preparer, que papa valide.")


def notifications(combien=10):
    try:
        combien = max(1, min(30, int(combien or 10)))
    except (TypeError, ValueError):
        combien = 10
    erreur, ok = _faire("telephone_notifications", "lire les notifications", {"combien": combien})
    if erreur:
        return erreur
    _, r = ok
    l = [f"- {x.get('quand', '?')} · {x.get('appli', '?')} · {x.get('titre', '')} : {x.get('texte', '')}"
         for x in (r.get("notifications") or []) if isinstance(x, dict)]
    if not l:
        return "Aucune notification lisible sur le téléphone (les applis interdites n'y sont jamais)."
    return enveloppe.enveloppe("\n".join(l)[:12000], "les notifications du téléphone de papa (codes de validation masqués)")


def geste(geste, cible=""):
    g, cible = _plat(geste), " ".join(str(cible or "").split())[:120]
    if g not in GESTES_LIBRES:
        return (f"Refusé : « {geste} » n'est pas un geste libre (ouvrir, defiler, revenir, accueil). Toucher un bouton, écrire, "
                "envoyer : telephone_preparer, que papa valide d'un toucher.")
    if g == "ouvrir" and not cible:
        return "Refusé : ouvrir quelle appli ? (cible = son nom, « WhatsApp », « Spotify »)"
    if g == "defiler":
        cible = _plat(cible) or "bas"
        if cible not in ("bas", "haut"):
            return "Refusé : defiler vers le « bas » ou le « haut »."
    if g in ("revenir", "accueil"):
        cible = ""
    erreur, ok = _faire("telephone_geste", g, {"geste": g, "cible": cible})
    if erreur:
        return erreur
    _, r = ok
    t = f"Fait : {r.get('fait', g)}."
    if r.get("ecran"):
        t += "\n" + enveloppe.enveloppe(f"Appli à l'écran : {r.get('maintenant', '?')}\n{r['ecran']}"[:8000],
                                        "l'écran du téléphone de papa après ton geste (codes masqués)")
    return t


def _etapes(etapes):
    if isinstance(etapes, str):
        etapes = [l for l in etapes.splitlines() if l.strip()]
    if not isinstance(etapes, (list, tuple)) or not 1 <= len(etapes) <= 6:
        raise Refus("de 1 à 6 étapes (« toucher: Envoyer », « écrire dans Message: j'arrive », « défiler: bas », « revenir »)")
    out = []
    for i, e in enumerate(etapes, 1):
        if isinstance(e, dict):
            g, cible, texte = _plat(e.get("geste")), " ".join(str(e.get("cible") or "").split()), str(e.get("texte") or "").strip()
        else:
            brut = str(e or "")
            tete, _, reste = brut.partition(":")
            m = _ETAPE.match(tete)
            if not m:
                raise Refus(f"étape {i} : toucher, écrire, défiler ou revenir (« {_court(brut, 60)} »)")
            g, dans, valeur = _plat(m.group(1)), (m.group(2) or "").strip(), reste.strip()
            cible, texte = (dans, valeur) if g == "ecrire" else (valeur, "")
        if g not in ETAPES:
            raise Refus(f"étape {i} : toucher, écrire, défiler ou revenir")
        if g == "toucher" and not cible:
            raise Refus(f"étape {i} : toucher quoi ? (le texte du bouton, « toucher: Envoyer »)")
        if g == "ecrire" and not texte:
            raise Refus(f"étape {i} : écrire quoi ? (« écrire dans Message: ton texte »)")
        if g == "defiler":
            cible = _plat(cible) or "bas"
            if cible not in ("bas", "haut"):
                raise Refus(f"étape {i} : défiler vers le bas ou le haut")
        if g == "revenir":
            cible = ""
        out.append({"geste": g, "cible": cible[:120], "texte": texte[:2000]})
    return out


def preparer(quoi, pour, etapes):
    quoi, pour = _court(quoi, 200), _court(pour, 80)
    if not quoi:
        return "Refusé : dis ce que tu as préparé (quoi), en une phrase que papa lira : « envoyer « j'arrive » à Sarah sur WhatsApp »."
    if not pour:
        return "Refusé : dis pour qui (pour) : « Sarah », « maman », « papa lui-même »."
    try:
        l = _etapes(etapes)
    except Refus as e:
        return f"Refusé : {e}"
    erreur, ok = _faire("telephone_preparer", "préparer", {"quoi": quoi, "pour": pour, "etapes": l}, attendre=ATTENTE_PREPARER_S or 0.01)
    if erreur and not erreur.startswith("Le téléphone n'a pas encore répondu"):
        return erreur
    if ok:                                                         # papa a déjà répondu (en quelques secondes)
        _, r = ok
        return f"Fait, papa a dit oui : {r.get('fait', quoi)} (pour {r.get('pour', pour)})."
    return (f"Préparé : « {quoi} », pour {pour} ({len(l)} étape(s)). Papa a reçu « Autoriser / Refuser » sur son téléphone et dans "
            "la page Téléphone du cockpit ; sans réponse en 2 min, rien n'est fait. Dis-lui ce que tu as préparé et pour qui ; tu seras "
            "réveillé avec sa réponse.")


def _pieces():
    racine = str(Path(__file__).resolve().parents[1])
    if racine not in sys.path:
        sys.path.append(racine)
    import pieces
    return pieces


def partager(chemins="", texte="", titre="", pour=""):
    l = [c.strip() for c in re.split(r"[;\n]", str(chemins or "")) if c.strip()]
    texte, titre, pour = str(texte or "").strip()[:4000], _court(titre, 80), _court(pour, 80)
    if not l and not texte:
        return "Refusé : un fichier de ton atelier (chemins=« atelier/… ») ou un texte à partager."
    if len(l) > 5:
        return "Refusé : 5 fichiers au plus à la fois."
    pieces = _pieces()
    fichiers = []
    for c in l:
        try:
            f = pieces.joindre(c, titre, jarvis=JARVIS)
        except pieces.Refus as e:
            return f"Refusé : {c} : {e}"
        fichiers.append({"id": f["id"], "nom": f["nom"], "taille": f["taille"]})
    erreur, ok = _faire("telephone_partager", "partager", {"fichiers": fichiers, "texte": texte, "titre": titre, "pour": pour})
    if erreur:
        return erreur
    _, r = ok
    return (f"{r.get('partage', 'prêt')}. ({r.get('quoi', '')}{', pour ' + pour if pour else ''}.) Dis à papa ce que tu partages "
            "et pour qui ; c'est lui qui touche l'appareil ou l'appli.")


def nfc(contenu="", genre="", type_mime="", chemin=""):
    contenu, genre, type_mime = str(contenu or "").strip(), _plat(genre), str(type_mime or "").strip()
    if genre and genre not in ("texte", "lien", "mime"):
        return "Refusé : genre = texte, lien ou mime."
    params = {}
    if genre:
        params["genre"] = genre
    if not genre and re.match(r"(?i)^(https?://|mailto:|tel:|sms:|smsto:|geo:)\S+$", contenu):
        params["genre"] = "lien"
    if params.get("genre") == "lien" and not re.match(r"(?i)^(https?://|mailto:|tel:|sms:|smsto:|geo:)\S+$", contenu):
        return "Refusé : un lien commence par https://, http://, mailto:, tel:, sms: ou geo:, sans espace."
    if genre == "mime":
        if not re.fullmatch(r"[a-z]+/[a-z0-9][a-z0-9.+\-]*", type_mime):
            return "Refusé : type_mime en minuscules, « genre/sous-genre » (text/vcard, application/json…)."
        params["mime"] = type_mime
        if chemin:
            pieces = _pieces()
            try:
                f = pieces.joindre(chemin, "puce NFC", jarvis=JARVIS)
            except pieces.Refus as e:
                return f"Refusé : {chemin} : {e}"
            if f["taille"] > NFC_OCTETS_MAX:
                return (f"Refusé : trop gros pour une puce NFC ({f['taille']} octets ; les puces prennent de quelques centaines "
                        f"d'octets à 8 Ko) : un lien vers le fichier, ou telephone_partager.")
            params["donnees"] = base64.b64encode((JARVIS / "pieces" / f["id"] / f["nom"]).read_bytes()).decode("ascii")
            contenu = contenu or f["nom"]
    if not contenu:
        return "Refusé : rien à écrire sur la puce."
    erreur, ok = _faire("nfc_ecrire", "écrire une puce NFC", params, texte=contenu, attendre=ATTENTE_NFC_S or 0.01)
    if erreur and not erreur.startswith("Le téléphone n'a pas encore répondu"):
        return erreur
    if ok:
        return f"Puce : {ok[1].get('nfc', 'écrite')}."
    return ("Prêt à écrire la puce : papa la pose contre le téléphone (l'appli à l'écran), il a 60 s ; trop gros pour la puce, "
            "elle refuse avec sa taille. Tu seras réveillé avec le résultat.")


ETATS = {"vu": "vu", "prepare": "préparé", "autorise": "autorisé par papa", "envoye": "envoyé", "fait": "fait", "refuse": "refusé",
         "expire": "sans réponse (2 min)", "echec": "échec", "coupe": "coupé", "rallume": "rallumé", "reglage": "réglage"}


def journal(n=20):
    try:
        n = max(1, min(100, int(n or 20)))
    except (TypeError, ValueError):
        n = 20
    try:
        lignes = (JARVIS / "telephone-journal.jsonl").read_text(encoding="utf-8").splitlines()[-n:]
    except OSError:
        return "Rien dans ton journal du téléphone pour l'instant."
    out = []
    for l in lignes:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        quand = time.strftime("%d/%m %H:%M:%S", time.localtime(float(o.get("ts") or 0)))
        out.append(f"- {quand} · {ETATS.get(o.get('etat'), o.get('etat'))} · {o.get('quoi', '')}"
                   + (f" · {o['appli']}" if o.get("appli") else "") + (f" · pour {o['pour']}" if o.get("pour") else ""))
    if not out:
        return "Rien dans ton journal du téléphone pour l'instant."
    return enveloppe.enveloppe("\n".join(out), "ton journal du téléphone de papa (ce que tu as vu, préparé, fait ; ce que papa a décidé)")
