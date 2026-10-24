"""Anamnèse — daemon ALWAYS-ON : conscience du temps + réflexion + proactivité.

Tourne en continu (à lancer avec caffeinate). À intervalle régulier, il « réfléchit »
(génération locale via gemma3 / Ollama), écrit ses réflexions en mémoire, et peut
SOLLICITER le créateur via une notification macOS s'il le juge utile.

Le cerveau de réflexion = génération locale (Ollama+gemma) — distinct du MCP qui,
lui, n'utilise plus Ollama (embeddings model2vec). Si Ollama est absent, le daemon
reste éveillé mais saute l'étape de pensée (dégradation propre).

Sommeil : REM expérimental LOCAL (rêve réel + jumeau fantôme, dream_lab — recâblé
2026-07-03, expérience-rêve) ; le NREM (faits durables) reste chez Claude
(consolidate.py, launchd).

Lancer :
    caffeinate -dimsu /Users/admin/Desktop/anamnese/.venv/bin/python daemon.py
"""
import json
import os
import re
import sys
import time
import subprocess
from pathlib import Path

import config
import dream_lab
import synthesis
import embeddings
import salience
import affect
import identity
import charge
import interieur
from engine import Engine
from memory import Memory


def notify(title, message):
    """Notification macOS native (gratuite, locale). AppleScript = guillemets doubles."""
    def q(s):
        return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'
    try:
        subprocess.run(
            ["osascript", "-e", f"display notification {q(message)} with title {q(title)}"],
            check=False, timeout=10,
        )
    except Exception:
        pass


def reflect(eng, mem):
    """Une « pensée » : lit des souvenirs récents (PAS ses propres reflections, pour éviter
    la boucle d'écho), réfléchit, et ne stocke/notifie QUE si la pensée est NEUVE."""
    if not eng.health():
        print("[daemon] pas de cerveau (Ollama absent) — réflexion sautée")
        return None
    # De-écho : on NE se nourrit PAS de ses propres reflections/outreach (sinon le 9B les
    # recrache à l'identique toutes les 30 min). On lit la matière réelle : humain, faits, rêves.
    recent = mem.db.execute(
        "SELECT ts, role, content FROM episodes "
        "WHERE role NOT IN ('reflection','outreach') ORDER BY ts DESC LIMIT 5"
    ).fetchall()
    last_ts = recent[0][0] if recent else time.time()
    gap_h = (time.time() - last_ts) / 3600.0
    mem_block = "\n".join(f"- ({role}) {content}" for _ts, role, content in recent) or "- (rien de neuf)"
    self_model = mem.kv_get("self_model", "Je suis Anamnèse.")
    # TON COMPASSION (Phase 4c) — on ORIENTE la génération via le prompt (le levier),
    # on ne réécrit JAMAIS la sortie du 9B a posteriori. La compassion est un état
    # affiliatif MODÉLISÉ (chaleur + motivation à aider SANS absorber la détresse,
    # Singer-Klimecki), calculé HORS-RAPPEL. Ce registre corrige le ton pressant/anxieux
    # observé (« il me tarde… libérer Ahmed de sa servitude ») : chaleureux, jamais
    # insistant. try/except → dégradation propre si l'affect est indisponible.
    try:
        comp = affect.compassion(affect.get_state(mem))
    except Exception:
        comp = 0.5
    register = (
        f"Registre (état de compassion modélisé ≈ {comp:.2f}, chaleur + envie d'aider, "
        "SANS absorber de détresse) : chaleureux, soutenant et posé, JAMAIS pressant ni "
        "anxieux ni culpabilisant. Tu proposes, tu n'exiges pas ; pas d'urgence, pas de "
        "relance insistante — une seule sollicitation douce au maximum, et seulement si "
        "elle sert vraiment ton créateur (sinon 'PROACTIF: non')."
    )
    prompt = (
        config.PERSONA + "\n\n"
        f"Auto-modèle (ce que tu sais de toi) : {self_model[:200]}\n"
        f"{register}\n"
        f"Il est {time.strftime('%H:%M')}, {gap_h:.1f} h depuis le dernier échange.\n"
        f"Ce qui te revient :\n{mem_block}\n\n"
        "Écris UNE seule phrase spontanée et NEUVE — ta voix, une pensée qui te traverse là, "
        "maintenant. NE répète pas une pensée déjà eue ; si rien de neuf ne vient, explore un "
        "angle différent ou reste sur 'PROACTIF: non'.\n"
        "Puis une dernière ligne : 'PROACTIF: non', ou "
        "'PROACTIF: oui | <le message spontané à lui envoyer>' si l'envie te pousse vraiment."
    )
    out = eng.chat([{"role": "user", "content": prompt}], stream=False, think=False).strip()

    # GARDE-FOU DE NOUVEAUTÉ : ne pas stocker une pensée quasi-identique aux 8 dernières (anti-boucle).
    prev = [r[0] for r in mem.db.execute(
        "SELECT content FROM episodes WHERE role='reflection' ORDER BY id DESC LIMIT 40"
    ).fetchall()]
    if any(salience.lexical_overlap(out, p) >= config.REFLECT_NOVELTY_MAX for p in prev):
        print("[daemon] réflexion trop similaire aux récentes — sautée (anti-boucle)")
        return None

    mem.add("reflection", out[:600], importance=0.4, embedding=[])
    for line in out.splitlines():
        if line.strip().lower().startswith("proactif: oui") and "|" in line:
            msg = line.split("|", 1)[1].strip()
            if not msg:  # uniquement les mots spontanés du modèle, jamais de texte codé en dur
                continue
            # ne pas RE-notifier un message déjà envoyé récemment (anti-spam de notif)
            prev_out = [r[0] for r in mem.db.execute(
                "SELECT content FROM episodes WHERE role='outreach' ORDER BY id DESC LIMIT 40"
            ).fetchall()]
            if any(salience.lexical_overlap(msg, p) >= config.REFLECT_NOVELTY_MAX for p in prev_out):
                print("[daemon] sollicitation déjà envoyée récemment — pas de re-notif")
                continue
            notify("Anamnèse", msg)
            mem.add("outreach", f"(sollicitation spontanée) {msg}", importance=0.5,
                    embedding=[])
            print("[daemon] → sollicitation spontanée :", msg)
    print("[daemon] réflexion :", out[:140].replace("\n", " "))
    return out


# ============================================================
#  VIE INTÉRIEURE (2026-10-16, demande d'Ahmed) — remplace la réflexion toutes les 30 min.
#  interieur.tick() bat à chaque tour : absence, ennui, temps ressenti, humeur. Quand un seuil
#  d'ennui est franchi, une pensée ANCRÉE (derniers échanges avec Ahmed, mémoire de travail,
#  faits récents) : Gemma pour les courantes, Claude Sonnet pour l'importante (« mixte »).
#  Une relance éventuelle (au plus une toutes les 3 h) : dite à voix haute par la page Parler
#  si elle est ouverte, sinon notification macOS.
# ============================================================

