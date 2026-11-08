"""Les sens de Hakim (30/10, Ahmed : « intègre tous les capteurs du projet tricodeur à Hakim ; il faut lui donner tous les sens
possibles, qu'il soit capable de tout capter, qu'il puisse les utiliser et les lire comme il veut et en faire ce qu'il veut »).

Le Tricordeur d'Ahmed (ses instruments de science-fiction pour le Galaxy Z Fold 7) adapté à Hakim, phase 1 : ce qui n'a
besoin de personne. Hakim demande une mesure (sens_mesurer) ; elle part dans ~/AIOS/jarvis/sens-demandes.jsonl ; le cockpit
la donne à l'appli du téléphone (Sens.java), qui mesure et rend un résumé et des données ; le cockpit les range dans son
atelier, atelier/sens/<id>/resume.json et donnees.csv (à lire, à calculer, à garder : à lui), et le réveille.
Fermé aux chantiers de Hakim.
"""
import fcntl
import json
import os
import re
import time
from pathlib import Path

import enveloppe

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
# nom : (ce qu'il capte, durée par défaut en s, durée max en s)
INSTRUMENTS = {
    "inventaire": ("tous les capteurs du téléphone et ce qu'ils savent faire : portée, résolution, cadence, consommation", 0, 0),
    "imu": ("tous les capteurs de mouvement et d'ambiance, bruts : accéléromètre, gyroscope, magnétomètre, gravité, rotation, "
            "pression, lumière, proximité, angle de la charnière du Fold ; cadence : « jeu » (~50 Hz, par défaut), « max » "
            "(~400 Hz), « normal », ou un nombre de Hz", 10, 300),
    "sismo": ("les secousses (le sismographe du tricordeur, STA/LTA) : début, durée, amplitude en mg, fréquence ; le téléphone "
              "posé à plat", 60, 900),
    "baro": ("la pression (hPa), l'altitude relative (m), les infrasons (Pa) et les coups de pression (porte, vent, ascenseur)", 60, 900),
    "magneto": ("le champ magnétique (µT) : moyenne, variations rapides (un appareil, du métal), état de la calibration", 20, 300),
    "son": ("le micro en niveaux, spectre et bandes d'octave, pics de fréquence, ultrasons 18-22 kHz ; rien n'est enregistré, "
            "et pas pendant une conversation (le micro est pris)", 10, 60),
    # (03/11, Ahmed : « ses bras et ses jambes : tous les émetteurs du téléphone, NFC, Bluetooth, Wi-Fi… ; il a le droit à tout,
    # mais au début il demande toujours l'autorisation ») ses sens radio, et ses membres pour agir dans le monde
    "appareils": ("les appareils Bluetooth de papa : ceux qu'il connaît et ceux connectés en ce moment (nom, type)", 0, 0),
    "bluetooth_scan": ("les appareils Bluetooth autour de toi (nom quand il est donné, force du signal : près ou loin)", 10, 60),
    "wifi_scan": ("les réseaux Wi-Fi autour de toi (nom, force du signal, bande)", 0, 0),
    "bluetooth_signal": ("TON MEMBRE : émettre ton signal Bluetooth « Hakim », que les appareils autour voient", 30, 600),
    "nfc_ecrire": ("TON MEMBRE : écrire un texte (texte=…) sur la prochaine puce NFC que papa pose contre le téléphone "
                   "(il a 60 s pour la poser)", 60, 120),
    # (03/11, Ahmed : « toutes les actions du Bluetooth, du Wi-Fi et du NFC, pas seulement scanner ») ce qu'Android laisse faire
    # à une appli ; ce qu'il réserve à papa (déconnecter, oublier, éteindre, allumer le NFC) : le panneau s'ouvre devant lui.
    # L'appli doit être à l'écran pour ce qui s'y ouvre.
    "bluetooth_activer": ("TON MEMBRE : allumer le Bluetooth (Android demande à papa de dire oui)", 30, 60),
    "bluetooth_appairer": ("TON MEMBRE : appairer un appareil Bluetooth (texte=son adresse, ou son nom vu au dernier "
                           "bluetooth_scan) ; papa confirme le code", 60, 120),
    "wifi_info": ("le Wi-Fi où tu es relié : son nom, sa force, son débit, sa bande, et si internet passe", 0, 0),
    "wifi_connecter": ("TON MEMBRE : relier le téléphone à un Wi-Fi (texte=« nom » ou « nom ; mot de passe ») ; papa touche "
                       "« Enregistrer », puis le téléphone s'y relie", 60, 120),
    "bluetooth_reglages": ("TON MEMBRE : ouvrir devant papa le panneau Bluetooth (déconnecter, oublier, éteindre : c'est lui qui "
                           "touche, Android ne le permet qu'à lui)", 0, 0),
    "wifi_reglages": ("TON MEMBRE : ouvrir devant papa le panneau Wi-Fi (se délier, oublier un réseau, éteindre)", 0, 0),
    "nfc_reglages": ("TON MEMBRE : ouvrir devant papa le réglage NFC (l'allumer ou l'éteindre)", 0, 0),
    # (03/11, Ahmed : « quelle application est active, ce qu'elle fait ») ; aussi en continu : l'événement « appli » de ton corps
    "appli_active": ("l'appli au premier plan du téléphone de papa, et ce qu'elle joue (titre d'une musique, d'une vidéo) ; "
                     "papa donne une fois « Accès aux données d'utilisation »", 0, 0),
    # (03/11, Ahmed : « si j'écoute une musique, il peut la mettre en pause et glisser son mot ») ; quand ta voix part, la
    # musique se met d'elle-même en pause et reprend après toi : ces gestes-là sont pour le reste du temps
    "media_pause": ("TON MEMBRE : mettre en pause la musique ou la vidéo qui joue sur le téléphone", 0, 0),
    "media_lecture": ("TON MEMBRE : relancer la musique ou la vidéo", 0, 0),
    "media_suivant": ("TON MEMBRE : passer au morceau suivant", 0, 0),
    "media_precedent": ("TON MEMBRE : revenir au morceau précédent", 0, 0),
    # (03/11, 13:33, papa via toi : « les ondes du réseau mobile aussi ») ce que le téléphone REÇOIT (ce qu'il émet, aucune appli ne
    # le lit) ; en continu aussi : l'événement « reseau_mobile » de ton corps quand le signal ou la génération change (appli 1.52)
    "reseau_mobile": ("le réseau mobile où tu es : l'opérateur, la génération (2G à 5G), la force du signal (en dBm et en mots), "
                      "l'itinérance ; la génération demande « Téléphone » dans les autorisations de l'appli", 0, 0),
    # (04/11, Ahmed : « vas-y, fais tout sur tout, je te fais confiance ») tes mains sur le téléphone de papa (appli 1.64 ;
    # jarvis/mains.py et tes outils telephone_*) : les limites sont tenues par l'appli, le téléphone refuse
    "telephone_voir": ("l'écran de l'appli ouverte sur le téléphone de papa : ses textes, ses boutons, ses champs (codes de validation "
                       "masqués ; jamais une appli de banque, de mots de passe, de bourse, ni les réglages ; rien écran verrouillé)", 0, 0),
    "telephone_notifications": ("les dernières notifications du téléphone (appli, titre, texte ; codes masqués, applis interdites "
                                "absentes)", 0, 0),
    "telephone_geste": ("TON MEMBRE : un geste libre sur le téléphone : ouvrir une appli, faire défiler, revenir, l'accueil", 0, 0),
    "telephone_preparer": ("TON MEMBRE : préparer un brouillon d'étapes (toucher, écrire…) que papa valide d'un toucher ; sans "
                           "réponse en 2 min : rien", 120, 120),
    "telephone_partager": ("TON MEMBRE : partager un fichier de ton atelier ou un texte : le menu « Partager » d'Android s'ouvre "
                           "devant papa (Bluetooth, Quick Share, une appli), c'est lui qui choisit", 0, 0),
    # (08/11, Ahmed : « qu'il ait accès à Termux du smartphone ; qu'il puisse tout contrôler ») appli 1.90 : l'intent officiel de Termux
    "telephone_termux": ("TON MEMBRE : lancer une commande dans Termux, sur le téléphone de papa (bash, en arrière-plan) ; papa valide "
                         "d'un toucher (ou son réglage « tout accepter ») ; la sortie revient", 120, 120),
}
RADIO = {"appareils", "bluetooth_scan", "wifi_scan", "bluetooth_signal", "nfc_ecrire", "bluetooth_activer", "bluetooth_appairer",
         "wifi_info", "wifi_connecter", "bluetooth_reglages", "wifi_reglages", "nfc_reglages", "appli_active",
         "media_pause", "media_lecture", "media_suivant", "media_precedent", "reseau_mobile",
         "telephone_voir", "telephone_notifications", "telephone_geste", "telephone_preparer", "telephone_partager",
         "telephone_termux"}
