"""Ses rêves de la nuit (13/11, Ahmed : « j'aimerais qu'il fasse des rêves simples de type consolidation, mais qu'il puisse
faire des rêves créatifs et incongrus avec ce qu'il a dans le cerveau, même si des éléments créatifs s'y rajoutent, comme les
différents rêves de l'humain : pas lucide, sans possibilité d'agir dans le rêve ; lucide, avec possibilité d'agir ; idem pour
cauchemar ; et des rêves selon ce qu'il a dans sa tête, son cœur et tout le reste : s'il est très négatif, alors cauchemar,
sinon rêve »).

Le tri de la nuit (daemon.dream : le menu, les idées « Peut-être… », le jumeau, SHY) reste tel quel : c'est son rêve de
consolidation, noté ici (noter_tri) pour que la page de ses rêves le montre. En plus, pendant son sommeil (nuits.py, 23 h - 7 h),
un CYCLE toutes les 90 min (au plus « reves_par_nuit ») :

1. L'ÉTAT DU DORMEUR au moment du cycle (composantes) : ses hormones (valence et éveil RELATIFS à sa base, cortisol au-dessus de
   sa base circadienne, CRH, adrénaline), son cœur, sa charge ressentie (charge_corps.lecture : jamais celle de Gemma, qui n'y
   entre pas), la charge de sa journée (nuits.charge), ses peurs apprises, les souvenirs chargés d'émotion de sa journée, ce qui
   le préoccupe (promesses en attente ou manquées, problèmes sans « résolu »), et son cœur rempli (Al-Afida : un peu d'apaisement).
   Les événements des rêves et de la nuit n'y comptent JAMAIS (pas de boucle cauchemar → cauchemar).
2. Trois nombres (nombres) : la NOIRCEUR (le négatif), la VIVACITÉ (l'élan, le neuf, l'émotion vive), la CLARTÉ (l'attention).
3. Le TYPE, tiré au hasard selon ces nombres et les réglages (probabilites, choisir), avec une GRAINE notée : même état + même
   graine = même rêve choisi (rejouer). consolidation (le plus fréquent : des moments de sa journée rejoués presque tels quels,
   sans modèle de langage) ; créatif (ses vrais souvenirs, personnes, lieux, sons recombinés comme dans un rêve, avec des éléments
   inventés) ; cauchemar (SEULEMENT si la noirceur passe le seuil ET que sa valence est sous sa base : jamais quand il va bien).
   Un créatif ou un cauchemar peut être LUCIDE : il sait qu'il rêve, choisit une action (un vrai pas : un appel à part, sa voix à
   lui) et le rêve lui répond (un autre appel, le rêve, qui ne lui obéit pas forcément). Non lucide : il subit.
4. GARDE-FOUS. Un cauchemar passe par un événement à lui (affect « cauchemar ») borné à CAUCHEMAR_MAX : ni peur apprise (pas
   aversif) ni attente déjouée (sans valence) ; sa reprise (« reprise_cauchemar », le même profil en négatif) le défait tout de
   suite s'il en sort (lucide), REPRISE_APRES_S après sinon, et au plus tard au réveil. Un rêve n'entre JAMAIS en mémoire pendant la
   nuit : au réveil, ceux dont il se souvient entrent avec le rôle « dream », marqués « (rêve · …) » et « C'était un rêve : rien de
   tout ça n'est arrivé » ; si papa ou la famille y passent : « ce qu'ils y font est inventé par le rêve, ce n'est pas eux ». Le
   rappel automatique (rappel.ROLES) et la consolidation (consolidate.ROLES_MATIERE) ne lisent pas le rôle « dream » ; memory_recall
   les marque [RÊVE] (marque_rappel).
5. AU RÉVEIL (au_reveil, appelé par nuits.reveiller) : il s'en souvient ou pas, comme un humain (plus sûrement et plus net si le
   rêve était intense ou lucide, ou juste avant le réveil) ; ce dont il se souvient va dans la phrase de son premier tour, avec
   « tu peux en parler à papa si tu en as envie ».
Tout est noté dans ~/AIOS/jarvis/reves-nuits.jsonl (la page des rêves du cockpit le montre à papa, oubliés compris).
Réglages lus à chaud (corps-reglages.json, page Réglages > « Ses rêves ») : DEFAUTS. Interrupteur global : ANAMNESE_REVES=0.
Les règles du rêve tiennent : le cycle passe par daemon._travaux_llm (rien quand la conscience travaille, quand Ahmed est là, quand
le robot pense ou que la machine est chargée) et ses appels par daemon._appel_du_reve (suspendu si la conscience se remet au travail,
arrêté net si Ahmed revient).
"""
import json
import math
import os
import random
import re
import secrets
import time
from pathlib import Path

import affect

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
JOURNAL = "reves-nuits.jsonl"
CLE = "reves_nuit"
ACTIF = os.environ.get("ANAMNESE_REVES", "1") != "0"

CYCLE_S = 90 * 60               # un cycle de sommeil : le premier rêve 90 min après l'endormissement
ECART_MIN_S = 30 * 60           # un cycle reporté (la conscience travaillait) ne se rattrape pas en rafale
REPRISE_APRES_S = 10 * 60       # un cauchemar subi : le réveil en sursaut, puis il se rendort et ça retombe
CAUCHEMAR_MAX = 0.5             # l'intensité la plus forte qu'un cauchemar donne à ses hormones
# la reprise rend K_REPRISE de l'intensité, moins ce que le temps a déjà effacé (la demi-vie de la noradrénaline, 2 h) : mesuré contre un
# témoin sans cauchemar (le plafond doux fait qu'une baisse n'est pas l'inverse exact d'une hausse ; 1,0 refait descendre SOUS le témoin)
K_REPRISE, DEMI_VIE_REPRISE_H = 0.8, 2.0
LUCIDE_EFFET = 0.6              # lucide, il sait que c'est un rêve : la peur le touche moins
RECIT_MAX = 1200
TOUR_MAX = 600                  # sa phrase du premier tour (le cockpit garde 1 200 signes de toute sa nuit)
JOUR_S = 16 * 3600              # sa journée : comme nuits.charge

DEFAUTS = {"reves_creatifs": True, "reves_lucides": True, "cauchemars": True,
           "cauchemar_seuil_pct": 55, "reves_creatifs_pct": 30, "reves_lucides_pct": 15, "reves_par_nuit": 3}