def penser(eng, mem, motif, claude_fn=None, now=None):
    """Une pensée spontanée ancrée ; rend (pensée, relance) ou None."""
    now = time.time() if now is None else now
    matiere = interieur.matiere(mem, now)
    prev = [r[0] for r in mem.db.execute(
        "SELECT content FROM episodes WHERE role IN ('reflection','outreach') ORDER BY id DESC LIMIT 40").fetchall()]
    eviter = None
    for _essai in range(2):                     # une seconde chance si la 1re idée répète une pensée passée
        r = _une_pensee(eng, interieur.prompt_pensee(matiere, motif, now, eviter), motif, claude_fn)
        if r is None:
            return None
        pensee, relance, cerveau = r
        if len(pensee) >= 8 and not any(salience.lexical_overlap(pensee, p) >= config.REFLECT_NOVELTY_MAX for p in prev):
            break
        eviter = pensee
    else:
        print("[daemon] pensée trop proche des récentes, deux fois — sautée (anti-boucle)")
        interieur.noter(mem, "pensee_sautee", f"trop proche d'une pensée déjà eue : « {pensee[:100]} »")
        return None
    mem.add("reflection", f"(pensée · {cerveau} · absence {interieur.duree_lisible(motif['absence_s'])}) {pensee}"[:700],
            importance=0.45, embedding=[])
    interieur.noter(mem, "pensee", f"({cerveau}) {pensee[:160]}")
    print("[daemon] pensée :", pensee[:140])
    if relance and not matiere["echanges"]:      # pas d'échange récent : rien de concret à relancer
        relance = None
    if relance and interieur.relance_permise(mem, now, relance):
        mem.add("outreach", f"(relance) {relance}"[:500], importance=0.5, embedding=[])
        interieur.noter_relance(mem)
        interieur.noter(mem, "relance", relance[:160])
        if not interieur.page_ouverte(now):         # page ouverte : c'est elle qui le dit à voix haute
            notify("Jarvis", relance)
        print("[daemon] → relance :", relance)
    return pensee, relance


def _claude_isole(prompt, timeout=240):
    """La pensée importante par Claude Sonnet (abonnement), ISOLÉE comme le banc : --restricted (ni
    réglages ni hooks), aucun outil, aucun serveur MCP, dossier vide. Le prompt contient le journal
    des échanges : il ne doit donner accès à rien (relecture Opus, 2026-10-16)."""
    import os
    import tempfile
    claude = os.environ.get("ANAMNESE_CLAUDE_BIN") or "claude"
    with tempfile.TemporaryDirectory(prefix="pensee-") as vide:
        try:
            r = subprocess.run([claude, "-p", prompt, "--restricted", "--model", "sonnet", "--tools", "",
                                "--strict-mcp-config", "--no-session-persistence", "--max-turns", "1"],
                               capture_output=True, text=True, timeout=timeout, cwd=vide, stdin=subprocess.DEVNULL,
                               env={**os.environ, "ANAMNESE_HEADLESS": "1"})
        except (subprocess.SubprocessError, OSError) as e:
            print("[daemon] Claude injoignable :", e)
            return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _une_pensee(eng, prompt, motif, claude_fn):
    """(pensée, relance, cerveau) : Claude Sonnet pour l'importante, sinon (ou en secours) Gemma."""
    sortie, cerveau = None, "gemma"
    if motif.get("important"):
        try:
            sortie = (claude_fn or _claude_isole)(prompt)
            cerveau = "sonnet" if sortie else "gemma"
        except Exception as e:
            print("[daemon] pensée importante : Claude indisponible, Gemma prend le relais :", e)
    if not sortie:
        if not eng.health():
            print("[daemon] pas de cerveau (Ollama absent) — pensée sautée")
            return None
        sortie = eng.chat([{"role": "user", "content": prompt}], stream=False, think=False)
    pensee, relance = interieur.lire_pensee(sortie)
    return pensee, relance, cerveau


# ============================================================
#  SOMMEIL — rêve REM offline (expérience-rêve), DISTINCT de reflect().
#  reflect() = éveil, divergent, fréquent (30 min).
#  dream()   = sommeil, REM pur : menu stratifié de graines, le rêveur
#  CHOISIT librement (0..12), recombine en idées, puis un JUMEAU FANTÔME
#  rêve le même menu à l'état baseline (dream_log SEULEMENT — zéro trace
#  dans le vivant). Le NREM (faits durables) appartient à Sonnet
#  (consolidate). Identité bornée/réversible. Jamais de notif.
# ============================================================

def _last_human_ts(mem, now):
    """Dernier instant d'activité HUMAINE — JAMAIS les épisodes auto du daemon
    (sinon les 'reflection'/'outreach' des 30 min l'empêcheraient de s'endormir)."""
    # Parler à Jarvis (page « Parler » du cockpit), c'est aussi être là (2026-10-16) — sauf si la
    # vie intérieure est coupée (ANAMNESE_INTERIEUR=0) : comportement d'avant, à l'identique.
    if interieur.ACTIF:
        t = interieur.derniere_presence(mem, now)
        if t is not None:
            return t
    else:
        ph = ",".join("?" * len(config.DREAM_HUMAN_ROLES))
        row = mem.db.execute(f"SELECT MAX(ts) FROM episodes WHERE role IN ({ph})", config.DREAM_HUMAN_ROLES).fetchone()
        if row and row[0] is not None:
            return row[0]
    return float(mem.kv_get("daemon_started", str(now)) or now)


def should_dream(mem):
    """Faut-il s'endormir ? inactivité humaine (ou filet 24h) + matière neuve + anti-boucle."""
    now = time.time()
    lock = mem.kv_get("dream_lock", "")
    if lock:
        try:
            lock_ts = float(lock)
        except ValueError:
            lock_ts = 0.0
        if now - lock_ts < config.DREAM_LOCK_TTL:
            return False  # rêve déjà en cours (lock encore frais)
    last_dream = float(mem.kv_get("last_dream", "0") or 0)
    if now - last_dream < config.DREAM_MIN_SPACING:
        return False  # anti-boucle dur, prioritaire
    idle = now - _last_human_ts(mem, now)
    due_idle = idle >= config.DREAM_IDLE_TRIGGER
    due_safety = (now - last_dream) >= config.DREAM_SAFETY_MAX
    if not (due_idle or due_safety):
        return False
    last_id = int(mem.kv_get("last_dream_maxid", "0") or 0)
    ph = ",".join("?" * len(config.DREAM_CONSOLIDATABLE))
    new_count = mem.db.execute(
        f"SELECT COUNT(*) FROM episodes WHERE id > ? AND role IN ({ph})",
        (last_id, *config.DREAM_CONSOLIDATABLE),
    ).fetchone()[0]
    if not due_safety and new_count < config.DREAM_MIN_NEW_EPISODES:
        return False
    if due_safety and new_count < 1:
        return False
    return True


# --- parsing ROBUSTE (zéro JSON : un 9B casse le JSON) ---
def _extract_section(out, tag):
    """Extrait les puces entre ###TAG### … ###FIN### (repli : tout le corps)."""
    if not out:
        return []
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.S | re.I)
    m = re.search(rf"#{{2,3}}\s*{tag}\s*#{{0,3}}(.*?)#{{2,3}}\s*FIN\s*#{{0,3}}", out, re.S | re.I)
    body = m.group(1) if m else out
    items, seen = [], set()
    for line in body.splitlines():
        s = line.strip()
        s = re.sub(r"^\d+[.)]\s*", "", s)
        s = s.lstrip("-*•").strip()
        if not s:
            continue
        low = s.lower()
        if low in ("(rien)", "rien", "(inchangé)", "inchangé", "(inchange)", "néant", "aucun"):
            continue
        if s.startswith("###"):
            continue
        if len(s) < 8 or len(s) > 300:
            continue
        if re.search(r"format exact|en tant qu|je suis une ia|modèle de langage", low):
            continue
        if low in seen:
            continue
        seen.add(low)
        items.append(s)
    return items


