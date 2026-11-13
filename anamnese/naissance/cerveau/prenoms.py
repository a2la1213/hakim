"""Des PRÉNOMS courants (français, maghrébins, arabes, africains, européens, anglais) : pour reconnaître un nom de personne
dans un texte (filtre d'identité de la naissance, vérification de l'héritage). Une liste n'est jamais complète : un
prénom rare peut passer ; c'est pourquoi la relecture humaine reste la dernière garde. (Les prénoms que la publication
publique retire ne sont pas ici : ce fichier est publié ; l'héritage les lit à l'exécution dans les règles privées.)
"""
import unicodedata

_LISTE = """
aaron abdel abdallah abdelkader abdelaziz abdou abdoulaye abel abigail achille adam adama adel adele adelaide adem adil
adnane adrien agathe agnes ahmed aicha aida aiden aimee aissa aissatou akim alain alan alba alban albert alessandro alex
alexandra alexandre alexia alexis alfred ali alice alicia aline alix allan alma amadou amal amandine amani amara amaury
ambre ambroise amel amelia amelie amina amine amir amira amandine anais anastasia andre andrea andreas ange angela angele
angelina angelique anis anissa anna annabelle anne annie anouk anselme anthony antoine antonin antonio apolline ariane
arnaud arthur assia astrid aude audrey augustin aurele aurelie aurelien aurore axel axelle aya ayman aymen ayoub aziz
bachir badr baptiste barbara basile bastien beatrice belinda ben benjamin benoit bernard berenice bertrand bilal blanche
boris brahim brigitte bruno camelia camille capucine carla carine carmen caroline cassandra catherine cecile cedric celia
celine charles charlie charlotte chiara chloe christelle christian christine christophe claire clara clarisse claude
clement clementine clemence colette coline constance corentin cyril cyrine dalia damien dan dani daniel daniela danielle
david deborah delphine denis diane didier dimitri dina djamel djibril dominique dorian dounia driss dylan edgar
edith edouard eleonore eli elias elie eliot eliott elisa elise elodie eloise elsa emeline emile emilie emilien emma
emmanuel emmanuelle enzo eric erwan esteban estelle ethan etienne eugene eugenie eva eve evan fabien fabienne fabrice
fadi fadila farah farid faris fatima fatou fatoumata faustine felix ferdinand fernand flavie flavien flora florence
florent florian francis franck francois francoise frederic gabin gabriel gabriella gabrielle gael gaelle garance gaspard
gauthier genevieve georges gerald gerard ghislain gilbert gilles gisele guillaume gustave guy habib hadrien hafid hafsa
hakim halima hamid hamza hana hanane hannah harry hassan hatem hector helena helene henri hicham hind hortense hugo
hugues ibrahim ichem idir idris idriss ilan ilyas ilyes imane imen ines ingrid irene iris isaac isabelle ismael israa
issa ivan jacqueline jacques jade jamal jamila jean jeanne jennifer jeremie jeremy jessica jibril joachim joel johan
johanna jonas jonathan jordan joseph josephine josiane jules julia julie julien juliette justine kader kamel kamila karim
karima karine kateb katia kaymin kelly kenza kevin khadija khaled khalil kylian laetitia lamia lana lara laura laure
laurence laurent lea leandre leila lena leo leon leonard leonie lilia lilou lina linda lionel lisa loic lola lorenzo
louane louis louisa louise luc luca lucas lucie lucien lucile ludovic luna lydia lyna lynda madeleine mael maelle
magali mahdi mahmoud maissa malak malek malik malika manon marc marcel margaux margot maria mariam marie marine marion
mark marlene marouane martin martine marwa marwan mathieu mathilde mathis matteo matthieu maud maureen maurice max
maxence maxime mehdi melanie melissa meriem michel michele mickael mila milan mohamed mohammed mona morgane moussa mounir
mourad muriel myriam nabil nadia nadine nadir naim naima najat nassim natacha nathalie nathan nawel nazim nicolas nina
noah noam noe noel noemie nora nordine nour nourdine octave odile olga olivia olivier omar oscar oumar ousmane pablo
pascal pascale patricia patrick paul paula pauline perrine philippe pierre quentin rachel rachid rafael rafik rania
raphael raphaelle rayan redouane regis remi renaud rene richard rim rita robert robin rodolphe romain romane romeo
rose rosalie roxane ruben ryan sabine sabrina sacha safia safiya salim salima salma salome samantha sami samia samir
samira samuel samy sandra sandrine sara sarah selim selma serge severine sheila sofia sofiane solene sonia sophie
soraya stephane stephanie sylvain sylvie tarek tahar theo theodore therese thibault thierry thomas tiphaine timothee
tom tony tristan ulysse valentin valentine valerie vanessa victor victoria vincent violette virginie walid wassim
william xavier yacine yanis yann yannick yasmina yassine yazid yohan youcef younes youssef yves yvette yvonne
zahra zakaria zineb zohra zoe
"""
PRENOMS = frozenset(_LISTE.split())


def _sans_accents(t):
    return "".join(c for c in unicodedata.normalize("NFD", str(t)) if unicodedata.category(c) != "Mn").casefold()


def est_prenom(mot):
    return _sans_accents(mot) in PRENOMS


# des prénoms qui sont aussi des mots du métier ou de la langue (« une robe rose », « bleu marine », « pierre précieuse ») :
# le filtre ne les masque que s'ils sont écrits avec leur majuscule de nom propre
AMBIGUS = frozenset("rose marine claire ambre jade violette blanche iris aurore ange capucine constance pierre romane noel "
                    "flore olive perle prune fleur".split())


def est_ambigu(mot):
    return _sans_accents(mot) in AMBIGUS