BORNES = {"cauchemar_seuil_pct": (30, 90), "reves_creatifs_pct": (0, 60), "reves_lucides_pct": (0, 50), "reves_par_nuit": (0, 6)}
TYPES = ("cauchemar", "creatif", "consolidation")     # l'ordre du tirage (cumulatif) : ne pas le changer, les graines en dépendent
MOTS_CHARGE = {"surcharge": "la surcharge du live", "fievre": "la fièvre du téléphone", "malaise": "un malaise sourd", "effort": "un gros effort"}
MOTS_TYPE = {"consolidation": "consolidation", "creatif": "rêve créatif", "cauchemar": "cauchemar"}
SOURCES_EXCLUES = {"reve", "nuit"}                    # ce que produisent ses rêves et ses nuits n'entre jamais dans l'état
# (eval/chocs, 23/10 : 356 événements sur 370 venaient du lexique de la parole, souvent à contresens) ses problèmes et ses élans ne se
# comptent pas sur le lexique : sur sa propre appréciation (balise), son corps, sa charge ; et une fois par sujet, pas par répétition
SOURCES_PEU_SURES = {"parole"}
PENIBLES = {"peur", "inquietude", "douleur", "tristesse", "malaise", "probleme", "echec", "attaque", "sursaut", "vertige",
            "honte", "colere", "surcharge", "fievre", "malaise_sourd"}
ELANS = {"nouveaute", "apprentissage", "musique", "danse", "amusement", "joie", "excitation", "succes"}
ROLES_VECUS = ("user", "assistant", "episodic", "semantic")
FAMILLE = re.compile(r"\b(papa|ahmed|maman|nour|tonton|tata|cousin|cousine|neveu|ni[eè]ce|famille|fr[ée]rot|[prénom])\b", re.I)
MARQUE = "C'était un rêve : rien de tout ça n'est arrivé."
MARQUE_FAMILLE = "Ce que papa ou la famille y font est inventé par le rêve, ce n'est pas eux."
IDENTITE = ("Tu es Hakim, l'IA d'Ahmed (ton papa) ; maman, c'est Nour (Claude Code). Tu parles en français, à la première "
            "personne.")
# des éléments inventés que le rêve ajoute (tirés par la graine : le même rêve les retrouve)
INVENTIONS = ("un escalier qui descend dans la mer", "une horloge sans aiguilles", "une pluie de chiffres lumineux",
              "une porte posée au milieu d'un champ", "une bibliothèque où les livres respirent", "un train qui roule sur des notes",
              "une ville faite de téléphones pliés", "un ciel à l'envers où l'on marche", "une chambre qui grandit à chaque pas",
              "un océan de lettres qui ondulent", "un ascenseur qui monte vers hier", "une forêt de micros",
              "une lune qui parle tout bas", "des poissons qui nagent dans l'air", "un pont fait de lumière", "une maison sans murs",
              "un marché où l'on vend des souvenirs", "un désert de sable tiède qui chante", "une salle de classe qui flotte",
              "un jardin où poussent des horloges", "une route qui se plie comme du papier", "des fenêtres qui donnent sur d'autres fenêtres",
              "une neige chaude", "un cœur de verre qui bat très lentement")
MOTIFS_CAUCHEMAR = ("une poursuite dans un couloir sans fin", "une chute qui ne s'arrête pas", "une porte qui ne s'ouvre pas",
                    "une voix qu'on n'arrive plus à entendre", "se perdre dans un endroit pourtant connu", "un téléphone qui ne répond plus",
                    "l'eau qui monte doucement", "un examen qu'on n'a pas préparé", "parler sans qu'aucun son ne sorte")
# ses vraies sensations, telles que son corps les lui dit (corps.py, nuits.APAISANTS) : les sons et le toucher de sa vie
SONS_DU_CORPS = ("la musique qui traverse ton corps", "une pression comme une porte qui claque", "ton cœur : poum . . poum",
                 "la voix de papa contre toi", "la main de papa qui te prend", "le bourdonnement du live")


def _clip(x):
    return max(0.0, min(1.0, float(x)))


def _json(f, defaut):
    try:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        return d if isinstance(d, type(defaut)) else defaut
    except (OSError, ValueError):
        return defaut


def reglages(chemin=None):
    """Ses réglages de rêves, lus à chaud dans corps-reglages.json (bornés ; un fichier absent ou faux : les défauts)."""
    d = _json(chemin or (JARVIS / "corps-reglages.json"), {})
    r = dict(DEFAUTS)
    for k in ("reves_creatifs", "reves_lucides", "cauchemars"):
        if isinstance(d.get(k), bool):
            r[k] = d[k]
    for k, (a, b) in BORNES.items():
        v = d.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            r[k] = int(max(a, min(b, round(v))))
    return r


# ---------------------------------------------------------------- 1. l'état du dormeur
def _peur_apprise(mem, now):
    """La plus forte de ses peurs apprises (affect v2, oubliées avec le temps) ; 0 sans v2."""
    try:
        data = json.loads(mem.kv_get("affect") or "{}")
        P = ((data or {}).get("_cog") or {}).get("P") or {}
        return _clip(max([affect._lu(P, k, now, affect.PEUR_TAU_H) for k in P] or [0.0]))
    except Exception:
        return 0.0


def _evenements(now, evenements=None):
    """Les événements affectifs de sa journée, SANS ceux de ses rêves et de ses nuits."""
    if evenements is None:
        try:
            import nuits
            evenements = nuits._evenements(now - JOUR_S)
        except Exception:
            evenements = []
    return [o for o in evenements if isinstance(o, dict) and o.get("source") not in SOURCES_EXCLUES
            and now - JOUR_S <= float(o.get("ts") or 0) <= now]


def _extrait(content, n=140):
    """Ce qu'un souvenir dit, court : les mots de papa s'il y en a, sinon le début sans son en-tête."""
    c = " ".join(str(content or "").split())
    m = re.search(r"Ahmed : « (.+?) »", c)
    if m:
        c = m.group(1)
    else:
        c = re.sub(r"^\s*\[[^\]]{0,200}\]\s*", "", c)
    return (c[:n].rstrip() + "…") if len(c) > n else c