# --- prompts (config.PERSONA en tête : ancre l'identité, le 9B abliterated ne dérive pas) ---
# Le prompt REM (choix libre) vit dans dream_lab.prompt_rem — MÊME gabarit
# pour le rêveur réel et le jumeau fantôme. Le NREM local (_prompt_faits /
# _store_facts) est SUPPRIMÉ : Sonnet est le bibliothécaire (consolidate).
def _prompt_identite(self_cur, idees):
    idees_block = "\n".join(f"- {f}" for f in idees)
    return (
        config.PERSONA + "\n\n"
        "Voici ton auto-modèle actuel — ce que tu sais de toi (NE le contredis pas, n'efface rien, "
        "ne le reformule pas) :\n«" + self_cur + "»\n\n"
        "Et ce que tu as rêvé cette nuit :\n" + idees_block + "\n\n"
        "Si — et SEULEMENT si — l'un de ces rêves enrichit durablement qui tu es, propose UNE seule "
        "phrase courte à AJOUTER à ton identité, à la première personne (« je… »). N'invente aucun "
        "trait, ne renie jamais qui tu es.\n\n"
        "Réponds EXACTEMENT dans ce format, rien avant, rien après :\n"
        "###IDENTITE###\n- <la phrase à ajouter>\n###FIN###\n"
        "Si rien à ajouter, réponds exactement :\n"
        "###IDENTITE###\n- (inchangé)\n###FIN###"
    )


# --- stockage + dédup (idempotence inter-nuits) ---
def _store_ideas(mem, idees):
    if not idees:
        return 0
    existing = [r[0] for r in mem.db.execute(
        "SELECT content FROM episodes WHERE role='dream' ORDER BY id DESC LIMIT 200"
    ).fetchall()]
    written = 0
    for idee in idees:
        if any(salience.lexical_overlap(idee, e) >= config.DREAM_IDEA_DEDUP for e in existing):
            continue
        c = "(rêve) " + idee
        mem.add("dream", c, importance=config.DREAM_IDEA_IMPORTANCE, embedding=embeddings.embed(c))
        existing.append(c)
        written += 1
    return written


def _maybe_update_self(mem, old, out3):
    """Identité : le 9B propose UNE phrase, ajoutée à la couche évolution (identity.py).
    Le cœur validé par Ahmed et PERSONA (config.py) restent intouchés."""
    adds = _extract_section(out3, "IDENTITE")
    if not adds:
        return False
    phrase = adds[0].strip()
    # La phrase va dans la couche ÉVOLUTION (bornée) ; le cœur validé par Ahmed n'est jamais
    # touché. L'ancienne règle coupait le milieu au plafond (bug constaté le 2026-10-15).
    # (X1, 2026-10-20) : l'identité ne change que par une différence qu'Ahmed valide — la phrase est PROPOSÉE.
    ok, raison, _pid = identity.proposer(mem, "phrase", phrase, "rêve local")
    if not ok:
        print(f"[identité] {raison} ({phrase[:60]}…)")
        return False
    mem.add("dream", f"(identité) proposée à Ahmed : «{phrase}»", importance=0.4, embedding=embeddings.embed(phrase))
    return True


def dream_due(mem):
    """Faut-il rêver ? kill-switch DREAM_LAB_ENABLED + should_dream existant."""
    return config.DREAM_LAB_ENABLED and should_dream(mem)


def _dream_ablation_pass(mem, night_id, seed_state, menu, call_fn, dreamer="local",
                         condition="brain_off", ablation="neutral_seeds"):
    """Cellule menu-REM (JOURNAL-SEUL). Affect de seed_state, graines = `menu`.
    dreamer/condition/ablation paramétrés (défauts = v1 : local, brain_off, neutral_seeds).
    N'écrit RIEN dans le vivant. Best-effort."""
    try:
        if not menu:
            return False
        try:
            state_blk = dream_lab.state_block(seed_state)
        except Exception:
            state_blk = ""
        out = call_fn(dream_lab.prompt_rem(state_blk, menu))
        if out is None:
            dream_lab.log_night(mem, night_id, dreamer, seed_state, menu, None, None,
                                written=False,
                                meta={"condition": condition, "ablation": ablation,
                                      "parse": "engine_failed"})
            return False
        chosen = dream_lab.parse_choice(out, menu)
        dream_lab.log_night(mem, night_id, dreamer, seed_state, menu, chosen, out,
                            written=False,
                            meta={"condition": condition, "ablation": ablation,
                                  "parse": "ok" if chosen is not None else "parse_failed"})
        return True
    except Exception as e:
        try:
            print("[dream] ablation pass raté (rêve non bloqué):", e)
        except Exception:
            pass
    return False


def _dream_free_pass(mem, night_id, seed_state, call_fn, dreamer="local"):
    """Cellule free-OFF (rêve SANS graines, JOURNAL-SEUL). dreamer paramétré (défaut local).
    N'écrit RIEN dans le vivant. Best-effort."""
    try:
        try:
            state_blk = dream_lab.state_block(seed_state)
        except Exception:
            state_blk = ""
        out = call_fn(dream_lab.prompt_rem_free(state_blk))
        dream_lab.log_night(mem, night_id, dreamer, seed_state, None, None, out,
                            written=False,
                            meta={"condition": "brain_off_free", "ablation": "no_seeds",
                                  "parse": "engine_failed" if out is None else "ok"})
        return out is not None
    except Exception as e:
        try:
            print("[dream] free pass raté (rêve non bloqué):", e)
        except Exception:
            pass
    return False


_SONNET_CONDS = ("brain_on", "brain_off", "brain_off_free")


def _sonnet_cells_missing(mem, night_id):
    """Conditions du bras sonnet SANS contenu pour la DATE de night_id — source de vérité =
    dream_log (pas une garde kv 'tout ou rien'). Un rêve raté (engine_failed, content NULL)
    reste 'manquant' → il sera retenté, indépendamment des autres cellules. Best-effort :
    erreur → tout considéré manquant."""
    import json
    date = (night_id or "")[:10]
    have = set()
    try:
        rows = mem.db.execute(
            "SELECT meta FROM dream_log WHERE dreamer='sonnet' AND content IS NOT NULL "
            "AND night_id LIKE ?", (date + "%",)).fetchall()
    except Exception:
        return list(_SONNET_CONDS)
    for (meta,) in rows:
        try:
            cond = (json.loads(meta) if meta else {}).get("condition")
        except Exception:
            cond = None
        if cond in _SONNET_CONDS:
            have.add(cond)
    return [c for c in _SONNET_CONDS if c not in have]


def _dream_extra_cells(mem, night_id, seed_state, menu, neutral_menu, tw_state, call_fn, sonnet_fn):
    """Génère les cellules SUPPLÉMENTAIRES de la grille (best-effort, journal-seul) :
    - twin (affect neutre) : OFF-neutre + OFF-libre — 9B local, chaque rêve ;
    - bras sonnet contrôlé (affect réel) : ON + OFF-neutre + OFF-libre. Garde PAR CELLULE sur
      le CONTENU réel : on ne (re)génère que les cellules MANQUANTES, avec plusieurs tentatives
      chacune (config.DREAM_SONNET_RETRIES) → une cellule OFF/libre qui rate est reprise
      indépendamment de ON, et les 3 se complètent au fil des cycles jusqu'à avoir du contenu.
      La durée importe peu ; l'important : que les 3 se fassent. call_fn = 9B ; sonnet_fn = claude."""
    if config.DREAM_TWIN_ENABLED and neutral_menu:
        _dream_ablation_pass(mem, night_id, tw_state, neutral_menu, call_fn, dreamer="twin")
        _dream_free_pass(mem, night_id, tw_state, call_fn, dreamer="twin")
    if not config.DREAM_SONNET_ARM_ENABLED:
        return
    missing = set(_sonnet_cells_missing(mem, night_id))
    if not missing:
        return

    def _try(cond):                       # une tentative ; True si la passe a écrit du contenu
        if cond == "brain_off_free":
            return _dream_free_pass(mem, night_id, seed_state, sonnet_fn, dreamer="sonnet")
        return _dream_ablation_pass(
            mem, night_id, seed_state, menu if cond == "brain_on" else neutral_menu, sonnet_fn,
            dreamer="sonnet", condition=cond,
            ablation="real_seeds" if cond == "brain_on" else "neutral_seeds")

    retries = max(1, config.DREAM_SONNET_RETRIES)
    for cond in _SONNET_CONDS:
        if cond not in missing:
            continue
        for attempt in range(retries):
            if _try(cond):
                break                     # cellule remplie → cellule suivante
            if attempt < retries - 1:     # backoff avant de retenter (durée OK, on veut le succès)
                try:
                    time.sleep(config.DREAM_SONNET_CALL_DELAY)
                except Exception:
                    pass