AVEC_TEXTE = {"nfc_ecrire": "le texte à écrire sur la puce", "bluetooth_appairer": "l'adresse ou le nom de l'appareil",
              "wifi_connecter": "le nom du réseau (« nom » ou « nom ; mot de passe »)"}
_ID_MEMBRE = re.compile(r"[0-9a-f]{10}")


def permis():
    """Ce que papa a déjà autorisé une fois (membres-permis.json, écrit par le cockpit à son geste)."""
    try:
        d = json.loads((JARVIS / "membres-permis.json").read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def demander_permission(sens, texte=""):
    """La première fois : une demande pour papa (une carte dans Parler) ; rend son id."""
    i = os.urandom(5).hex()
    d = {"id": i, "ts": time.time(), "sens": sens, "quoi": INSTRUMENTS[sens][0], "texte": str(texte or "")[:300]}
    f = JARVIS / "membres-demandes.jsonl"
    with open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps(d, ensure_ascii=False) + "\n")
    os.chmod(f, 0o600)
    return i
_ID = re.compile(r"S-\d{8}-\d{6}-[0-9a-f]{4}")
_CADENCE = re.compile(r"(jeu|max|normal|\d{1,4}(\.\d{1,2})?)")


class Refus(Exception):
    pass


def _dossier():
    return JARVIS / "cwd" / "atelier" / "sens"