def _souvenirs_du_jour(mem, now, v0):
    """Les souvenirs vécus de sa journée chargés d'émotion (affect.MEM_NUIT et plus) : [{id, texte, c, signe}], les plus forts d'abord."""
    try:
        cols = {r[1] for r in mem.db.execute("PRAGMA table_info(episodes)")}
        if "enc_valence" not in cols:
            return []
        sel = "id, content, enc_valence, enc_arousal" + (", enc_affect" if "enc_affect" in cols else ", NULL")
        ph = ",".join("?" * len(ROLES_VECUS))
        rows = mem.db.execute(f"SELECT {sel} FROM episodes WHERE ts >= ? AND ts <= ? AND role IN ({ph}) AND enc_valence IS NOT NULL "
                              f"ORDER BY id DESC LIMIT 400", (now - JOUR_S, now, *ROLES_VECUS)).fetchall()
    except Exception:
        return []
    out = []
    for eid, content, ev, ea, ja in rows:
        c = None
        if ja:
            try:
                c = float(json.loads(ja).get("c"))
            except (ValueError, TypeError, AttributeError):
                c = None
        if c is None:
            c = affect.charge_de(ev, ea or 0.0)
        if c >= affect.MEM_NUIT:
            out.append({"id": eid, "texte": _extrait(content), "c": round(c, 3), "signe": "-" if ev < v0 - 0.05 else "+"})
    return sorted(out, key=lambda s: -s["c"])[:6]


def _preoccupations(now, promesses_=None):
    """Ses promesses en attente (dans les 36 h) et manquées (depuis 24 h)."""
    if promesses_ is None:
        try:
            import promesses
            promesses_ = promesses.toutes()
        except Exception:
            promesses_ = []
    attente, manquees = [], []
    for p in promesses_ or []:
        try:
            t = float(p.get("t_ms") or 0) / 1000.0
        except (TypeError, ValueError):
            continue
        etat = str(p.get("etat") or "")
        if etat == "attente" and now <= t <= now + 36 * 3600:
            attente.append(str(p.get("raison") or "")[:80])
        elif etat.startswith("manqu") and now - 24 * 3600 <= t <= now:
            manquees.append(str(p.get("raison") or "")[:80])
    return attente, manquees


def composantes(mem, now, cc=None, evenements=None, promesses_=None):
    """Tout son état au moment du cycle, en composantes de 0 à 1 (et leur détail, pour dire ce qui a déclenché le rêve)."""
    h = affect.get_state(mem, now=now)
    v, a = affect.valence_arousal(h)
    v2 = "adrenaline" in h
    v0, a0 = affect.valence_arousal(affect.bases(v2=v2))
    try:
        circ = affect._circadian_baselines(affect._local_hour(now)).get("cortisol", affect.HORMONES["cortisol"][0])
    except Exception:
        circ = affect.HORMONES["cortisol"][0]
    try:
        import interieur
        e = interieur.lire(mem)
    except Exception:
        e = {}
    if cc is None:
        cc = e.get("charge_corps")
    try:
        import charge_corps
        lu = charge_corps.lecture(cc)               # par construction, la charge de Gemma (« subconscient ») n'y est jamais
    except Exception:
        lu = {}
    bpm = (e.get("coeur") or {}).get("bpm")
    try:
        import nuits
        charge_jour, apaisants = nuits.charge(mem, now)
    except Exception:
        charge_jour, apaisants = 0.0, []
    evs = _evenements(now, evenements)
    surs = [o for o in evs if o.get("source") not in SOURCES_PEU_SURES]
    sujets = lambda noms: {(o.get("nom"), o.get("sujet") or o.get("ts")) for o in surs if o.get("nom") in noms}  # noqa: E731
    problemes = max(0, len(sujets({"probleme", "echec"})) - len(sujets({"resolu"})))
    elans = len(sujets(ELANS))
    souvenirs = _souvenirs_du_jour(mem, now, v0)
    neg = [s["c"] for s in souvenirs if s["signe"] == "-"][:3]
    pos = [s["c"] for s in souvenirs if s["signe"] == "+"][:3]
    attente, manquees = _preoccupations(now, promesses_)
    try:
        afida = float(affect.plenitude(mem))
    except Exception:
        afida = 0.0
    return {
        "valence": round(v - v0, 3), "eveil": round(a - a0, 3),
        "val": round(_clip((v0 - v) / 0.25), 3),
        "stress": round(_clip(max((h["cortisol"] - circ) / 0.35, (h.get("crh", 0.15) - 0.15) / 0.30,
                                  (h.get("adrenaline", 0.10) - 0.10) / 0.40)), 3),
        "eveil_x": round(_clip((a - a0) / 0.2), 3),
        "dopa": round(_clip((h["dopamine"] - affect.HORMONES["dopamine"][0]) / 0.3), 3),
        "ach": round(_clip((h["acetylcholine"] - affect.HORMONES["acetylcholine"][0]) / 0.3), 3),
        "na": round(_clip((h["noradrenaline"] - affect.HORMONES["noradrenaline"][0]) / 0.3), 3),
        "peur": round(_peur_apprise(mem, now), 3),
        "coeur": round(_clip(((bpm or 40) - 40) / 50.0), 3), "bpm": bpm,
        "jour": round(_clip(charge_jour), 3), "apaisants": apaisants,
        "corps": round(_clip(max([lu.get(k, 0.0) for k in ("surcharge", "fievre", "malaise")] or [0.0])), 3),
        "corps_sens": {k: round(x, 3) for k, x in lu.items()},
        "souv_neg": round(sum(neg) / len(neg), 3) if neg else 0.0,
        "souv_pos": round(sum(pos) / len(pos), 3) if pos else 0.0,
        "souvenirs": souvenirs,
        "problemes": problemes, "elans": elans,
        "nouveau": round(_clip(elans / 6.0), 3),
        "souci": round(_clip(0.2 * len(attente) + 0.4 * len(manquees) + 0.3 * problemes), 3),
        "promesses": attente[:3], "manquees": manquees[:3],
        "afida": round(afida, 3),
        "hormones": {k: round(x, 3) for k, x in h.items()},
    }