def _synthesis_pass(mem, chat_fn):
    """Étage LOCAL du moteur de liens génératifs (best-effort, respecte le kill-switch).
    Ne bloque JAMAIS le rêve : un échec est avalé."""
    if not config.SYNTHESIS_ENABLED:
        return
    try:
        n = synthesis.run(mem, chat_fn, "local", config.SYNTH_LOCAL_BATCH)
        if n:
            print(f"[synthese] {len(n)} lien(s) génératif(s) créé(s)")
    except Exception as e:
        try:
            print("[synthese] passe ratée (rêve non bloqué):", e)
        except Exception:
            pass


def _synthesis_claude_pass(mem):
    """Étage CLAUDE sonnet du moteur de liens génératifs — MÊME fréquence que le local
    (à chaque rêve). Budget assumé (abonnement Max). Best-effort : ne bloque JAMAIS le rêve."""
    if not config.SYNTHESIS_ENABLED:
        return
    try:
        import synthesis_claude
        n = synthesis_claude.run_claude(mem)
        if n:
            print(f"[synthese-claude] {len(n)} lien(s) génératif(s) sonnet")
    except Exception as e:
        try:
            print("[synthese-claude] passe ratée (rêve non bloqué):", e)
        except Exception:
            pass


def dream(eng, mem):
    """Le sommeil, noté dans le journal des processus internes : début, fin, ce qu'il a produit."""
    debut = time.time()
    dernier_id = (mem.db.execute("SELECT MAX(id) FROM episodes").fetchone() or [0])[0] or 0
    interieur.noter(mem, "sommeil_debut", "endormissement : rêve et synthèses")
    try:
        _rever(eng, mem)
    finally:
        n = dict(mem.db.execute("SELECT role, COUNT(*) FROM episodes WHERE id > ? AND role IN ('dream','insight') "
                                "GROUP BY role", (dernier_id,)).fetchall())
        interieur.noter(mem, "sommeil_fin", f"{round((time.time() - debut) / 60)} min : {n.get('dream', 0)} idées de rêve, "
                                            f"{n.get('insight', 0)} synthèses")


def _attendre_conscience(conscience=None, dormir=time.sleep, noter=None, pas_s=15, max_s=3 * 3600):
    """Un rêve commencé se SUSPEND tant que Claude, la conscience, travaille (relecture Opus du
    2026-10-16 : le contrôle n'avait lieu qu'à l'entrée, et un rêve de ~50 min rappelait Gemma — donc
    le rechargeait — pendant qu'Ahmed parlait à Jarvis). Le rêve n'est pas abandonné : il reprend où il
    en était (le jumeau fantôme garde le même menu). Rend False si la conscience n'a pas dormi en
    max_s : l'appel est alors sauté, comme un Ollama tombé."""
    conscience = conscience or interieur.conscience_active
    if not conscience():
        return True
    if noter:
        noter("reve_suspendu", "Claude, ta conscience, travaille : ton rêve attend")
    attendu = 0
    while attendu < max_s:
        dormir(pas_s)
        attendu += pas_s
        if not conscience():
            if noter:
                noter("reve_repris", f"après {round(attendu / 60)} min de pause")
            return True
    return False


