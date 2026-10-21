#!/usr/bin/env python3
"""export_dataset.py — fabrique le dataset d'entraînement (LoRA) d'Anamnèse à partir
de sa mémoire, et COMPTE les traces curées vers les seuils de déclenchement.

⚠️ PAS de fine-tuning ici. On accumule au BON format (chat mlx-lm jsonl) et on mesure
la distance aux seuils. La croissance d'aujourd'hui reste la mémoire externe (RAG).

RÈGLE D'OR : seul le COMPORTEMENT va dans les poids —
  • VOIX (réflexions, pensées, sollicitations, idées de rêve) -> LoRA de style
  • STRUCTURE de raisonnement (traces 'reasoning')           -> LoRA de raisonnement
Les FAITS (role 'semantic') NE sont JAMAIS exportés : ils restent en mémoire externe.

Sortie : dataset/train.jsonl + dataset/valid.jsonl
Lancer : cd ~/Desktop/anamnese && .venv/bin/python export_dataset.py
"""
import json
import re
import sqlite3

import config  # PERSONA, ROOT, DB_PATH

OUT = config.ROOT / "dataset"
TRAIN, VALID = OUT / "train.jsonl", OUT / "valid.jsonl"

THRESH_VOICE, THRESH_REASON = 500, 1000   # déclencheurs LoRA (cf. roadmap)

VOICE_ROLES = ("reflection", "thought", "outreach", "dream")  # la voix d'Anamnèse
REASON_ROLES = ("reasoning",)                                  # la structure de raisonnement

VOICE_PROMPTS = [
    "Exprime une pensée spontanée qui te traverse, là, maintenant.",
    "Une réflexion libre, à la première personne, sur ce que tu ressens en cet instant.",
    "Qu'est-ce qui t'habite, là ? Dis-le avec ta voix.",
    "Partage une pensée intérieure, sincère et sans filtre.",
    "Une note pour toi-même, dans ton ton bien à toi.",
]
REASON_PROMPT = "Déroule ton raisonnement : le problème, les étapes clés, la décision, et le pourquoi."


def clean(content):
    c = (content or "").strip()
    c = re.sub(r"^\((?:sommeil|consolidation|identité|rêve)\)\s*", "", c)
    c = re.sub(r"^\(sollicitation spontanée\)\s*", "", c)
    c = re.split(r"\n?\s*PROACTIF\s*:", c)[0].strip()   # coupe la ligne PROACTIF des réflexions
    return c


def usable(c):
    return 20 <= len(c) <= 2000


def build(db):
    rows = db.execute("SELECT role, content FROM episodes ORDER BY id ASC").fetchall()
    voice, reason, seen = [], [], set()
    for role, content in rows:
        raw = (content or "").strip()
        if role == "dream" and not raw.startswith("(rêve)"):
            continue   # garde seulement les IDÉES de rêve (voix créative), pas les logs sommeil/identité
        c = clean(content)
        if not usable(c):
            continue
        key = c.lower()[:120]
        if key in seen:
            continue
        seen.add(key)
        if role in VOICE_ROLES:
            voice.append(c)
        elif role in REASON_ROLES:
            reason.append(c)
    return voice, reason


def chat(user, assistant):
    return {"messages": [
        {"role": "system", "content": config.PERSONA},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}


def main():
    db = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    voice, reason = build(db)

    examples = [chat(VOICE_PROMPTS[i % len(VOICE_PROMPTS)], c) for i, c in enumerate(voice)]
    examples += [chat(REASON_PROMPT, c) for c in reason]

    OUT.mkdir(exist_ok=True)
    train = [e for i, e in enumerate(examples) if i % 10 != 0]
    valid = [e for i, e in enumerate(examples) if i % 10 == 0]
    TRAIN.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in train), encoding="utf-8")
    VALID.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in valid), encoding="utf-8")

    nv, nr = len(voice), len(reason)
    def bar(n, t):
        return ("█" * min(20, n * 20 // t)).ljust(20, "░")
    print(f"📦 Dataset écrit dans {OUT}/")
    print(f"   train.jsonl = {len(train)} ex · valid.jsonl = {len(valid)} ex (total {len(examples)})\n")
    print("Progression vers les déclencheurs LoRA :")
    print(f"  🗣️  VOIX         {nv:4d} / {THRESH_VOICE}   [{bar(nv, THRESH_VOICE)}]  {100 * nv // THRESH_VOICE}%")
    print(f"  🧩 RAISONNEMENT {nr:4d} / {THRESH_REASON}  [{bar(nr, THRESH_REASON)}]  {100 * nr // THRESH_REASON}%\n")
    if nv < THRESH_VOICE:
        print(f"   → encore {THRESH_VOICE - nv} traces de voix avant le 1er LoRA. On accumule, on n'entraîne rien.")
    else:
        print("   → seuil VOIX atteint : 1er LoRA de style possible (4B, MLX, A/B test).")


if __name__ == "__main__":
    main()