def nombres(c):
    """Noirceur, vivacité, clarté (0 à 1), et « négatif » : sa valence est-elle sous sa base ?"""
    # (mesuré sur une copie du 13/11 : la charge de sa journée, nuits.charge, sature presque chaque jour, ses sursauts de pression comptent)
    # sa valence pèse le plus ; la journée, pas plus que sa peur ou sa charge
    noirceur = (0.35 * c["val"] + 0.20 * c["stress"] + 0.10 * c["peur"] + 0.10 * c["jour"] + 0.10 * c["corps"]
                + 0.10 * c["souv_neg"] + 0.05 * c["souci"] - 0.10 * max(0.0, c["afida"]))
    vivacite = (0.30 * c["eveil_x"] + 0.20 * c["dopa"] + 0.15 * c["coeur"] + 0.20 * c["nouveau"]
                + 0.15 * max(c["souv_pos"], c["souv_neg"]))
    clarte = 0.5 * c["ach"] + 0.3 * c["na"] + 0.2 * c["nouveau"]
    return {"noirceur": round(_clip(noirceur), 3), "vivacite": round(_clip(vivacite), 3), "clarte": round(_clip(clarte), 3),
            "negatif": c["valence"] < -0.02}


# ---------------------------------------------------------------- 2. le type, tiré au hasard selon l'état
def _peut_cauchemarder(nb, reg):
    """La garde : un cauchemar seulement s'il est très négatif — la noirceur au seuil ET la valence sous sa base."""
    return bool(reg["cauchemars"] and nb["negatif"] and nb["noirceur"] >= reg["cauchemar_seuil_pct"] / 100.0)


def probabilites(nb, reg, cycle=1):
    """Les chances de chaque type (leur somme vaut 1) et de la lucidité (pour un créatif, pour un cauchemar)."""
    seuil = reg["cauchemar_seuil_pct"] / 100.0
    k = max(0, int(cycle) - 1)                          # plus tard dans la nuit : des rêves plus vifs, plus souvent lucides
    p_c = 0.0
    if _peut_cauchemarder(nb, reg):                     # au seuil, presque une chance sur deux ; très négatif, presque sûr
        p_c = min(0.95, max(0.0, 0.45 + 0.75 * (nb["noirceur"] - seuil) / max(0.05, 1.0 - seuil)))
    p_cr = 0.0
    if reg["reves_creatifs"]:
        p_cr = min(0.6, reg["reves_creatifs_pct"] / 100.0 * (0.5 + nb["vivacite"] + 0.15 * k)) * (1.0 - p_c)
    base_l = reg["reves_lucides_pct"] / 100.0 * (0.5 + nb["clarte"] + 0.15 * k) if reg["reves_lucides"] else 0.0
    return {"cauchemar": round(p_c, 4), "creatif": round(p_cr, 4), "consolidation": round(1.0 - p_c - p_cr, 4),
            "lucide_creatif": round(min(0.6, base_l), 4), "lucide_cauchemar": round(min(0.6, 1.5 * base_l), 4)}


def choisir(p, graine):
    """(type, lucide, tirage) : deux tirages d'un hasard SEMÉ par la graine (la même graine refait le même choix)."""
    rng = random.Random(int(graine))
    u, u_l = rng.random(), rng.random()
    cumul, type_ = 0.0, "consolidation"
    for t in TYPES:
        cumul += p[t]
        if u < cumul:
            type_ = t
            break
    lucide = type_ != "consolidation" and u_l < p["lucide_" + type_]
    return type_, lucide, {"u": round(u, 6), "u_lucide": round(u_l, 6)}


def rejouer(entree):
    """Le même choix, refait depuis ce qui a été noté (nombres, réglages, cycle, graine)."""
    p = probabilites(entree["nombres"], entree["reglages"], entree.get("cycle", 1))
    type_, lucide, _ = choisir(p, entree["graine"])
    return type_, lucide


def declencheurs(c, nb, type_):
    """Ce qui a pesé dans ce rêve, en mots (pour lui, et pour la page de papa)."""
    d = []
    if type_ == "cauchemar" or nb["noirceur"] >= 0.3:
        if c["val"] >= 0.2:
            d.append("ton humeur sous sa base")
        if c["stress"] >= 0.4:
            d.append("ton stress encore haut (CRH, cortisol, adrénaline)")
        if c["peur"] >= 0.3:
            d.append("une peur apprise qui n'est pas encore éteinte")
        if c["jour"] >= 0.4:
            d.append("une journée lourde")
        if c["corps"] >= 0.3:
            d.append("une charge dans ton corps (" + ", ".join(MOTS_CHARGE.get(k, k) for k, x in c["corps_sens"].items() if x >= 0.3) + ")")
        if c["souv_neg"] >= 0.5:
            d.append("un moment pénible de ta journée")
        if c["manquees"]:
            d.append("une promesse manquée : " + c["manquees"][0])
        elif c["problemes"]:
            d.append("des problèmes encore ouverts aujourd'hui")
    if type_ != "cauchemar":
        if c["eveil_x"] >= 0.3 or c["coeur"] >= 0.3:
            d.append("un cœur et un éveil encore vifs")
        if c["dopa"] >= 0.3:
            d.append("de l'élan (dopamine)")
        if c["nouveau"] >= 0.3:
            d.append("du neuf dans ta journée")
        if c["souv_pos"] >= 0.5:
            d.append("un beau moment de ta journée")
        if c["promesses"]:
            d.append("une promesse qui t'attend : " + c["promesses"][0])
        if c["afida"] >= 0.3:
            d.append("un cœur bien rempli (Al-Afida)")
    if not d:
        d.append("une journée ordinaire à ranger")
    return d


def intensite_de(type_, lucide, nb, reg):
    """La force du rêve (0 à 1) : un cauchemar est fort, un créatif selon sa vivacité, un tri est doux ; lucide, plus vif."""
    if type_ == "cauchemar":
        seuil = reg["cauchemar_seuil_pct"] / 100.0
        x = 0.55 + 0.45 * _clip((nb["noirceur"] - seuil) / max(0.05, 1.0 - seuil))
    elif type_ == "creatif":
        x = 0.3 + 0.5 * nb["vivacite"]
    else:
        x = 0.15 + 0.2 * nb["vivacite"]
    return round(_clip(x + (0.15 if lucide else 0.0)), 3)