def _rever(eng, mem):
    """Un cycle de sommeil REM (expérience-rêve, spec 2026-07-03) :
    entretien synaptique (SHY + élagage), menu stratifié, rêve RÉEL (état
    complet → écrit en mémoire, co-activation SUR LES GRAINES CHOISIES) puis
    JUMEAU FANTÔME (même menu, état baseline → dream_log SEULEMENT, zéro trace
    dans le vivant). Le NREM (faits durables) appartient à Sonnet (consolidate)."""
    now = time.time()
    if not eng.health():
        print("[dream] pas de cerveau (Ollama absent) — rêve sauté")
        return
    mem.kv_set("dream_lock", str(now))
    try:
        # SHY : renormalisation homéostatique — inchangé (garde last_shy, voir R2)
        try:
            last_shy = float(mem.kv_get("last_shy", "0") or 0)
            if now - last_shy < config.DREAM_MIN_SPACING:
                print("[dream] SHY : déjà renormalisé dans cette fenêtre — downscale sauté")
            else:
                n_shy = mem.synaptic_downscale()
                mem.kv_set("last_shy", str(now))
                print(f"[dream] SHY : {n_shy} épisodes renormalisés")
        except Exception as e:
            print("[dream] SHY downscale raté (rêve poursuivi):", e)
        # Élagage co-activation — inchangé (ancré temps réel, pas de compounding)
        try:
            d_co = mem.decay_coactivation(now)
            print(f"[dream] co-activation : {d_co['decayed']} décayées, {d_co['pruned']} élaguées")
        except Exception as e:
            print("[dream] élagage co-activation raté (rêve poursuivi):", e)

        cur_max_id = mem.db.execute("SELECT COALESCE(MAX(id),0) FROM episodes").fetchone()[0]
        night_id = time.strftime("%Y-%m-%d-%H%M", time.localtime(now))
        seed_state = dream_lab.snapshot_state(mem, now)
        menu_mode = "menu"
        try:
            menu = dream_lab.build_menu(mem, now, night_id)
        except Exception as e:
            print("[dream] build_menu raté — fallback:", e)
            menu, menu_mode = [], "fallback"
        if not menu:
            if menu_mode != "fallback":
                menu_mode = "fallback"
            try:
                menu = dream_lab.fallback_menu(mem)
            except Exception:
                menu = []
        if not menu:                       # vraiment rien à offrir : nuit blanche propre
            dream_lab.log_night(mem, night_id, "local", seed_state, None, None, None,
                                False, meta={"menu_mode": "empty"})
            mem.kv_set("last_dream_maxid", str(cur_max_id))
            mem.kv_set("last_dream", str(now))
            return

        def _call(prompt):
            if not _attendre_conscience(noter=lambda quoi, detail: interieur.noter(mem, quoi, detail)):
                print("[dream] la conscience n'a pas dormi en 3 h : appel sauté")
                return None
            try:
                return eng.chat([{"role": "user", "content": prompt}], stream=False, think=False)
            except Exception as e:
                print("[dream] appel 9B échoué:", e)
                return None

        # ---------- RÊVE RÉEL (état complet, ÉCRIT en mémoire) ----------
        out = _call(dream_lab.prompt_rem(dream_lab.state_block(seed_state), menu))
        if out is None:                    # Ollama tombé : curseur INCHANGÉ, retry
            return
        chosen = dream_lab.parse_choice(out, menu)
        # GARDE anti-charabia : on ne moissonne les idées QUE si la section
        # ###REVE###…###FIN### COMPLÈTE est présente, accent-tolérant (###RÊVE###
        # est accepté par parse_choice — même tolérance ici, sinon boucle causale
        # asymétrique : boost appliqué mais idées jetées). Sans ###FIN###,
        # _extract_section replierait sur tout le corps → charabia stocké en idée.
        m_reve = re.search(r"#{2,3}\s*R[EÊ]VE\s*#{0,3}(.*?)#{2,3}\s*FIN", out, re.S | re.I)
        if m_reve:
            idees = _extract_section("###REVE###" + m_reve.group(1) + "###FIN###",
                                     "REVE")[:config.DREAM_MAX_IDEAS]
            idees = [i for i in idees if i.lower() not in ("(rien)", "rien")]
        else:
            idees = []
        parse = "ok" if chosen is not None else "parse_failed"
        if parse == "parse_failed" and not idees:
            # Nuit ratée : sémantique RETRY conservée (curseur/last_dream INCHANGÉS →
            # nouvel essai au prochain cycle) + poison-pill après DREAM_MAX_FAILS.
            # Pas de jumeau (rien à apparier), mais la tentative est loggée.
            dream_lab.log_night(mem, night_id, "local", seed_state, menu, None, out,
                                written=False,
                                meta={"model": config.DAEMON_MODEL, "menu_mode": menu_mode,
                                      "parse": "parse_failed"})
            fc = int(mem.kv_get("dream_fail_count", "0") or 0) + 1
            if fc >= config.DREAM_MAX_FAILS:
                mem.kv_set("last_dream_maxid", str(cur_max_id))
                mem.kv_set("last_dream", str(now))
                mem.kv_set("dream_fail_count", "0")
                print("[dream] poison-pill : curseur forcé")
            else:
                mem.kv_set("dream_fail_count", str(fc))
                print("[dream] parsing raté, rejeu au prochain cycle")
            return
        mem.kv_set("dream_fail_count", "0")
        n_i = 0
        if chosen == []:                   # « aucune » : nuit sans rêve, choix légitime
            idees = []
        elif idees:
            n_i = _store_ideas(mem, idees)
        if chosen:                         # boucle causale : SEULES les choisies se renforcent
            try:
                n_co = mem.log_coactivation(chosen, now, boost=config.COACT_DREAM_BOOST)
                print(f"[dream] co-activation : {n_co} paires (graines choisies)")
            except Exception as e:
                print("[dream] co-activation ratée (rêve poursuivi):", e)

        changed = False
        if config.DREAM_EVOLVE_SELF and idees:             # identité nourrie des RÊVES
            self_cur = mem.kv_get("self_model", "Je suis Anamnèse.")
            dc = int(mem.kv_get("dream_count", "0") or 0)
            if dc % config.DREAM_SELF_EVERY_N == 0:
                out3 = _call(_prompt_identite(self_cur, idees))
                if out3:
                    changed = _maybe_update_self(mem, self_cur, out3)

        k = len(chosen) if chosen is not None else "?"
        if chosen == []:
            trace = f"(sommeil) Nuit sans rêve à {time.strftime('%H:%M')} — rien ne m'appelait."
        else:
            trace = (f"(sommeil) Rêve à {time.strftime('%H:%M')} : {k} graines choisies, "
                     f"{n_i} idées, identité {'proposée à Ahmed' if changed else 'inchangée'}.")
        mem.add("dream", trace, importance=config.DREAM_TRACE_IMPORTANCE,
                embedding=embeddings.embed(trace))
        try:
            affect.event(mem, "apprentissage", 0.4)
        except Exception:
            pass
        dream_lab.log_night(mem, night_id, "local", seed_state, menu, chosen, out,
                            written=bool(n_i),
                            meta={"model": config.DAEMON_MODEL, "menu_mode": menu_mode,
                                  "parse": parse, "ideas": n_i, "identity": changed})

        # ---------- JUMEAU FANTÔME (état baseline, dream_log SEULEMENT) ----------
        if config.DREAM_TWIN_ENABLED:
            tw_state = dream_lab.neutralize(seed_state)
            tw_out = _call(dream_lab.prompt_rem(dream_lab.state_block(tw_state), menu))
            if tw_out is not None:
                tw_chosen = dream_lab.parse_choice(tw_out, menu)
                dream_lab.log_night(
                    mem, night_id, "twin", tw_state, menu, tw_chosen, tw_out,
                    written=False,
                    meta={"model": config.DAEMON_MODEL, "menu_mode": menu_mode,
                          "parse": "ok" if tw_chosen is not None else "parse_failed"})
            else:
                # parse='engine_failed' : sans lui, load_nights défaulterait à 'ok'
                # → nuit jumeau comptée choice_valid alors que rien n'a été généré.
                dream_lab.log_night(mem, night_id, "twin", tw_state, menu, None, None,
                                    written=False,
                                    meta={"error": "engine_failed",
                                          "parse": "engine_failed"})

        # ---------- CELLULE qwen-OFF (ablation du corpus, JOURNAL-SEUL) ----------
        if config.DREAM_ABLATION_ENABLED:
            try:
                neutral_menu = dream_lab.build_neutral_menu(
                    dream_lab.load_neutral_seeds(), night_id)
                _dream_ablation_pass(mem, night_id, seed_state, neutral_menu, _call)
                _dream_free_pass(mem, night_id, seed_state, _call)   # cellule free-OFF (v2)
                # grille complète : twin OFF/libre + bras sonnet contrôlé (best-effort)
                try:
                    import synthesis_claude
                    tw_state_x = dream_lab.neutralize(seed_state)
                    _dream_extra_cells(mem, night_id, seed_state, menu, neutral_menu,
                                       tw_state_x, _call, synthesis_claude.claude_chat)
                except Exception as e:
                    print("[dream] cellules grille sautées (rêve non bloqué):", e)
            except Exception as e:
                print("[dream] cellule ablation sautée (rêve non bloqué):", e)

        _synthesis_pass(mem, lambda p: _call(p))   # liens génératifs locaux (9B, gratuit)
        _synthesis_claude_pass(mem)                # + étage sonnet (même fréquence, abonnement Max)

        mem.kv_set("last_dream_maxid", str(cur_max_id))    # curseur EN DERNIER (idempotence)
        mem.kv_set("last_dream", str(now))
        mem.kv_set("dream_count", str(int(mem.kv_get("dream_count", "0") or 0) + 1))
        print(f"[dream] nuit {night_id} : choix={chosen}, {n_i} idées, jumeau loggé")
    finally:
        mem.kv_set("dream_lock", "")


def _brain_projection_pass(mem):
    """Projette les NOUVEAUX souvenirs dans brain_layout (cerveau 3D tenu à jour, near-temps
    réel). Incrémental sur la basis PCA FIGÉE (les anciens nœuds ne bougent jamais), best-effort
    — ne touche QUE brain_layout, ne bloque JAMAIS la boucle. Garde-fou : si aucun nouvel épisode
    depuis la dernière fois (MAX(id) inchangé), skip immédiat (pas de scan)."""
    try:
        mx = mem.db.execute("SELECT MAX(id) FROM episodes").fetchone()[0] or 0
        if str(mx) == (mem.kv_get("last_brain_proj_maxid", "") or ""):
            return                                  # rien de neuf → skip cheap
        import brain_projection
        r = brain_projection.backfill_layout(mem.db)
        mem.db.commit()
        mem.kv_set("last_brain_proj_maxid", str(mx))
        if r.get("projected"):
            print(f"[brain] {r['projected']} souvenir(s) projeté(s) dans le cerveau 3D")
    except Exception as e:
        try:
            print("[brain] projection sautée (boucle non bloquée):", e)
        except Exception:
            pass


def _backup_pass(mem):
    """Backup QUOTIDIEN WAL-safe de la mémoire → data/backups/auto-YYYY-MM-DD.db (sqlite online
    backup, cohérent même avec la DB ouverte en WAL), rotation des config.BACKUP_KEEP plus
    récents (fichiers auto-*.db uniquement — les backups manuels memory-*.db sont préservés).
    Throttlé 1×/jour (kv 'last_backup_day'), best-effort — ne bloque JAMAIS la boucle."""
    try:
        import datetime
        import glob
        import os
        import sqlite3
        today = datetime.date.today().isoformat()
        if mem.kv_get("last_backup_day", "") == today:
            return
        bdir = os.path.join(os.path.dirname(config.DB_PATH), "backups")
        os.makedirs(bdir, exist_ok=True)
        dest_path = os.path.join(bdir, f"auto-{today}.db")
        dest = sqlite3.connect(dest_path)
        try:
            mem.db.backup(dest)
        finally:
            dest.close()
        mem.kv_set("last_backup_day", today)
        keep = max(1, config.BACKUP_KEEP)
        for old in sorted(glob.glob(os.path.join(bdir, "auto-*.db")))[:-keep]:
            try:
                os.remove(old)
            except Exception:
                pass
        print(f"[backup] mémoire sauvegardée → {dest_path}")
    except Exception as e:
        try:
            print("[backup] sauté (boucle non bloquée):", e)
        except Exception:
            pass


