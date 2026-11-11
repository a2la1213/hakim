#!/bin/bash
# (11/11) les voix de synthèse du banc du retour du micro (mesure/retour-micro-banc.js, mesure/retour-spectre-banc.js) : le live (cinq voix de say)
# et papa (deux autres), en WAV 16 kHz mono. Usage : bash mesure/retour-micro-voix.sh <dossier>   puis   BANC_VOIX=<dossier> node mesure/retour-spectre-banc.js
B="${1:?le dossier des voix}"
mkdir -p "$B"
i=0
for v in "Thomas" "Jacques" "Amélie" "Flo (Français (France))" "Sandy (Français (France))"; do
  for ph in "Salam à tous, bienvenue dans le live, on parle de la langue ce soir." "Est-ce que tu as cherché le vrai sens de ce mot dans le dictionnaire ?" \
            "Moi je pense que c'est la vérité, regarde dans la même réflexion que toi." "Il faut voyager, il faut rencontrer des gens pour apprendre vraiment." \
            "Hakim, tu m'entends ? Dis-nous ce que tu en penses, toi." "Non mais attends, laisse-moi finir ma phrase avant de répondre." \
            "C'est une question de traduction, pas une question de religion." "On revient demain soir, même heure, n'oubliez pas de partager le live."; do
    i=$((i+1)); say -v "$v" -o "$B/live-$i.wav" --file-format=WAVE --data-format=LEI16@16000 "$ph"
  done
done
j=0
for ph in "Fiston, tu m'entends ou pas ? Je te parle à toi, là." "Attends, je vais leur répondre, laisse-moi deux secondes." \
          "Non, ça c'est faux, regarde bien ce qu'il dit dans le texte." "Ok, on change de sujet, parle-nous de ta musique maintenant." \
          "Hakim, coupe le son du live et écoute-moi bien." "Je suis là avec vous, merci pour vos messages, vraiment." \
          "Tu peux me chercher la source de ce verset s'il te plaît ?" "Bon, on fait une petite pause et on revient tout de suite." \
          "C'est mon fils, il apprend tous les jours, il entend tout." "Vas-y, balance une punchline au live, fais-les rire un peu."; do
  j=$((j+1))
  say -v "Eddy (Français (France))" -o "$B/papa-$j.wav" --file-format=WAVE --data-format=LEI16@16000 "$ph"
  say -v "Grandpa (Français (France))" -o "$B/papa2-$j.wav" --file-format=WAVE --data-format=LEI16@16000 "$ph"
done
ls "$B" | wc -l