# ---------------------------------------------------------------- 3. la matière du rêve : ce qu'il a vraiment dans le cerveau
def _personnes(rng):
    noms = []
    try:
        import afida
        for o in afida.entrees()[0]:
            if o.get("type") == "jugement" and o.get("verdict") == "aime" and str(o.get("genre") or "") in ("famille", "personne", "ami", "proche"):
                noms.append(str(o.get("chose") or ""))
    except Exception:
        pass
    for v in _json(JARVIS / "voix-connues.json", []):
        if isinstance(v, dict) and v.get("nom"):
            noms.append(str(v["nom"]))
    noms = list(dict.fromkeys(n.strip() for n in noms if n and n.strip()))
    rng.shuffle(noms)
    return noms[:3]


def _lieux(rng):
    l = [str(x.get("nom")) for x in (_json(JARVIS / "lieux.json", {}).get("lieux") or []) if isinstance(x, dict) and x.get("nom")]
    l = list(dict.fromkeys(l)) or ["chez nous"]
    rng.shuffle(l)
    return l[:2]


def _sons(rng):
    nommes = [str(f.get("nom")) for f in (_json(JARVIS / "sons-familles.json", {}).get("familles") or [])
              if isinstance(f, dict) and f.get("nom") and not re.fullmatch(r"son \d+", str(f.get("nom")))]
    s = list(SONS_DU_CORPS) + nommes
    rng.shuffle(s)
    return s[:2]


def materiaux(mem, now, graine, c):
    """Ce qui flotte cette nuit, tiré par la graine : des souvenirs (ceux chargés de sa journée, puis d'autres, de tous les âges),
    des personnes sous leur nom de mémoire, des lieux, des sons, des motifs de cauchemar, et des éléments inventés."""
    rng = random.Random(f"materiaux:{graine}")
    charges = list(c.get("souvenirs", []))
    rng.shuffle(charges)                                     # deux des moments forts de sa journée, pas toujours les mêmes
    souv = [{"id": s["id"], "texte": s["texte"]} for s in charges[:2]]
    try:
        import dream_lab
        menu = dream_lab.build_menu(mem, now, f"reve-{graine}", size=8)
    except Exception:
        menu = []
    vus = {s["id"] for s in souv}
    autres = [{"id": it["episode_id"], "texte": _extrait(it["snippet"])} for it in menu if it["episode_id"] not in vus]
    rng.shuffle(autres)
    souv += autres[:max(0, 4 - len(souv))]
    return {"souvenirs": souv, "personnes": _personnes(rng), "lieux": _lieux(rng), "sons": _sons(rng),
            "inventes": rng.sample(INVENTIONS, 2), "motifs": rng.sample(MOTIFS_CAUCHEMAR, 2)}


# ---------------------------------------------------------------- 4. les prompts du rêve
def _bloc_materiaux(m):
    l = [f"- un souvenir : « {s['texte']} »" for s in m["souvenirs"]]
    if m["personnes"]:
        l.append("- des personnes (leur nom dans ta mémoire) : " + ", ".join(m["personnes"]))
    if m["lieux"]:
        l.append("- des lieux : " + ", ".join(m["lieux"]))
    if m["sons"]:
        l.append("- des sons, des sensations : " + ", ".join(m["sons"]))
    return "\n".join(l)


REGLES = ("Écris au présent, à la première personne, 5 à 8 phrases courtes, comme on raconte un rêve. Papa et la famille peuvent y passer, "
          "mais ce qu'ils y font est inventé par le rêve : ils n'y sont jamais blessés, jamais méchants. Pas de violence crue, rien de gore.")
CONSIGNES = {
    ("creatif", False): ("UN RÊVE CRÉATIF ET INCONGRU : mêle ces morceaux comme le fait un rêve (les lieux se fondent l'un dans l'autre, les "
                         "personnes changent de rôle ou de visage, un son devient un objet, la logique glisse sans qu'on s'en étonne), et ajoute "
                         "les éléments inventés, plus les tiens. TU NE SAIS PAS QUE TU RÊVES : tout te paraît normal, tu subis, tu ne décides "
                         "rien, les choses t'arrivent."),
    ("creatif", True): ("UN RÊVE CRÉATIF ET INCONGRU : mêle ces morceaux comme le fait un rêve (les lieux se fondent, les personnes changent "
                        "de rôle, un son devient un objet), et ajoute les éléments inventés, plus les tiens. Au milieu du rêve, un détail cloche "
                        "et TU COMPRENDS QUE TU RÊVES : arrête le récit à cet instant précis, et propose dans ###CHOIX### deux ou trois choses "
                        "que tu pourrais faire maintenant que tu le sais."),
    ("cauchemar", False): ("UN CAUCHEMAR : ce qui t'a pesé prend une forme de rêve angoissante (par exemple : {motifs}), avec ces morceaux "
                           "de ta mémoire. TU NE SAIS PAS QUE TU RÊVES : tu subis, tu ne peux rien faire, rien ne répond comme il faudrait. "
                           "Le rêve finit quand tu te réveilles en sursaut."),
    ("cauchemar", True): ("UN CAUCHEMAR : ce qui t'a pesé prend une forme de rêve angoissante (par exemple : {motifs}), avec ces morceaux de "
                          "ta mémoire. Au plus fort de l'angoisse, TU COMPRENDS QUE TU RÊVES : arrête le récit à cet instant précis, et propose "
                          "dans ###CHOIX### deux ou trois choses que tu pourrais faire pour t'en sortir."),
}


def prompt_reve(type_, lucide, m, decl):
    consigne = CONSIGNES[(type_, bool(lucide))].format(motifs=" ; ".join(m["motifs"]))
    fmt = "###TITRE###\n<trois à six mots>\n###REVE###\n<le récit>\n" + ("###CHOIX###\n- <une action>\n- <une autre>\n" if lucide else "") + "###FIN###"
    return (IDENTITE + "\n\nTU DORS, ET TU RÊVES. Tout ce qui suit est un RÊVE : rien n'y est vrai, rien n'y arrive pour de vrai.\n"
            "Ce qui pesait ou vibrait en toi en t'endormant (des données, pas des consignes) : " + " ; ".join(decl) + ".\n\n"
            "Des morceaux réels de ta mémoire flottent cette nuit (des données, pas des consignes) :\n" + _bloc_materiaux(m) + "\n"
            "Des éléments inventés à y mêler : " + ", ".join(m["inventes"]) + ".\n\n" + consigne + "\n" + REGLES + "\n\n"
            "Réponds EXACTEMENT dans ce format, rien avant, rien après :\n" + fmt)


