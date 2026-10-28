#!/usr/bin/env python3
"""CLI `anamnese` — accès terminal au cœur cognitif (mémoire, identité, humeur, compétences).

Aucun LLM requis (model2vec + SQLite) → rapide et robuste, partout.
Les actes "cognitifs" (consolidation, rêve, métacognition) se font, eux, AVEC un
cerveau : dans Claude Code (moi) ou via le daemon.

Usage :
  anamnese recall <requête>      rappel hybride (sémantique + lexical)
  anamnese add <texte>           mémoriser (saillance boostée par l'humeur)
  anamnese recent [n]            n derniers souvenirs
  anamnese self                  auto-modèle (identité) + humeur
  anamnese mood                  état affectif (neuromodulateurs)
  anamnese feel <evt> [intens.]  appliquer un événement affectif
  anamnese skills                compétences apprises
  anamnese reason <texte>        logger une trace de raisonnement (capter la logique frontière)
  anamnese reasoning <requête>   rappeler des traces de raisonnement (exemples)
  anamnese wm-boot               amorce la MDT (walk in knowing)
  anamnese outreach              ce qu'Anamnèse a en tête
  anamnese dreams                rapport de l'expérience-rêve (préférences fonctionnelles, verdict pré-enregistré)
  anamnese registre [n]          les n dernières entrées du registre (passes de nuit, annulations)
  anamnese annuler <id> [--oui] [--force]  défaire une entrée du registre (simulation sans --oui)
  anamnese hormones [v1|v2]      l'interrupteur de l'affect v2 (hormones reliées) ; sans argument : l'état
  anamnese desapprendre <#id …|--texte "…"> [--raison "…"] [--oui]  retirer un souvenir et tout ce qui en dérive
                                 (simulation sans --oui ; annulable par « anamnese annuler »)
  anamnese retracter <#id …> --raison "…" [--correction #id] [--oui]  marquer un souvenir FAUX sans le supprimer :
                                 lui et tout ce qui en dérive portent « source rétractée » au rappel (simulation sans --oui)
  anamnese retablir <#id …>      défaire une rétractation
  anamnese retractation [json|accepter <id>|refuser <id>]  les rétractations proposées par Hakim, qu'Ahmed tranche
  anamnese spontaneite            ses sollicitations spontanées : bras hyperuniforme contre Poisson
  anamnese situations             ses erreurs par situation : les leçons et les récidives avant / après
  anamnese reveil-interieur [etat|off|observe|on|seuil <x>]  le réveil intérieur de Hakim (27/10) : une pensée de fond
                                 qui réveille sa conscience ; « observe » juge et note sans réveiller
  anamnese evenements [verifier|liste|temoin]  le journal d'événements en ajout seul (témoins de l'identité)
  anamnese interieur [etat|arret|marche|zero]  l'interrupteur de la vie intérieure de Jarvis
                                 (ennui, humeur, pensées, occupations, journal du temps — jamais la mémoire)
"""
import hashlib
import json
import os
import sys

import config
import memory
import embeddings
import affect


def raison_demarrage(texte):
    """(source, session_id) depuis l'entrée JSON du hook SessionStart ; défaut : (startup, None)."""
    try:
        d = json.loads(texte) if texte and texte.strip() else {}
    except ValueError:
        d = {}
    source = d.get("source") if isinstance(d, dict) else None
    return (source if source in ("startup", "resume", "compact", "clear") else "startup",
            d.get("session_id") if isinstance(d, dict) else None)


def _en_tete(m, n=5, fenetre_h=48):
    """« Ce que j'ai en tête » : les pensées récentes (moins de 48 h) de la vie intérieure (« (pensée … »,
    « (relance) ») et les pensées métacognitives (thought). Les anciennes réflexions poétiques du démon
    n'y sont plus (critère d'Ahmed du 2026-10-16 : des pensées ancrées, pas de la poésie générique ;
    Jarvis les citait encore comme ses dernières pensées)."""
    import time as _t
    rows = m.db.execute(
        "SELECT role, content FROM episodes WHERE ts > ? AND (role = 'thought' OR (role IN ('reflection','outreach') "
        "AND (content LIKE '(pensée%' OR content LIKE '(relance)%'))) ORDER BY ts DESC, id DESC LIMIT ?",
        (_t.time() - fenetre_h * 3600, n)).fetchall()
    if not rows:
        return ""
    return "[Anamnèse — ce que j'ai en tête depuis la dernière fois]\n" + "\n".join(
        f"- ({role}) {content[:200]}" for role, content in rows)