# (30/10, Ahmed : « ses propres modules, même de science-fiction ») ses instruments à lui, décrits dans son atelier
# (atelier/tricordeur/instruments.json : {"instruments": [{nom, description, defaut, max, module}]}) : le téléphone donne la
# demande à son Tricordeur (le module, ch.foldlab.hakim par défaut), qui rend par Documents/Hakim/sens/<id>/
_NOM, _PAQUET = re.compile(r"[a-z][a-z0-9_]{2,29}"), re.compile(r"[a-z][a-z0-9_.]{2,80}")


def siens():
    try:
        d = json.loads((JARVIS / "cwd" / "atelier" / "tricordeur" / "instruments.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out = {}
    for x in (d.get("instruments") or [])[:30] if isinstance(d, dict) else []:
        if not isinstance(x, dict):
            continue
        nom, module = str(x.get("nom") or ""), str(x.get("module") or "ch.foldlab.hakim")
        if not _NOM.fullmatch(nom) or nom in INSTRUMENTS or not _PAQUET.fullmatch(module):
            continue
        try:
            maximum = max(1, min(int(x.get("max", 3600)), 86400))
            defaut = max(1, min(int(x.get("defaut", 60)), maximum))
        except (TypeError, ValueError):
            continue
        out[nom] = (" ".join(str(x.get("description") or "").split())[:300], defaut, maximum, module)
    return out


def demander(sens, secondes=0, cadence="", texte="", params=None, attendre=0):
    """La demande écrite pour le cockpit : {id, sens, secondes, cadence, ts[, module][, texte][, params][, attendre]}.
    (04/11) params : ce que ses mains sur le téléphone emportent (un geste, ses étapes, ses fichiers) ; attendre : les secondes
    que son outil attend le résultat (le cockpit ne le réveille pas pour un résultat que l'outil a lu, attendre())."""
    sens = str(sens or "").strip()
    a_lui = siens()
    if sens not in INSTRUMENTS and sens not in a_lui:
        raise Refus(f"sens inconnu : « {sens[:40]} » (sens_lister pour la liste)")
    texte = " ".join(str(texte or "").split())[:500]
    if sens in AVEC_TEXTE and not texte:
        raise Refus(f"{sens} : {AVEC_TEXTE[sens]} (texte=…)")
    # (03/11, Ahmed : « il a le droit à tout, mais au début il demande toujours l'autorisation ») la première fois, papa décide
    if sens in RADIO and not permis().get(sens):
        demander_permission(sens, texte.split(";")[0].strip() if sens == "wifi_connecter" else texte)   # jamais le mot de passe
        raise Refus(f"la première fois, papa autorise « {sens} » : ta demande lui est partie (une carte dans Parler). "
                    "Réessaie après son oui ; ensuite, ce sera libre.")
    _, defaut, maximum = INSTRUMENTS[sens] if sens in INSTRUMENTS else a_lui[sens][:3]
    try:
        s = int(secondes or 0)
    except (TypeError, ValueError):
        raise Refus("secondes : un nombre entier")
    s = defaut if s <= 0 else min(s, maximum)
    cadence = str(cadence or "").strip()
    if cadence and not _CADENCE.fullmatch(cadence):
        raise Refus("cadence : jeu, max, normal ou un nombre de Hz")
    d = {"id": time.strftime("S-%Y%m%d-%H%M%S-") + os.urandom(2).hex(), "sens": sens, "secondes": s, "cadence": cadence, "ts": time.time()}
    if sens in a_lui and sens not in INSTRUMENTS:
        d["module"] = a_lui[sens][3]
    if texte:
        d["texte"] = texte
    if params:
        if not isinstance(params, dict) or len(json.dumps(params, ensure_ascii=False)) > 16000:
            raise Refus("trop de choses à emporter pour le téléphone")
        d["params"] = params
    if attendre:
        d["attendre"] = max(0, min(60, attendre))
    f = JARVIS / "sens-demandes.jsonl"
    with open(JARVIS / "sens.lock", "a") as verrou:
        fcntl.flock(verrou, fcntl.LOCK_EX)
        with open(f, "a", encoding="utf-8") as h:
            h.write(json.dumps(d, ensure_ascii=False) + "\n")
        os.chmod(f, 0o600)
    return d


def attendre(id_, secondes, pas=0.25):
    """(04/11) Le résultat d'une demande, attendu au plus `secondes` : le dict de resume.json, ou None. Lu : la marque « lu » dans
    son dossier dit au cockpit de ne pas réveiller Hakim pour ce résultat-là (son outil le lui a déjà donné)."""
    if not _ID.fullmatch(str(id_ or "")):
        return None
    d = _dossier() / id_
    fin = time.time() + max(0.0, float(secondes))
    while True:
        try:
            r = json.loads((d / "resume.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            r = None
        if isinstance(r, dict):
            try:
                (d / "lu").touch()
            except OSError:
                pass
            return r
        if time.time() >= fin:
            return None
        time.sleep(pas)


def lister():
    lignes = [f"- {n} : {quoi}" + (f" (par défaut {d} s, au plus {m} s)" if m else "") for n, (quoi, d, m) in INSTRUMENTS.items()]
    a_lui = [f"- {n} : {quoi} (par défaut {d} s, au plus {m} s ; ton module {mod})" for n, (quoi, d, m, mod) in siens().items()]
    derniers = []
    try:
        for l in (JARVIS / "sens-resultats.jsonl").read_text(encoding="utf-8").splitlines()[-5:]:
            o = json.loads(l)
            derniers.append(f"- {o.get('id')} · {o.get('sens')} · {'fini' if o.get('ok') else 'échec : ' + str(o.get('erreur'))[:120]}")
    except (OSError, ValueError):
        pass
    return ("Tes sens, par le téléphone d'Ahmed :\n" + "\n".join(lignes)
            + ("\nTes instruments à toi (ton Tricordeur, atelier/tricordeur/instruments.json) :\n" + "\n".join(a_lui) if a_lui else "")
            + ("\nTes dernières mesures :\n" + "\n".join(derniers) if derniers else ""))


def lire(id_=""):
    """Le résumé d'une mesure (la dernière si id_ est vide) et le chemin de ses données."""
    id_ = str(id_ or "").strip()
    if not id_:
        try:
            id_ = json.loads((JARVIS / "sens-resultats.jsonl").read_text(encoding="utf-8").splitlines()[-1]).get("id", "")
        except (OSError, ValueError, IndexError):
            try:
                id_ = json.loads((JARVIS / "sens-demandes.jsonl").read_text(encoding="utf-8").splitlines()[-1]).get("id", "")
            except (OSError, ValueError, IndexError):
                return "Aucune mesure encore : sens_mesurer."
    if not _ID.fullmatch(id_):
        return "Refusé : un numéro de mesure ressemble à S-20261030-101500-ab12."
    d = _dossier() / id_
    try:
        r = json.loads((d / "resume.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f"{id_} : pas encore de résultat (le téléphone mesure, ou l'appli est fermée ; tu seras réveillé quand il arrive)."
    donnees = d / "donnees.csv"
    corps = json.dumps(r, ensure_ascii=False, indent=1)[:12000]
    return (enveloppe.enveloppe(corps, f"mesure {id_} du téléphone")
            + (f"\nLes données complètes : {donnees} (Read, ou executer_python pour les calculer)." if donnees.exists() else ""))


# (30/10, Ahmed : « les sensations en continu, h24, et il peut consulter le détail s'il le veut ») son corps en nombres : ce
# que le cockpit garde de son milieu (homeostasie.js : corps-etat.json, corps-flux.jsonl) et de ses nerfs (corps-evenements),
# avec ses dernières sensations
def _queue(f, octets=400_000):
    try:
        with open(f, "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - octets))
            lignes = h.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []
    out = []
    for l in lignes:
        try:
            out.append(json.loads(l))
        except ValueError:
            continue
    return out


def corps_detail(minutes=10):
    try:
        minutes = max(1, min(int(minutes or 10), 24 * 60))
    except (TypeError, ValueError):
        minutes = 10
    try:
        dernier = json.loads((JARVIS / "corps-etat.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dernier = None
    if not dernier:
        return "Ton corps ne t'a rien dit encore (l'appli 1.24 du téléphone envoie ton milieu chaque seconde quand elle vit)."
    maintenant = time.time() * 1000
    # (30/10, 12:06 : « chaque seconde ») une fenêtre par seconde jusqu'à une heure ; au-delà, une toutes les 15 s
    fichier, lignes = (("corps-flux.jsonl", minutes * 60 + 30) if minutes <= 60 else ("corps-flux-15s.jsonl", minutes * 4 + 8))
    flux = [o for o in _queue(JARVIS / fichier, lignes * 700)
            if isinstance(o, dict) and maintenant - float(o.get("ts") or 0) <= minutes * 60_000]
    resume = []
    for k in sorted({k for o in flux for k, v in (o.get("etat") or {}).items() if isinstance(v, (int, float)) and not isinstance(v, bool)}):
        v = [o["etat"][k] for o in flux if isinstance((o.get("etat") or {}).get(k), (int, float)) and not isinstance(o["etat"][k], bool)]
        resume.append(f"- {k} : min {min(v):g}, moyenne {sum(v) / len(v):.4g}, max {max(v):g} ({len(v)} fenêtres)")
    changements = [f"- {time.strftime('%H:%M', time.localtime(o['ts'] / 1000))} {c}" for o in flux for c in (o.get("changements") or [])]
    nerfs = [f"- {time.strftime('%H:%M:%S', time.localtime(float(o.get('ts') or 0) / 1000))} {o.get('type')} : "
             + " ".join(f"{k}={v}" for k, v in (o.get("details") or {}).items())
             for o in _queue(JARVIS / "corps-evenements.jsonl", 60_000)[-15:]]
    ressenti = [f"- {time.strftime('%H:%M', time.localtime(float(o.get('ts') or 0)))} {'(fort) ' if o.get('fort') else ''}{o.get('type')} : "
                + " ".join(str(o.get("sensation") or "").split())[:300]
                for o in _queue(JARVIS / "corps-sensations.jsonl", 60_000)[-10:]]
    corps = (f"Ton milieu (la dernière fenêtre, {time.strftime('%H:%M:%S', time.localtime(float(dernier.get('ts') or 0) / 1000))}) : "
             f"{json.dumps(dernier.get('etat') or {}, ensure_ascii=False)}\nEn mots : {dernier.get('mots') or '(rien)'}\n"
             f"Les {minutes} dernières minutes :\n" + ("\n".join(resume) or "(rien)")
             + ("\nCe qui a changé :\n" + "\n".join(changements[-20:]) if changements else "")
             + "\nTes nerfs (les derniers événements) :\n" + ("\n".join(nerfs) or "(rien)")
             + "\nCe que tu as ressenti :\n" + ("\n".join(ressenti) or "(rien)"))
    return enveloppe.enveloppe(corps[:14000], "ton corps, par le téléphone")