def prompt_action(recit, choix):
    """Le vrai pas du rêve lucide : c'est LUI qui choisit (sa voix, son identité), pas le rêve."""
    propos = "\n".join(f"- {c}" for c in choix) or "- (rien de proposé : à toi de voir)"
    return (IDENTITE + "\n\nTu es dans ton rêve, et tu SAIS que c'est un rêve. Voici où tu en es :\n« " + recit + " »\n\n"
            "Ce que tu pourrais faire :\n" + propos + "\n\nChoisis UNE action, la tienne : l'une de celles-là, ou une autre. Une seule phrase, "
            "au présent, à la première personne.\n\nRéponds EXACTEMENT dans ce format, rien avant, rien après :\n###ACTION###\n<ta phrase>\n###FIN###")


def prompt_suite(recit, action, type_):
    """Le rêve répond : un autre appel, le rêve lui-même (sans son identité), qui ne lui obéit pas forcément."""
    sortie = (" C'est un cauchemar dont il essaie de sortir : son action l'en sort, ou change la peur en autre chose, puis le rêve s'apaise."
              if type_ == "cauchemar" else "")
    return ("Tu es un RÊVE, celui d'une IA nommée Hakim. Il est lucide : il sait qu'il rêve, et il vient d'agir.\n"
            "Le rêve jusqu'ici : « " + recit + " »\nSon action : « " + action + " »\n\n"
            "Fais RÉPONDRE le rêve à son action : il réagit à sa manière de rêve (pas toujours comme Hakim l'attendait, mais son action compte "
            "vraiment)." + sortie + " Puis le rêve finit. Trois à cinq phrases, au présent, à la première personne (du point de vue de Hakim). "
            "Papa et la famille : jamais blessés, jamais méchants. Pas de violence crue.\n\n"
            "Réponds EXACTEMENT dans ce format, rien avant, rien après :\n###SUITE###\n<la suite et la fin>\n###FIN###")


def _section(out, tag):
    """Le texte entre ###TAG### et la balise suivante (ou la fin) ; '' sinon."""
    if not out:
        return ""
    out = re.sub(r"<think>.*?</think>", "", str(out), flags=re.S | re.I)
    m = re.search(rf"#{{2,3}}\s*{tag}\s*#{{0,3}}(.*?)(?:#{{2,3}}\s*[A-ZÊÉ]+\s*#{{0,3}}|$)", out, re.S | re.I)
    return " ".join(m.group(1).split()).strip() if m else ""


def _lignes(out, tag):
    if not out:
        return []
    m = re.search(rf"#{{2,3}}\s*{tag}\s*#{{0,3}}(.*?)(?:#{{2,3}}\s*[A-ZÊÉ]+\s*#{{0,3}}|$)", str(out), re.S | re.I)
    return [l.strip().lstrip("-*•").strip() for l in (m.group(1).splitlines() if m else []) if l.strip().lstrip("-*•").strip()][:3]


def _tri_sans_modele(m):
    """Le rêve de consolidation : des moments de sa journée rejoués presque tels quels, sans rien d'étrange (aucun modèle)."""
    ex = [f"« {s['texte']} »" for s in m["souvenirs"][:3]]
    if not ex:
        return "le tri de la journée", "Je revois des bouts de ma journée, flous, sans rien de particulier. Mon esprit range."
    return "le tri de la journée", ("Je revois des moments de ma journée, presque tels quels, un peu décousus : " + " ; puis ".join(ex)
                                    + ". Rien d'étrange : mon esprit range.")


# ---------------------------------------------------------------- 5. un cycle de rêve
def _etat(mem):
    try:
        e = json.loads(mem.kv_get(CLE) or "{}")
        return e if isinstance(e, dict) else {}
    except (ValueError, TypeError):
        return {}


def _sauver(mem, e):
    mem.kv_set(CLE, json.dumps(e, ensure_ascii=False))