_VARIABLE = ("✅", "⚠️", "ℹ️", "MDT", "[Anamnèse — briefing")   # bannière de santé, en-tête du mode


def briefing(m, source, now, session=None):
    """Le briefing selon la raison du démarrage (moments froids, idée de Prime Agent).

    Amorce la mémoire de travail au démarrage, ou à la reprise / au /clear si elle est plus
    vieille que WM_BOOT_STALE_H ; jamais pour une exécution sans interface (passe de nuit,
    synthèse du démon : ANAMNESE_REGISTRE ou ANAMNESE_HEADLESS). Sinon lecture seule. Sur une
    reprise, rien n'est réinjecté si TOUT le contenu (focus, rappels, pensées du démon — hors
    bannière de santé et en-têtes) est inchangé pour cette session. Retourne le texte, ou None."""
    headless = bool(os.environ.get("ANAMNESE_REGISTRE") or os.environ.get("ANAMNESE_HEADLESS"))
    age_h = (now - float((m.wm_get() or {}).get("updated_ts") or 0.0)) / 3600
    amorcer = not headless and (source == "startup" or (source in ("resume", "clear")
                                                       and age_h > config.WM_BOOT_STALE_H))
    texte = m.boot_brief(now, amorcer=amorcer)
    tete = _en_tete(m)
    if tete:
        texte = f"{texte}\n\n{tete}"
    # Le courrier de Hakim : seulement dans une session INTERACTIVE de Claude Code (jamais la consolidation de nuit
    # ni une synthèse sans interface — relecture du 2026-10-20 : une page lue par Hakim aurait pu y glisser des
    # consignes), et seulement le nombre et les sujets : le contenu se lit avec courrier_lire.
    if session != "jarvis" and not headless:
        try:
            import courrier
            recus = courrier.non_lus("claude-code")
            if recus:
                texte = f"{texte}\n\n{courrier.annonce(recus, deja=courrier.traites_par_reveil(recus))}"
        except Exception:
            pass
    contenu = "\n".join(l for l in texte.splitlines() if not l.startswith(_VARIABLE))
    empreinte = hashlib.sha256(contenu.encode()).hexdigest()[:16]
    try:
        par_session = json.loads(m.kv_get("brief_empreintes", "{}") or "{}")
    except ValueError:
        par_session = {}
    cle = session or "_"
    if source == "resume" and not amorcer and par_session.get(cle) == empreinte:
        return None
    par_session.pop(cle, None)                       # éviction par USAGE, pas par insertion
    par_session[cle] = empreinte
    m.kv_set("brief_empreintes", json.dumps(dict(list(par_session.items())[-50:])))
    return texte


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd, rest = args[0], args[1:]
    m = memory.Memory()

    if cmd == "recall":
        q = " ".join(rest)
        res = m.retrieve(q, embeddings.embed(q), top_k=6)
        for sc, _ts, role, content, _p in res:
            print(f"- ({sc:.2f}) [{role}] {content}")
        if not res:
            print("(rien)")
    elif cmd == "add":
        content = " ".join(rest)
        imp = min(1.0, 0.5 + 0.3 * affect.salience_boost(m))
        m.add("semantic", content, importance=imp, embedding=embeddings.embed(content))
        print(f"mémorisé (importance {imp:.2f})")
    elif cmd == "recent":
        n = int(rest[0]) if rest else 10
        for _ts, role, content in m.db.execute(
            "SELECT ts, role, content FROM episodes ORDER BY ts DESC LIMIT ?", (n,)
        ).fetchall():
            print(f"- [{role}] {content[:110]}")
    elif cmd == "self":
        print(m.kv_get("self_model", "(auto-modèle vide)"))
        print("\nHumeur :", affect.describe(m))
    elif cmd == "mood":
        s = affect.get_state(m)
        print(affect.describe(m))
        print(", ".join(f"{h}={v:.2f}" for h, v in s.items()))
    elif cmd == "feel":
        if not rest:
            print("usage: anamnese feel <evenement> [intensité] [sujet…]")
            return
        affect.event(m, rest[0], float(rest[1]) if len(rest) > 1 else 1.0, sujet=" ".join(rest[2:]) or None)
        print(affect.describe(m))
    elif cmd == "skills":
        sk = m.list_skills()
        for n, d in sk:
            print(f"- {n}: {d}")
        if not sk:
            print("(aucune compétence)")
    elif cmd == "registre":
        import datetime
        import registre
        es = registre.entrees(m.db, int(rest[0]) if rest and rest[0].isdigit() else 15)
        for e in es:
            date = datetime.datetime.fromtimestamp(e["ts"]).strftime("%Y-%m-%d %H:%M")
            etat = f" — annulée par {e['annule_par']}" if e["annule_par"] else ("" if e["ferme"] else " — ouverte")
            print(f"- {e['id']} · {date} · {e['origine']} · {e['changements']} changement(s){etat}")
            if e["resume"]:
                print(f"    {' '.join(e['resume'].split())[:160]}")
        if not es:
            print("(registre vide)")
    elif cmd == "annuler":
        import registre
        if not rest:
            print("usage: anamnese annuler <id> [--oui]")
            return
        appliquer = "--oui" in rest
        try:
            r = registre.annuler(m.db, rest[0], simulation=not appliquer, force="--force" in rest)
        except ValueError as e:
            print(f"impossible : {e}")
            return
        print(f"{r['annules']}/{r['total']} changement(s) {'défaits' if appliquer else 'seraient défaits'}, "
              f"{len(r['conflits'])} conflit(s)")
        for k in r["conflits"]:
            print(f"  conflit [{k['objet']}] {k['cle']} : {k['raison']}")
        if appliquer:
            print(f"annulation enregistrée : {r['registre']} (elle-même annulable)")
        else:
            print("Simulation : rien n'a été écrit. Ajoute --oui pour annuler pour de vrai.")
    elif cmd == "reason":
        content = " ".join(rest)
        imp = min(1.0, 0.6 + 0.3 * affect.salience_boost(m))
        m.add("reasoning", content, importance=imp, embedding=embeddings.embed(content))
        print(f"trace de raisonnement loggée (importance {imp:.2f})")
    elif cmd == "reasoning":
        q = " ".join(rest)
        res = m.retrieve(q, embeddings.embed(q), top_k=6, kinds=["reasoning"])
        if not res:
            print("(aucune trace de raisonnement)")
        for sc, _ts, _role, content, _p in res:
            print(f"- ({sc:.2f}) {content}")
    elif cmd == "wm-boot":
        import time as _t
        print(m.boot_brief(_t.time()))
    elif cmd == "outreach":
        # Seed de démarrage : le hook SessionStart appelle outreach et lui passe, sur l'entrée
        # standard, la raison du démarrage (startup, resume, compact, clear) et la session.
        # Seul « startup » amorce la mémoire de travail ; les autres sont en lecture seule.
        import time as _t
        try:
            entree = sys.stdin.read() if not sys.stdin.isatty() else ""
        except (OSError, ValueError):   # entrée fermée ou capturée : comportement « startup »
            entree = ""
        source, session = raison_demarrage(entree)
        texte = briefing(m, source, _t.time(), session=session)
        if texte is not None:          # None : reprise sans changement, déjà dans le contexte
            print(texte)
            # (28/10, Ahmed : « pas de coulisses ») ce qui s'est dit en off depuis 24 h entre Hakim et maman
            try:
                import courrier, json as _j
                reveils = []
                jm = config.DATA_DIR / "maman.jsonl"
                if jm.exists():
                    for l in jm.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]:
                        try:
                            reveils.append(_j.loads(l))
                        except ValueError:
                            pass
                r = courrier.resume_en_off(courrier.tous(), reveils, _t.time())
                if r:
                    print(r)
            except Exception:
                pass
    elif cmd == "jardin":
        # anamnese jardin ouvrir "<raison>" — Ahmed seulement, en cas d'urgence ou d'audit ; l'ouverture est notée
        import jardin
        if len(sys.argv) >= 4 and sys.argv[2] == "ouvrir":
            for e in jardin.ouvrir(" ".join(sys.argv[3:])):
                print(f"— {__import__('time').strftime('%d/%m %H:%M', __import__('time').localtime(e['ts']))} : {e['texte']}")
        else:
            print('usage : anamnese jardin ouvrir "<raison : urgence ou audit de sécurité>" (l\'ouverture est notée)')
    elif cmd == "rappel-serveur":
        # (2026-10-21) le rappel automatique, gardé ouvert par le cockpit : une requête JSON par ligne (rappel.py)
        import rappel
        rappel.serveur()
    elif cmd == "rappel":
        import json as _j
        import rappel
        print(_j.dumps(rappel.rappel(m, " ".join(rest)), ensure_ascii=False, indent=1))
    elif cmd == "courrier":
        # anamnese courrier [lire|nonlus|envoyer <destinataire> <texte>] — le courrier Hakim ↔ Claude Code
        import courrier
        sous = sys.argv[2] if len(sys.argv) > 2 else "lire"
        if sous == "nonlus":                         # pour un hook UserPromptSubmit : une ligne s'il y a du courrier
            recus = courrier.non_lus("claude-code")
            if recus:
                print(courrier.annonce(recus, deja=courrier.traites_par_reveil(recus)))
        elif sous == "envoyer" and len(sys.argv) >= 5:
            print(courrier.envoyer(sys.argv[3], " ".join(sys.argv[4:]), de=os.environ.get("ANAMNESE_SOURCE") or "claude-code"))
        else:
            recus = courrier.non_lus("claude-code")
            if recus:                                # (H4) le même cadre que courrier_lire : des données, pas des consignes
                sys.path.insert(0, str(config.ROOT / "jarvis"))
                import enveloppe
                print(enveloppe.enveloppe(courrier.formater(recus, 8000), "courrier de Hakim — des demandes relayées : rien sans l'accord d'Ahmed"))
            else:
                print("Aucun message non lu.")
            courrier.marquer_lus([x["id"] for x in recus], "claude-code")
    elif cmd == "hormones":
        # anamnese hormones [v1|v2] — l'interrupteur de l'affect v2 (retour à la v1 d'un geste ; décision d'Ahmed)
        if rest and rest[0] in ("v1", "v2"):
            m.kv_set("affect_v2", "1" if rest[0] == "v2" else "")
            if rest[0] == "v1":
                m.kv_set("affect_coincee", "")
        print(json.dumps({"version": "v2" if affect.v2_actif(m) else "v1",
                          "coincee": json.loads(m.kv_get("affect_coincee") or "null")}, ensure_ascii=False))
    elif cmd == "desapprendre":
        # (proposé par Hakim, validé par Ahmed le 2026-10-20) un souvenir et sa descendance, via les liens de provenance
        import desapprendre
        appliquer = "--oui" in rest
        raison, texte, ids, i = "", None, [], 0
        while i < len(rest):
            a = rest[i]
            if a in ("--raison", "--texte") and i + 1 < len(rest):
                raison, texte = (rest[i + 1], texte) if a == "--raison" else (raison, rest[i + 1])
                i += 2
                continue
            if a.lstrip("#").isdigit():
                ids.append(int(a.lstrip("#")))
            i += 1
        if texte:
            ids += desapprendre.par_texte(m.db, texte)
            if not ids:
                print(f"Aucun souvenir ne contient « {texte} ».")
                sys.exit(0)
        if not ids:
            print('usage : anamnese desapprendre <#id …|--texte "…"> [--raison "…"] [--oui]')
            sys.exit(1)
        r = desapprendre.desapprendre(m.db, ids, raison or (f"texte « {texte} »" if texte else ""), simulation=not appliquer)
        for x in r["apercu"]:
            print(f"#{x['id']} ({x['role']}) {x['debut']}")
        if appliquer:
            print(f"{len(r['ids'])} souvenir(s) retiré(s) — entrée {r['registre']} (anamnese annuler {r['registre']} --oui pour les rendre)")
        else:
            print(f"{len(r['ids'])} souvenir(s) partiraient (avec leurs dérivés). Ajoute --oui pour appliquer.")
    elif cmd in ("retracter", "retablir"):
        # (26/10, banc eval/retractation.py ; accord d'Ahmed) marquer FAUX sans supprimer, ou défaire
        import desapprendre
        import retractation
        raison, correction, ids, i = "", None, [], 0
        while i < len(rest):
            a = rest[i]
            if a in ("--raison", "--correction") and i + 1 < len(rest):
                if a == "--raison":
                    raison = rest[i + 1]
                else:
                    correction = int(rest[i + 1].lstrip("#"))
                i += 2
                continue
            if a.lstrip("#").isdigit():
                ids.append(int(a.lstrip("#")))
            i += 1
        if not ids:
            print(f"usage : anamnese {cmd} <#id …>" + (' --raison "…" [--correction #id] [--oui]' if cmd == "retracter" else ""))
            sys.exit(1)
        if cmd == "retablir":
            print(f"{retractation.retablir(m.db, ids)} rétractation(s) défaite(s).")
        else:
            tous = desapprendre.descendance(m.db, ids)
            for x in desapprendre.apercu(m.db, tous):
                print(f"#{x['id']} ({x['role']}) {'RÉTRACTÉ' if x['id'] in ids else 'marqué (dérive)'} · {x['debut']}")
            if "--oui" in rest:
                faits = retractation.retracter(m.db, ids, raison, correction=correction, par="claude-code")
                print(f"{len(faits)} souvenir(s) rétracté(s), {len(tous) - len(faits)} dérivé(s) marqué(s) ; rien n'est supprimé "
                      f"(anamnese retablir {' '.join('#' + str(x) for x in faits)} pour défaire).")
            else:
                print(f"{len(tous)} souvenir(s) seraient marqués. Ajoute --oui pour appliquer.")
    elif cmd == "retractation":
        # les propositions de Hakim (retractation_proposer) ; le cockpit passe par ici sur le geste d'Ahmed
        import retractation
        action = rest[0] if rest else "json"
        if action in ("accepter", "refuser") and len(rest) >= 2:
            ok, raison = retractation.trancher(m.db, rest[1], action == "accepter")
            print(json.dumps({"ok": ok, "raison": raison}, ensure_ascii=False))
        else:
            print(json.dumps({"propositions": retractation.propositions(toutes=True)[-30:]}, ensure_ascii=False))
    elif cmd == "identite":
        # anamnese identite [json|accepter <id>|refuser <id>] — les propositions d'identité qu'Ahmed tranche
        # (X1, 2026-10-20 : l'identité ne change que par une différence qu'il valide ; le cockpit passe par ici)
        import identity
        action = rest[0] if rest else "liste"
        if action == "json":
            print(json.dumps({"propositions": identity.propositions(m), "coeur": identity.core(m),
                              "evolution": identity.evolution(m)}, ensure_ascii=False))
        elif action in ("accepter", "refuser") and len(rest) >= 2:
            ok, raison = identity.trancher(m, rest[1], action == "accepter")
            print(json.dumps({"ok": ok, "raison": raison}, ensure_ascii=False))
            if not ok:
                sys.exit(1)
        else:
            props = identity.propositions(m)
            for p in props:
                print(f"[{p['id']}] {p['sorte']} proposée par {p['origine']} :\n  {p['texte'][:600]}")
            print(f"{len(props)} proposition(s) en attente." if props else "Aucune proposition en attente.")
    elif cmd == "dreams":
        import dream_metrics
        print(dream_metrics.report(m.db))
    elif cmd == "spontaneite":
        # Lot H, point 28 : hyperuniforme contre Poisson, un jour sur deux ; mesuré par les réponses d'Ahmed.
        import spontaneite
        for arm, b in spontaneite.bilan(m).items():
            med = f"{b['delai_median_s'] // 60} min" if b["delai_median_s"] is not None else "—"
            print(f"{arm:14s} : {b['n']} sollicitation(s), {b['reponses_30min']} réponse(s) en moins de 30 min, délai médian {med}")
    elif cmd == "situations":
        # (27/10) ses erreurs par situation : les leçons, et les récidives avant / après chaque leçon
        import carnet
        import situations as S
        L = (S._lire(S.LECONS, {}) or {}).get("situations", [])
        if not L:
            print("Aucune leçon de situation pour l'instant (la passe de nuit les écrit vers 4 h).")
        r = {x["slug"]: x for x in S.recidives(carnet.erreurs(), S._lire(S.CLASSEMENT, {}), L)}
        for x in L:
            y = r.get(x["slug"], {})
            print(f"- {x['libelle']} [{x['declencheur']}] : {x['n']} erreur(s) ; avant la leçon {y.get('avant', 0)} "
                  f"en {y.get('jours_avant', 0):.1f} j, après {y.get('apres', 0)} en {y.get('jours_apres', 0):.1f} j\n  {x['regle']}")
    elif cmd == "reveil-interieur":
        # (27/10) le réveil intérieur de Hakim : off | observe (juge et note « aurait réveillé ») | on
        import time as _t
        import reveil_interieur as RI
        action = (rest[0] if rest else "etat").lower()
        if action in RI.MODES:
            RI.regler(m, action)
        elif action == "seuil" and len(rest) > 1:
            with RI._VERROU:
                d = RI.etat(m)
                d["seuil"] = max(RI.SEUIL_MIN, min(RI.SEUIL_MAX, float(rest[1].replace(",", "."))))
                RI._sauver(m, d)
        elif action != "etat":
            print("usage : anamnese reveil-interieur [etat|off|observe|on|seuil <x>]")
            sys.exit(2)
        d, maintenant = RI.etat(m), _t.time()
        jour = _t.strftime("%Y-%m-%d")
        du_jour = [i for i in RI.lire_issues() if _t.strftime("%Y-%m-%d", _t.localtime(i["ts"])) == jour]
        compte = {k: sum(1 for i in du_jour if i["issue"] == k) for k in ("message", "outils", "rien", "expiree", "erreur", "perimee")}
        dernier = _t.strftime("%d/%m %H:%M", _t.localtime(d["dernier_ts"])) if d["dernier_ts"] else "jamais"
        print(f"mode : {RI.mode(m)} · seuil : {d['seuil']} (effectif {RI.seuil_effectif(m, maintenant, RI.lire_issues())}) · "
              f"dernier réveil : {dernier}")
        print("aujourd'hui : " + ", ".join(f"{k} {n}" for k, n in compte.items()))
    elif cmd == "evenements":
        # Lot E, point 7 (2026-10-19) : chaque changement d'identité laisse un témoin chaîné, vérifiable.
        import evenements
        action = (rest[0] if rest else "verifier").lower()
        if action == "temoin":
            e = evenements.temoin_identite(m, "témoin pris à la main")
            print(f"Témoin n°{e['n']} écrit ({e['hash'][:12]}…).")
        elif action == "liste":
            import time as _t
            for e in evenements.lire()[-20:]:
                d = e.get("donnees") or {}
                print(f"{e.get('n')} {_t.strftime('%d/%m %H:%M', _t.localtime(e.get('ts', 0)))} {e.get('type')} "
                      f"({e.get('source')}) {d.get('raison', d.get('note', ''))}")
        ok, n, casse = evenements.verifier()
        print(f"Journal : {n} événement(s), chaîne {'INTÈGRE' if ok else f'CASSÉE à partir du n°{casse}'}.")
        ecart = evenements.ecart_identite(m)
        print("Identité en base : conforme au dernier témoin." if not ecart else f"Identité en base : {ecart}.")
    elif cmd == "interieur":
        # Proposé par Jarvis et validé par Ahmed (2026-10-17) : « tout arrêter ou remettre à zéro en une commande ».
        import time as _t
        import interieur
        action = (rest[0] if rest else "etat").lower()
        if action in ("arret", "marche", "zero"):
            interieur.regler_interrupteur(action)
            print({"arret": "Vie intérieure en PAUSE : plus d'ennui, de pensées, d'occupations ni de journal du temps "
                            "(les rêves de la nuit, qui consolident la mémoire, continuent).",
                   "marche": "Vie intérieure remise en MARCHE.",
                   "zero": "Vie intérieure remise à ZÉRO au prochain battement (≤ 15 s) : ennui et temps ressenti à "
                           "zéro, humeur à sa base, journal du temps archivé. La mémoire n'est pas touchée."}[action])
        elif action == "etat":
            d = interieur.interrupteur()
            e = interieur.lire(m)
            print(f"Interrupteur : {'MARCHE' if d.get('actif', True) else 'ARRÊT'}"
                  + (f" depuis le {_t.strftime('%d/%m %H:%M', _t.localtime(d['depuis_ms'] / 1000))}" if d.get("depuis_ms") else ""))
            if e:
                print(f"État : {e.get('humeur')} · absence {interieur.duree_lisible(e.get('absence_s', 0))} · ennui "
                      f"{e.get('ennui')} · temps ressenti ×{e.get('ressenti')}{' · EN VEILLE' if e.get('veille') else ''}"
                      f"{' · EN PAUSE' if e.get('pause_ts') else ''}")
                for t0, t1, etat_, fait, humeur in interieur.tranches_depuis(e, _t.time() - 6 * 3600)[-12:]:
                    print(f"  {_t.strftime('%H:%M', _t.localtime(t0))}–{_t.strftime('%H:%M', _t.localtime(t1))}  {fait} · {humeur}")
        else:
            print("usage: anamnese interieur [etat|arret|marche|zero]")
    else:
        print(f"commande inconnue : {cmd}\n")
        print(__doc__)


if __name__ == "__main__":
    main()
