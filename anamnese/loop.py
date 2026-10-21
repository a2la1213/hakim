"""Anamnèse — Phase 1 : « Il se souvient » (+ fondations d'auto-évolution).

Boucle : récupère les souvenirs saillants (sparse) -> contexte -> moteur -> stocke.

Commandes (tape-les comme un message) :
  /aide                  cette aide
  /memoire               nombre de souvenirs
  /modules               liste les modules chargés
  /run <module> <arg>    exécute un module
  /skills                liste les compétences apprises
  /skill <nom>           affiche une compétence
  /evolve <description>  l'IA génère un NOUVEAU module -> modules/proposed/ (revue requise)
  /promote <nom>         promeut un module proposé (après ta revue) -> actif au prochain lancement
  /quitter
"""
import sys
import time

import config
import embeddings
from engine import Engine
from memory import Memory
from modules.registry import load_modules

SYSTEM_PROMPT = config.PERSONA + (
    "\nQuand des « Souvenirs pertinents » te sont fournis, sers-t'en pour assurer "
    "la continuité avec le passé. Sois concise et utile."
)


def build_messages(memories, user_input):
    sys_prompt = SYSTEM_PROMPT
    if memories:
        block = "\n".join(
            f"- [{time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))}] {role}: {content}"
            for _s, ts, role, content, _p in memories
        )
        sys_prompt += "\n\nSouvenirs pertinents :\n" + block
    return [{"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_input}]


def evolve(description, eng):
    """L'IA propose un nouveau module. GARDE-FOU : écrit dans proposed/, inactif."""
    if not description:
        print("Usage : /evolve <description de la capacité>")
        return
    print("🧬 Génération d'un module...")
    prompt = (
        "Tu écris un module Python pour le système Anamnèse. Le module DOIT : "
        "sous-classer `Module` (importé via `from modules.registry import Module`), "
        "définir `name` (court, snake_case), `description`, et une méthode "
        "`run(self, arg, context)` qui retourne une chaîne. Réponds UNIQUEMENT "
        "avec le code Python, sans texte autour.\n\nCapacité demandée : " + description
    )
    code = eng.chat([{"role": "user", "content": prompt}], stream=False).strip()
    if code.startswith("```"):
        code = code.split("```")[1]
        if code.lstrip().startswith("python"):
            code = code.lstrip()[len("python"):]
        code = code.strip()
    safe = "".join(c if c.isalnum() else "_" for c in description.lower())[:30].strip("_") or "module"
    config.PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    path = config.PROPOSED_DIR / f"{safe}.py"
    path.write_text(code, encoding="utf-8")
    print(f"\n✅ Module proposé écrit dans : {path}")
    print(f"   ⚠️  REVOIS-le, puis : /promote {safe}")


def promote(name):
    """Promeut un module proposé -> actif. GARDE-FOU : action humaine explicite."""
    if not name:
        print("Usage : /promote <nom_du_fichier_sans_.py>")
        return
    src = config.PROPOSED_DIR / f"{name}.py"
    if not src.exists():
        print(f"❌ introuvable : {src}")
        return
    dst = config.MODULES_DIR / f"{name}.py"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"✅ Promu : {dst.name}. Actif au prochain lancement.")
    print(f"   💡 Versionne pour pouvoir revenir en arrière : "
          f"git add -A && git commit -m 'evolve: {name}'")


def handle_command(cmd, eng, mem, modules):
    """Retourne 'quit' pour sortir, sinon None."""
    parts = cmd.split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if name in ("/aide", "/help"):
        print(__doc__)
    elif name == "/memoire":
        print(f"🧠 {mem.count()} souvenirs.")
    elif name == "/modules":
        if not modules:
            print("(aucun module actif)")
        for m in modules.values():
            print(f"  • {m.name} — {m.description}")
    elif name == "/run":
        mp = arg.split(maxsplit=1)
        mname = mp[0] if mp else ""
        marg = mp[1] if len(mp) > 1 else ""
        if mname in modules:
            print(modules[mname].run(marg, {"engine": eng, "memory": mem}))
        else:
            print(f"❌ module inconnu : {mname}")
    elif name == "/skills":
        skills = mem.list_skills()
        if not skills:
            print("(aucune compétence apprise)")
        for sn, sd in skills:
            print(f"  • {sn} — {sd}")
    elif name == "/skill":
        s = mem.get_skill(arg)
        print(f"{s[0]} : {s[1]}\n\n{s[2]}" if s else f"❌ compétence inconnue : {arg}")
    elif name == "/evolve":
        evolve(arg, eng)
    elif name == "/promote":
        promote(arg)
    elif name in ("/quitter", "/quit", "/exit"):
        return "quit"
    else:
        print(f"❓ commande inconnue : {name}  (tape /aide)")
    return None


def main():
    eng = Engine()
    if not eng.health():
        print("❌ Ollama ne répond pas.\n"
              "   1) Démarre le serveur :  ollama serve   (ou ouvre l'app Ollama)\n"
              "   2) Récupère les modèles :\n"
              f"        ollama pull {config.CHAT_MODEL}\n"
              f"        ollama pull {config.EMBED_MODEL}")
        sys.exit(1)
    mem = Memory()
    modules = load_modules(config.MODULES_DIR)
    print(f"🧠 Anamnèse — {mem.count()} souvenirs, {len(modules)} module(s). "
          "Tape /aide, ou parle-moi. (/quitter pour sortir)\n")
    while True:
        try:
            user_input = input("👤 ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n💤 À bientôt.")
            break
        if not user_input:
            continue
        if user_input.startswith("/"):
            if handle_command(user_input, eng, mem, modules) == "quit":
                print("💤 À bientôt.")
                break
            continue
        now = time.time()
        q_emb = embeddings.embed(user_input)
        memories = mem.retrieve(user_input, q_emb, now)
        if memories:
            print(f"   💭 ({len(memories)} souvenir(s) rappelé(s))")
        print("🤖 ", end="")
        reply = eng.chat(build_messages(memories, user_input))
        mem.add("user", user_input,
                importance=eng.rate_importance(user_input), embedding=q_emb)
        mem.add("assistant", reply, importance=0.5, embedding=embeddings.embed(reply))


if __name__ == "__main__":
    main()