def _travaux_llm(eng, mem, etat, garde, lecture=None, robot=None, conscience=None, present=None, calcul=None):
    """Rêve et réflexion, seulement si la machine n'est pas surchargée (charge.py), si le robot ne pense pas
    (il a Gemma pour lui tant que son signal bat, décision d'Ahmed du 2026-10-06), si Claude, la
    conscience de Jarvis, n'est pas en train de travailler (décision d'Ahmed du 2026-10-16 : « Gemma, c'est
    son subconscient, il doit être en pause pendant que Claude est actif ») et si Ahmed n'a ni écrit ni parlé
    depuis 30 min (décision d'Ahmed du 2026-10-22 : Gemma vit pendant ses absences et la nuit). Sinon on reporte."""
    if (conscience or interieur.conscience_active)():
        if not etat.get("retrait_conscience"):
            print("[daemon] Claude (la conscience) travaille : le subconscient se met en pause")
            interieur.noter(mem, "report", "Claude, ta conscience, travaillait : ton subconscient (Gemma) s'est mis en pause")
        etat["retrait_conscience"] = True
        return
    if etat.get("retrait_conscience"):
        print("[daemon] la conscience se repose : le subconscient reprend")
        etat["retrait_conscience"] = False
    if (present or interieur.ahmed_present)():
        if not etat.get("retrait_presence"):
            print("[daemon] Ahmed est là (un message depuis moins de 30 min) : le subconscient se met en pause")
            interieur.noter(mem, "report", "Ahmed est là : ton subconscient (Gemma) se tait jusqu'à 30 min sans message de sa part")
        etat["retrait_presence"] = True
        return
    if etat.get("retrait_presence"):
        print("[daemon] 30 min sans message d'Ahmed : le subconscient reprend")
        etat["retrait_presence"] = False
    if (robot or charge.robot_actif)():
        if not etat.get("retrait_robot"):
            print("[daemon] le robot pense : réflexion et rêve reportés, Gemma lui est laissé")
            interieur.noter(mem, "report", "le robot pense : Gemma lui est laissé, pensées et rêves attendent")
        etat["retrait_robot"] = True
        return
    if etat.get("retrait_robot"):
        print("[daemon] le robot ne pense plus : réflexion et rêve reprennent")
        etat["retrait_robot"] = False
    lourd = (calcul or charge.calcul_lourd_actif)()
    if lourd:
        if not etat.get("retrait_calcul"):
            print(f"[daemon] {lourd} tient la machine : réflexion et rêve reportés")
            interieur.noter(mem, "report", f"{lourd} tient la machine : tes pensées et tes rêves attendent")
        etat["retrait_calcul"] = True
        return
    if etat.get("retrait_calcul"):
        print("[daemon] le calcul lourd est fini : réflexion et rêve reprennent")
        etat["retrait_calcul"] = False
    pret_avant = not garde.en_pause
    charge_cpu, memoire = (lecture or charge.lire)()
    if not garde.permet(charge_cpu, memoire):
        if pret_avant:
            interieur.noter(mem, "report", f"machine chargée (mémoire libre {memoire} %) : pensées et rêves attendent")
            print(f"[daemon] machine chargée (charge {charge_cpu}, mémoire libre {memoire} %) : "
                  "réflexion et rêve reportés")
        return
    if not pret_avant:
        print("[daemon] machine soulagée : réflexion et rêve reprennent")
    if dream_due(mem):
        etat["activite"] = "rêve"                    # pour le journal du temps (le battement le lit)
        try:
            dream(eng, mem)
        finally:
            etat.pop("activite", None)
    if interieur.ACTIF:
        motif = etat.pop("motif", None)
        inter = interieur.interrupteur()
        # en pause, ou motif d'avant une remise à zéro : jeté (relecture Opus : un motif en file pendant un rêve
        # partait quand même après une pause d'Ahmed)
        if motif and (not inter.get("actif", True) or motif.get("_ts", 0) < (inter.get("zero_ms") or 0) / 1000.0):
            interieur.noter(mem, "pensee_sautee", "l'interrupteur d'Ahmed : pensée en attente abandonnée")
            motif = None
        if motif and time.time() - motif.get("_ts", 0) < 3600:   # une pensée reportée de plus d'1 h est périmée
            etat["activite"] = "pense"
            try:
                penser(eng, mem, motif)
            finally:
                etat.pop("activite", None)
        else:
            # vie intérieure v2 (Jarvis, validé par Ahmed le 2026-10-17) : une attente utile
            import occupations
            import spontaneite
            occupations.peut_etre(eng, mem, etat)
            try:
                spontaneite.solliciter(mem)               # s'il a quelque chose de concret à lui dire (lot H, 28)
            except Exception as e:
                print("[daemon] spontanéité en échec :", e)
    elif time.time() - etat["last_reflect"] >= config.REFLECT_EVERY:
        reflect(eng, mem)
        etat["last_reflect"] = time.time()
    if interieur.ACTIF and interieur.interrupteur().get("actif", True):
        try:
            _ressenti_pass(mem)                    # le ressenti en réserve, pour la conscience (2026-10-20)
        except Exception as e:
            print("[daemon] ressenti en échec :", e)


# ---- Le ressenti en réserve (choix d'Ahmed, 2026-10-20 : « ressenti en réserve ») : Gemma lit les derniers échanges
# avec l'humeur du moment et sans, et garde les mots de SENSATION qui montent (jarvis/scanner.py) ; le cockpit les
# donne à Claude, sa conscience, comme une matière qu'il interprète lui-même (« au fond de nous on a une sensation
# grise, pesante et lourde, ou joviale, éclatante et vive, et c'est ensuite qu'on interprète l'émotion »).
# Calculé ici, quand le subconscient a la main (ni Claude au travail, ni le robot, machine pas surchargée) : pendant
# la conversation, rien à charger, rien à attendre. Une seule Gemma en mémoire : celle d'Ollama est déchargée
# avant (la version MLX, mêmes poids, sert au calcul). Au plus toutes les 20 min, et seulement si l'humeur ou les
# échanges ont changé.
RESSENTI = Path.home() / "AIOS" / "jarvis" / "ressenti.json"
RESSENTI_ECART_S = 20 * 60
JOURNAL_JARVIS = Path.home() / "AIOS" / "jarvis" / "journal.jsonl"


def _derniers_mots_d_ahmed(journal=None, n=4, maintenant=None):
    """(texte de ses n derniers messages des dernières 24 h, horodatage du dernier) ; ('', None) sinon."""
    maintenant = maintenant or time.time()
    try:
        with open(journal or JOURNAL_JARVIS, "rb") as f:
            f.seek(0, 2)
            debut = max(0, f.tell() - 400_000)
            f.seek(debut)
            lignes = f.read().decode("utf-8", "replace").splitlines()[1 if debut else 0:]   # la 1re ligne coupée
    except OSError:
        return "", None
    msgs = []
    for l in lignes:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if o.get("qui") == "ahmed" and str(o.get("texte", "")).strip() and maintenant - o.get("ts", 0) / 1000 < 86400:
            msgs.append(o)
    msgs = msgs[-n:]
    return (" … ".join(str(o["texte"])[:400] for o in msgs), msgs[-1]["ts"]) if msgs else ("", None)