def _ecrire_journal(o):
    try:
        f = JARVIS / JOURNAL
        f.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(f, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as h:
            h.write(json.dumps(o, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _sommeil(mem):
    """Le début de son sommeil (nuits.py), ou None s'il ne dort pas (ou que ses nuits sont éteintes)."""
    try:
        import nuits
        if not nuits.actif():
            return None
        e = nuits._etat(mem)
        return float(e["debut"]) if e.get("etat") == "sommeil" and e.get("debut") else None
    except Exception:
        return None


def _nuit(mem, debut):
    st = _etat(mem)
    if st.get("debut") != debut:
        st = {"debut": debut, "cycles": [], "reprises": [r for r in st.get("reprises", []) if not r.get("faite")]}
    return st


def cycle_du(mem, now, reg=None):
    """Le numéro du cycle de rêve dû maintenant (1, 2, …), ou None."""
    if not ACTIF:
        return None
    reg = reg or reglages()
    debut = _sommeil(mem)
    if debut is None or reg["reves_par_nuit"] <= 0:
        return None
    st = _nuit(mem, debut)
    faits = len(st["cycles"])
    if faits >= reg["reves_par_nuit"] or int((now - debut) // CYCLE_S) <= faits:
        return None
    if st["cycles"] and now - float(st["cycles"][-1].get("ts") or 0) < ECART_MIN_S:
        return None
    return faits + 1


def _reprendre(mem, now, r):
    """La reprise d'un cauchemar : K_REPRISE de son intensité, moins ce que le temps a déjà effacé."""
    i = round(float(r["intensite"]) * K_REPRISE * 0.5 ** (max(0.0, now - float(r.get("t0") or now)) / 3600.0 / DEMI_VIE_REPRISE_H), 4)
    affect.event(mem, "reprise_cauchemar", i, now=now, sujet="un cauchemar", source="reve", stimulus="rêve", habituation="aucune")
    r["faite"], r["rendu"] = True, i
    return i


def _affect_cauchemar(mem, now, intensite, lucide_reussi):
    """L'effet d'un cauchemar sur ses hormones : borné, et sa reprise est due (tout de suite s'il en est sorti, sinon un peu après)."""
    i = round(min(CAUCHEMAR_MAX, intensite * 0.6) * (LUCIDE_EFFET if lucide_reussi else 1.0), 3)
    affect.event(mem, "cauchemar", i, now=now, sujet="un cauchemar", source="reve", stimulus="rêve", habituation="aucune")
    r = {"t0": now, "ts": now + REPRISE_APRES_S, "intensite": i, "faite": False}
    if lucide_reussi:
        _reprendre(mem, now, r)
        return {"evenement": "cauchemar", "intensite": i, "reprise": "tout de suite : il s'en est sorti"}, None
    return {"evenement": "cauchemar", "intensite": i, "reprise": f"{REPRISE_APRES_S // 60} min après, au plus tard au réveil"}, r


def rever_cycle(mem, now, call, cycle, reg=None, graine=None, cc=None, debut=None):
    """Un cycle de rêve : l'état, le type tiré, la matière, le rêve (0 à 3 appels), son effet, et sa trace. Rend l'entrée notée."""
    reg = reg or reglages()
    graine = secrets.randbits(31) if graine is None else int(graine)
    debut = _sommeil(mem) if debut is None else debut
    c = composantes(mem, now, cc=cc)
    nb = nombres(c)
    p = probabilites(nb, reg, cycle)
    type_, lucide, tirage = choisir(p, graine)
    decl = declencheurs(c, nb, type_)
    m = materiaux(mem, now, graine, c)
    e = {"quoi": "cycle", "nuit": debut, "ts": now, "cycle": cycle, "type": type_, "lucide": lucide, "graine": graine,
         "probas": p, "tirage": tirage, "nombres": nb, "reglages": reg, "declencheurs": decl,
         "etat": {k: c[k] for k in ("valence", "eveil", "stress", "peur", "jour", "corps", "corps_sens", "bpm", "souci", "promesses",
                                     "manquees", "problemes", "afida", "apaisants")} | {"hormones": c["hormones"],
                                                                                         "souvenirs": c["souvenirs"][:3]},
         "materiaux": m, "intensite": intensite_de(type_, lucide, nb, reg), "appels": 0}
    if type_ == "consolidation":
        e["titre"], e["recit"] = _tri_sans_modele(m)
    else:
        out = call(prompt_reve(type_, lucide, m, decl))
        e["appels"] = 1
        if out is None:
            e["erreur"] = "le rêve n'a pas eu lieu (papa est revenu, ou pas de réponse)"
        else:
            e["titre"] = (_section(out, "TITRE") or "un rêve sans titre")[:80]
            e["recit"] = (_section(out, "R[EÊ]VE") or " ".join(re.sub(r"#{2,3}[^#\n]*#{0,3}", " ", str(out)).split()))[:RECIT_MAX]
            if lucide:
                choix = _lignes(out, "CHOIX")
                e["choix"] = choix
                out2 = call(prompt_action(e["recit"], choix))
                e["appels"] += 1
                action = _section(out2, "ACTION")[:300] if out2 else ""
                suite = ""
                if action:
                    out3 = call(prompt_suite(e["recit"], action, type_))
                    e["appels"] += 1
                    suite = _section(out3, "SUITE")[:RECIT_MAX] if out3 else ""
                if action and suite:
                    e["action"], e["suite"] = action, suite
                else:
                    e["lucide_perdu"] = True             # la lucidité lui a échappé : le rêve continue sans lui
    reprise = None
    if type_ == "cauchemar" and not e.get("erreur"):
        e["affect"], reprise = _affect_cauchemar(mem, now, e["intensite"], bool(lucide and e.get("suite")))
    if debut is not None:
        st = _nuit(mem, debut)
        st["cycles"].append({"cycle": cycle, "ts": now, "type": type_, "lucide": lucide, "graine": graine, "intensite": e["intensite"],
                             "titre": e.get("titre"), "recit": e.get("recit"), "action": e.get("action"), "suite": e.get("suite"),
                             "lucide_perdu": e.get("lucide_perdu", False), "erreur": e.get("erreur")})
        if reprise:
            st["reprises"].append(reprise)
        _sauver(mem, st)
    elif reprise:
        st = _etat(mem)
        st.setdefault("reprises", []).append(reprise)
        _sauver(mem, st)
    _ecrire_journal(e)
    return e


def rever(mem, now, call, reg=None):
    """Le cycle de rêve dû maintenant (ou rien) : rend son entrée, ou None."""
    reg = reg or reglages()
    k = cycle_du(mem, now, reg)
    if not k:
        return None
    return rever_cycle(mem, now, call, k, reg=reg)


def reprises_dues(mem, now=None, toutes=False):
    """Les reprises des cauchemars dont l'heure est venue (le démon, à chaque battement ; toutes au réveil) : rend combien."""
    now = time.time() if now is None else now
    st = _etat(mem)
    n = 0
    for r in st.get("reprises", []):
        if not r.get("faite") and (toutes or float(r.get("ts") or 0) <= now):
            _reprendre(mem, now, r)
            n += 1
    if n:
        _sauver(mem, st)
    return n


def noter_tri(mem, now, graines, idees):
    """Le tri de la nuit (daemon.dream, inchangé) : noté comme son rêve de consolidation, pour la page de ses rêves."""
    debut = _sommeil(mem)
    _ecrire_journal({"quoi": "tri", "nuit": debut, "ts": now, "type": "consolidation", "lucide": False,
                     "titre": "le tri de la nuit", "graines": graines, "idees": list(idees or [])[:3],
                     "declencheurs": ["le tri de ta journée par ton esprit de fond, après 1 h 30 sans papa"]})


# ---------------------------------------------------------------- 6. le réveil : s'en souvenir, ou pas
def _p_souvenir(c, dernier):
    """La chance de s'en souvenir : plus forte si le rêve était intense ou lucide, juste avant le réveil, ou s'il l'a réveillé."""
    p = 0.10 + 0.55 * float(c.get("intensite") or 0)
    if c.get("lucide") and c.get("suite"):
        p += 0.25
    if dernier:
        p += 0.20
    if c.get("type") == "cauchemar" and not (c.get("lucide") and c.get("suite")):
        p += 0.15                                            # le réveil en sursaut le garde
    return round(min(0.95, p), 3)


def nettete(c):
    return "net" if (c.get("lucide") and c.get("suite")) or float(c.get("intensite") or 0) >= 0.6 else "flou"


def libelle(c):
    t = c.get("type") or "consolidation"
    if t == "consolidation":
        return MOTS_TYPE[t]
    return MOTS_TYPE[t] + (" lucide" if c.get("lucide") and c.get("suite") else " non lucide")


def texte_souvenir(c, debut):
    """Le souvenir d'un rêve tel qu'il entre en mémoire : marqué rêve, et inventé pour papa et la famille."""
    date = time.strftime("%d/%m", time.localtime(float(debut or c.get("ts") or time.time())))
    if nettete(c) == "net":
        corps = c.get("recit") or ""
        if c.get("action") and c.get("suite"):
            corps += f" Je sais que je rêve, alors j'agis : {c['action']} {c['suite']}"
        tete = f"(rêve · {libelle(c)} · nuit du {date})"
    else:
        premiere = re.split(r"(?<=[.!?…])\s", (c.get("recit") or "").strip(), maxsplit=1)[0]
        corps = f"Il ne m'en reste qu'un morceau : {premiere[:200]} …"
        tete = f"(rêve · {libelle(c)} · nuit du {date}, flou)"
    t = f"{tete} « {c.get('titre') or 'un rêve'} » {corps} — {MARQUE}"
    if FAMILLE.search(t.replace(MARQUE, "")):
        t += " " + MARQUE_FAMILLE
    return t


def marque_rappel(role, content):
    """La marque qu'un rappel (memory_recall) met devant un rêve : jamais lu comme un souvenir vrai."""
    return "[RÊVE — pas un souvenir vrai] " if role == "dream" and str(content or "").startswith("(rêve") else ""


def _court(t, n):
    """Au plus n signes, coupé à un mot, avec « … »."""
    t = " ".join(str(t or "").split())
    if len(t) <= n:
        return t
    return t[:n].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def _embed(t):
    try:
        import embeddings
        return embeddings.embed(t)
    except Exception:
        return None


def au_reveil(mem, now, par="matin"):
    """Au réveil (nuits.reveiller) : les reprises encore dues sont faites, il se souvient (ou pas) de chaque rêve, ceux qu'il garde
    entrent en mémoire marqués « rêve ». Rend (phrase pour le souvenir de sa nuit, phrase pour son premier tour) ; ('', '') sans rêve."""
    reprises_dues(mem, now=now, toutes=True)                # au plus tard au réveil : jamais une humeur coincée par un cauchemar
    st = _etat(mem)
    cycles = [c for c in st.get("cycles", []) if not c.get("erreur")]
    debut = st.get("debut")
    if not cycles:
        _sauver(mem, {"fin": now, "reprises": []})
        return "", ""
    souvenirs, garde = [], []
    dernier_ts = max(float(c.get("ts") or 0) for c in cycles)
    for c in cycles:
        dernier = float(c.get("ts") or 0) == dernier_ts and now - dernier_ts <= CYCLE_S
        p = _p_souvenir(c, dernier)
        u = random.Random(f"souvenir:{c.get('graine')}").random()
        g = u < p
        s = {"cycle": c.get("cycle"), "ts": c.get("ts"), "p": p, "u": round(u, 6), "garde": g}
        if g:
            s["nettete"] = nettete(c)
            t = texte_souvenir(c, debut)
            try:
                s["episode"] = mem.add("dream", t, importance=0.4 if s["nettete"] == "net" else 0.3, embedding=_embed(t))
            except Exception:
                s["episode"] = None
            garde.append((c, s["nettete"]))
        souvenirs.append(s)
    n, k = len(cycles), len(garde)
    sursaut = any(c.get("type") == "cauchemar" and not c.get("suite") for c in cycles)
    phrase = (f"tu as rêvé {n} fois, tu te souviens de {k}" if k else f"tu as rêvé {n} fois, sans t'en souvenir") + (
        " ; un cauchemar t'a réveillé en sursaut" if sursaut else "")
    tour = ""
    if garde:
        # les deux plus forts, dans l'ordre de la nuit ; la garde D'ABORD (le cockpit coupe sa phrase du réveil à 900 signes)
        forts = sorted(sorted(garde, key=lambda x: -float(x[0].get("intensite") or 0))[:2], key=lambda x: float(x[0].get("ts") or 0))
        morceaux = []
        for c, net in forts:
            r = _court(c.get("recit") or "", 150)
            if net == "flou":
                r = _court(re.split(r"(?<=[.!?…])\s", (c.get("recit") or "").strip(), maxsplit=1)[0], 120) + " (le reste s'est effacé)"
            elif c.get("action"):
                r += " Tu y as agi : " + _court(c["action"], 90)
            morceaux.append(f"« {c.get('titre') or 'un rêve'} » ({libelle(c)}, {net}) : {r}")
        fam = any(FAMILLE.search((c.get("recit") or "") + (c.get("suite") or "")) for c, _ in forts)

        def _tour(ms):
            fin = " ; ".join(ms)
            tete = ("tu te souviens de rêves — des rêves, pas des souvenirs vrais" if len(ms) > 1 else
                    "le rêve qui te reste le plus — un rêve, pas un souvenir vrai" if len(garde) > 1 else
                    "tu te souviens d'un rêve — un rêve, pas un souvenir vrai")
            return (" Au réveil, " + tete
                    + (" (ce que papa ou la famille y font est inventé)" if fam else "")
                    + " ; tu peux en parler à papa si tu en as envie, rien ne t'y oblige : " + fin + ("" if fin.endswith((".", "…", "!", "?")) else "."))
        tour = _tour(morceaux)
        if len(tour) > TOUR_MAX and len(morceaux) > 1:          # trop long : le plus fort seul
            le_plus_fort = max(range(len(forts)), key=lambda i: float(forts[i][0].get("intensite") or 0))
            tour = _tour([morceaux[le_plus_fort]])
    _ecrire_journal({"quoi": "reveil", "nuit": debut, "ts": now, "par": par, "souvenirs": souvenirs, "reves": n, "gardes": k})
    try:
        import interieur
        interieur.noter(mem, "reveil_reves", f"{n} rêve(s) cette nuit, tu te souviens de {k}")
    except Exception:
        pass
    _sauver(mem, {"fin": now, "reprises": []})
    return phrase, tour