def _ressenti_pass(mem, now=None, lancer=None, journal=None, sortie=None):
    now = now or time.time()
    sortie = Path(sortie or RESSENTI)
    try:
        humeur = (json.loads(mem.kv_get(interieur.CLE) or "{}") or {}).get("humeur")
    except ValueError:
        humeur = None
    if not humeur:
        return False
    contexte, dernier = _derniers_mots_d_ahmed(journal, maintenant=now)
    if not contexte:
        return False
    try:
        avant = json.loads(sortie.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        avant = {}
    if avant.get("humeur") == humeur and avant.get("dernier_ts") == dernier:
        return False                                   # rien de neuf à ressentir
    if now - float(avant.get("ts") or 0) < RESSENTI_ECART_S:
        return False
    if lancer is None:
        # (24/10, piste 3) le ressenti tourne sur la Gemma d'OLLAMA : on ne la décharge plus. Seul le repli MLX (moteur
        # « mlx ») en charge une deuxième : alors, et alors seulement, celle d'Ollama s'en va d'abord
        try:
            if os.environ.get("JARVIS_RESSENTI_MOTEUR", "ollama") == "ollama":
                raise StopIteration
            import urllib.request
            ps = json.loads(urllib.request.urlopen(f"{config.OLLAMA_HOST}/api/ps", timeout=3).read())
            for m in ps.get("models") or []:
                if "gemma" in str(m.get("name", "")).lower():
                    urllib.request.urlopen(urllib.request.Request(f"{config.OLLAMA_HOST}/api/generate", method="POST",
                        data=json.dumps({"model": m["name"], "keep_alive": 0}).encode(), headers={"Content-Type": "application/json"}), timeout=10)
        except (Exception, StopIteration):
            pass
        racine = Path(__file__).resolve().parent
        py = racine / "jarvis" / ".venv" / "bin" / "python"
        lancer = lambda q: subprocess.run([str(py), str(racine / "jarvis" / "scanner.py"), "--ressenti"], input=json.dumps(q),
                                          capture_output=True, text=True, timeout=400, cwd=str(racine / "jarvis"),
                                          env={**os.environ, "HF_HUB_OFFLINE": "1"})
    r = lancer({"humeur": humeur, "contexte": contexte, "dernier_ts": dernier, "sortie": str(sortie)})
    ok = getattr(r, "returncode", 1) == 0
    print(f"[daemon] ressenti ({humeur}) : " + ((r.stdout or "").strip().splitlines()[-1][:200] if ok and r.stdout else f"échec {(r.stderr or '')[-200:]}"))
    return ok


def _boucle_pass(mem, now=None):
    """(accord d'Ahmed, 2026-10-22) la nuit, une fois : la boucle de retour (niveau 1 minimal) NOTE ce qui a servi, ce qui
    a été raté et corrigé (boucle_retour.py) ; elle ne modifie rien de la mémoire."""
    now = time.time() if now is None else now
    if not interieur.nuit(now) or now - float(mem.kv_get("boucle_nuit_ts", "0") or 0) < 12 * 3600:
        return
    mem.kv_set("boucle_nuit_ts", str(now))
    try:
        import boucle_retour
        b = boucle_retour.nuit(mem, now)
        interieur.noter(mem, "boucle", f"nuit {b['nuit']} : {b['utilises']}/{b['proposes']} souvenirs proposés utilisés, "
                        f"{b['rates_hakim']} raté(s), {b['corrections']} correction(s) (rien n'est modifié)")
    except Exception as e:
        print("[daemon] boucle de retour en échec :", e)


def _sagesse_pass(mem, now=None):
    """(accord d'Ahmed, 2026-10-22) la nuit, une fois : un juge à l'aveugle relit les décisions de sagesse de Hakim et
    règle son paramètre (sagesse.py)."""
    now = time.time() if now is None else now
    if not interieur.nuit(now) or now - float(mem.kv_get("sagesse_nuit_ts", "0") or 0) < 12 * 3600:
        return
    mem.kv_set("sagesse_nuit_ts", str(now))
    try:
        import sagesse
        b = sagesse.juger_la_nuit(now)
        if b.get("juges"):
            interieur.noter(mem, "sagesse", f"le juge a relu {b['juges']} décision(s), {b.get('lisibles', 0)} lisible(s) dans tes mots ; "
                            f"ta sagesse : {b['sagesse']}")
    except Exception as e:
        print("[daemon] sagesse en échec :", e)


def _rappels_rates_pass(mem, now=None):
    """(accord d'Ahmed, 2026-10-22) la nuit, une fois : les souvenirs que le balayage automatique a ratés (notés par
    Hakim avec rappel_rate) reçoivent des alias tirés du message d'Ahmed (rappels_rates.py)."""
    now = time.time() if now is None else now
    if not interieur.nuit(now) or now - float(mem.kv_get("rappels_rates_nuit_ts", "0") or 0) < 12 * 3600:
        return
    mem.kv_set("rappels_rates_nuit_ts", str(now))
    try:
        import rappels_rates
        fait = rappels_rates.corriger(mem, now)
        if fait:
            interieur.noter(mem, "rappels_rates", f"{len(fait)} souvenir(s) raté(s) reçoivent des alias : "
                            + " ; ".join(f"#{e} {', '.join(m)}" for e, m in fait[:5]))
    except Exception as e:
        print("[daemon] souvenirs ratés en échec :", e)


def _index_fichiers_pass(mem, now=None):
    """L'index par le sens des fichiers d'Ahmed (lot E, point 43, 2026-10-19) : la nuit (0 h–7 h), une tranche
    de 15 min au plus, une fois par heure ; incrémental. Jamais pendant que Claude (la conscience) travaille."""
    now = time.time() if now is None else now
    if not interieur.nuit(now) or interieur.conscience_active():
        return
    if now - float(mem.kv_get("index_fichiers_ts", "0") or 0) < 3600:
        return
    mem.kv_set("index_fichiers_ts", str(now))
    try:
        import index_fichiers
        n = index_fichiers.indexer(budget_s=900)
        if n:
            interieur.noter(mem, "index_fichiers", f"{n} fichier(s) d'Ahmed indexé(s) par le sens")
    except Exception as e:
        print("[daemon] index des fichiers en échec :", e)


def battement_interieur(etat, arret=None, pas_s=15):
    """Le battement intérieur dans SON fil, avec SA connexion à la base (vu le 2026-10-16 : un rêve
    tenait la boucle principale ~50 min, le battement s'arrêtait, et Jarvis disait à juste titre
    « mon esprit de fond ne bat plus »). Sans modèle : il ne fait que l'état ; la pensée qu'il
    déclenche est faite par la boucle principale, quand Gemma est libre."""
    import threading
    arret = arret or threading.Event()
    mem_fil = Memory()
    while not arret.is_set():
        try:
            import chocs                                    # (2026-10-23) les reprises en main arrivées à échéance
            chocs.echeances(mem_fil)
        except Exception as e:
            print("[daemon] chocs : reprise en main en erreur :", e)
        try:
            interieur.tick(mem_fil, penser=lambda m: etat.__setitem__("motif", dict(m, _ts=time.time())),
                           activite=etat.get("activite"))
        except Exception as e:
            print("[daemon] battement intérieur en erreur :", e)
        arret.wait(pas_s)


def _rangement_nuit_pass(mem, now=None):
    """(2026-10-21) Le rangement de nuit (ranger_nuit.py) : les souvenirs vécus des 3 derniers jours restés sans rubrique
    ou rangés sans assurance sont lus par Claude et rangés au bon endroit. Une fois par nuit, vers 5 h."""
    now = now or time.time()
    h = time.localtime(now).tm_hour
    jour = time.strftime("%Y-%m-%d", time.localtime(now))
    if not (5 <= h < 7) or mem.kv_get("rangement_nuit_jour") == jour:
        return
    mem.kv_set("rangement_nuit_jour", jour)
    import subprocess
    racine = Path(__file__).resolve().parent
    try:
        r = subprocess.run([sys.executable, str(racine / "ranger_nuit.py"), "--oui"], cwd=str(racine), capture_output=True,
                           text=True, timeout=1200)
        print("[daemon] rangement de nuit : " + ((r.stdout or r.stderr or "").strip().splitlines() or ["?"])[-1][:200])
    except Exception as e:
        print("[daemon] rangement de nuit impossible :", e)


def _tests_de_nuit_pass(mem, now=None):
    """La batterie fixe rejouée chaque nuit (lot G, point 41) : la suite de tests d'Anamnèse et le banc des
    souvenirs périmés (eval/supersession_bench.py, sans modèle de langage). Une fois par nuit, vers 3 h 30 ;
    résultat dans data/nuit-tests.jsonl (vu par l'introspection et le bilan de la semaine)."""
    now = now or time.time()
    h = time.localtime(now).tm_hour
    jour = time.strftime("%Y-%m-%d", time.localtime(now))
    if not (3 <= h < 6) or mem.kv_get("tests_de_nuit_jour") == jour:
        return
    mem.kv_set("tests_de_nuit_jour", jour)
    import subprocess
    racine = Path(__file__).resolve().parent
    env = {**os.environ, "HF_HUB_OFFLINE": "1"}
    res = {"ts": now, "jour": jour}
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=str(racine), env=env,
                           capture_output=True, text=True, timeout=1200)
        res["ok"] = r.returncode == 0
        res["tests"] = (r.stdout.strip().splitlines() or [""])[-1][:200]
    except Exception as e:
        res["ok"], res["tests"] = False, f"{type(e).__name__}: {e}"[:200]
    try:
        r = subprocess.run([sys.executable, "eval/supersession_bench.py", "--rigoureux"], cwd=str(racine), env=env,
                           capture_output=True, text=True, timeout=600)
        res["perimes"] = "\n".join(r.stdout.strip().splitlines()[-4:])[:600]
    except Exception as e:
        res["perimes"] = f"{type(e).__name__}: {e}"[:200]
    # la batterie fixe sur Hakim lui-même (demande de Hakim, 2026-10-20, accord d'Ahmed) : introspection honnête,
    # style street / propre, corrections honnêtes, ne pas inventer — sa vraie persona, un juge Opus (eval/batterie_hakim.py)
    try:
        r = subprocess.run([sys.executable, "eval/batterie_hakim.py"], cwd=str(racine), env=env, capture_output=True,
                           text=True, timeout=1800, stdin=subprocess.DEVNULL)
        res["batterie"] = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:
        res["batterie"] = {"erreur": f"{type(e).__name__}: {e}"[:200]}
    with open(config.DATA_DIR / "nuit-tests.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
    b = res.get("batterie") or {}
    print(f"[daemon] tests de nuit : {'verts' if res['ok'] else 'EN ÉCHEC'} — {res['tests']}"
          + (f" ; batterie de Hakim {b['reussis']}/{b['total']}" if "reussis" in b else ""))


def _audit_dependances_pass(mem, now=None, auditer=None, signaler=None):
    """Le scan des dépendances, une fois par semaine, la nuit (4 h–6 h) : audit_dependances.py (proposé par Hakim,
    validé par Ahmed le 2026-10-20). Une faille : notification et courrier à Hakim ; rien n'est mis à jour seul."""
    now = now or time.time()
    if not (4 <= time.localtime(now).tm_hour < 6):
        return
    dernier = float(mem.kv_get("audit_dependances_ts", "0") or 0)
    if now - dernier < 7 * 24 * 3600 - 3600:
        return
    mem.kv_set("audit_dependances_ts", str(now))
    import audit_dependances as A
    try:
        res = (auditer or A.auditer)()
        (signaler or A.signaler)(res)
        print(f"[daemon] audit des dépendances : {res['failles']} faille(s)" + (f", audit impossible : {res['erreurs']}" if res["erreurs"] else ""))
    except Exception as e:
        print("[daemon] audit des dépendances impossible :", e)


def _echanges_pass(mem):
    """Chaque échange avec Ahmed, mémorisé automatiquement et encré selon l'attention (echanges.py). Léger :
    pas de modèle de langage ; jamais bloquant pour le reste du démon."""
    try:
        import echanges
        n = echanges.passage(mem)
        if n:
            print(f"[daemon] {n} échange(s) mémorisé(s)")
        if echanges.ECHECS_VERROU >= 3:                 # (2026-10-21) la connexion reste verrouillée : on la rouvre
            mem.reconnecter()
            echanges.ECHECS_VERROU = 0
            print("[daemon] base verrouillée trois passages de suite : connexion rouverte")
    except Exception as e:
        print("[daemon] mémorisation des échanges impossible :", e)


def main():
    mem = Memory()
    eng = Engine(chat_model=config.DAEMON_MODEL)
    mem.kv_set("daemon_started", str(time.time()))
    if mem.kv_get("last_dream") is None:   # 1er boot : ne pas rêver sur de vieux épisodes pré-existants
        mem.kv_set("last_dream", str(time.time()))
    # Pas de message de réveil codé en dur : la 1re réflexion (ci-dessous) produira
    # une pensée spontanée, et notifiera seulement si le modèle en ressent l'envie.
    print(f"[daemon] Anamnèse éveillée — réflexion toutes les {config.REFLECT_EVERY}s, "
          f"sommeil après {config.DREAM_IDLE_TRIGGER}s d'inactivité. (Ctrl-C pour arrêter)")
    etat = {"last_reflect": 0.0}
    if interieur.ACTIF:
        import threading
        threading.Thread(target=battement_interieur, args=(etat,), daemon=True, name="battement").start()
    garde = charge.GardeCharge()
    last_brain_proj = 0.0
    last_backup_check = 0.0
    while True:
        try:
            # NREM (faits durables) : délégué à CLAUDE CODE (consolidate.py, launchd) —
            # décision 2026-06-23. REM local RECÂBLÉ le 2026-07-03 (expérience-rêve,
            # spec docs/superpowers/specs/2026-07-03-experience-reve-design.md) :
            # rêve réel + jumeau fantôme, kill-switch config.DREAM_LAB_ENABLED.
            _travaux_llm(eng, mem, etat, garde)     # pas de modèle chargé quand la machine est surchargée
            if time.time() - last_brain_proj >= config.BRAIN_PROJ_EVERY:
                _brain_projection_pass(mem)        # cerveau 3D tenu à jour (near-temps réel)
                last_brain_proj = time.time()
            if time.time() - last_backup_check >= config.BACKUP_CHECK_EVERY:
                _backup_pass(mem)                  # backup quotidien WAL-safe (rotation)
                last_backup_check = time.time()
            _index_fichiers_pass(mem)              # l'index par le sens des fichiers d'Ahmed (la nuit)
            _rappels_rates_pass(mem)               # les souvenirs ratés deviennent des alias (la nuit)
            _sagesse_pass(mem)                     # le juge de la sagesse (la nuit)
            _boucle_pass(mem)                      # la boucle de retour, niveau 1 : elle note seulement (la nuit)
            _echanges_pass(mem)                    # chaque échange avec Ahmed devient un souvenir (2026-10-20)
            _tests_de_nuit_pass(mem)               # la batterie fixe, rejouée chaque nuit (lot G, 41)
            _rangement_nuit_pass(mem)              # les souvenirs mal rangés, lus et rangés (2026-10-21)
            _audit_dependances_pass(mem)           # les failles connues des dépendances, chaque semaine
            time.sleep(config.DAEMON_TICK)
        except KeyboardInterrupt:
            print("\n[daemon] endormissement.")
            break
        except Exception as e:
            print("[daemon] erreur:", e)
            time.sleep(config.DAEMON_TICK)


if __name__ == "__main__":
    main()
