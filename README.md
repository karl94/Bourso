# BRVM Mon Portefeuille

Application personnelle de suivi de portefeuille BRVM : collecte quotidienne des cours, signaux d'achat et de vente, veille et alertes Telegram. Coût : 0 € par mois.

**État : sprint 2 (collecte) prêt.** Les écrans de l'application arriveront au sprint 4.

## Ce que fait ce dépôt aujourd'hui

Chaque jour de bourse à 18 h 05 (heure d'Abidjan), GitHub lance automatiquement la collecte :

1. lecture du tableau des cours sur brvm.org ;
2. si la page est vide ou incomplète, lecture du Bulletin Officiel de la Cote (PDF) en secours ;
3. contrôle de cohérence (cours nul, variation au-delà de ±7,5 %, titre manquant) ;
4. enregistrement dans votre base Supabase ;
5. message Telegram : nombre de titres lus, cours de vos titres, anomalies éventuelles.

Une sauvegarde CSV de toute la base est faite chaque samedi.

## Installation (environ 30 minutes, une seule fois)

### 1. Supabase : la base de données

1. Créez un compte sur [supabase.com](https://supabase.com), puis **New project**. Nom : `brvm-portefeuille`, région : la plus proche (Europe). Notez le mot de passe proposé.
2. Menu **SQL Editor** > **New query** : collez tout le contenu de `supabase/schema.sql`, puis **Run**. Le message « Success » doit s'afficher.
3. Menu **Authentication** > **Sign In / Providers** : désactivez **Allow new users to sign up**. Vous serez le seul utilisateur.
4. Menu **Project Settings** > **API** : copiez
   - **Project URL** → ce sera `SUPABASE_URL` ;
   - la clé **service_role** (bouton Reveal) → ce sera `SUPABASE_SERVICE_KEY`. Elle donne un accès total : ne la partagez jamais et ne la collez jamais dans le code.

### 2. Telegram : le bot d'alertes

1. Dans Telegram, ouvrez **@BotFather**, envoyez `/newbot`, choisissez un nom (ex. « BRVM Alertes ») et un identifiant finissant par `bot`.
2. BotFather vous donne un **jeton** → ce sera `TELEGRAM_TOKEN`.
3. Ouvrez votre nouveau bot et envoyez-lui « bonjour ».
4. Ouvrez dans un navigateur `https://api.telegram.org/bot<VOTRE_JETON>/getUpdates` : le nombre après `"chat":{"id":` → ce sera `TELEGRAM_CHAT_ID`.

### 3. GitHub : l'automatisation

1. Dans ce dépôt : **Settings** > **Secrets and variables** > **Actions** > **New repository secret**. Créez les 4 secrets :
   `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`.
2. Onglet **Actions** : si GitHub le demande, cliquez sur **I understand my workflows, enable them**.

### 4. Premier essai

1. **Actions** > **Essai de collecte (sans écriture)** > **Run workflow**. Il lit brvm.org et affiche ce qui serait enregistré, sans rien écrire. Le journal doit lister environ 47 titres avec leur cours.
2. Si c'est bon : **Actions** > **Collecte quotidienne BRVM** > **Run workflow**. Vous devez recevoir le message Telegram, et la table `cours_journaliers` se remplit dans Supabase (menu **Table Editor**).

Ensuite, plus rien à faire : la collecte tourne seule chaque soir de semaine.

### 5. Importer votre portefeuille

1. Copiez `donnees/modele_transactions.csv` et remplacez les lignes d'exemple par vos transactions réelles : une ligne par achat ou vente.
2. Colonnes : `code_titre` (symbole BRVM, ex. `SOGC` pour SOGB, `PALC` pour Palm CI, `SNTS` pour Sonatel, `UNXC` pour Uniwax, `SICC` pour Sicable, `STBC` pour Sitab, `SIBC` pour SIB, `BOABF` pour BOA-BF), `date` (AAAA-MM-JJ), `sens` (achat ou vente), `quantite`, `cours`, `frais`, `poche` (dividendes ou swing), `note`.
3. Le plus simple : dans Supabase, **Table Editor** > `transactions` > **Insert** > **Import data from CSV**. Supprimez d'abord la colonne `note` si elle est vide partout.
   Ou, sur un ordinateur : `python scripts/import_csv.py donnees/mes_transactions.csv` (vérifie le fichier ligne par ligne avant l'envoi ; ajoutez `--essai` pour vérifier sans envoyer).
4. La vue `positions` de Supabase calcule alors vos quantités, prix de revient, valeurs et plus-values.

## Si quelque chose ne marche pas

| Symptôme | Cause probable | Que faire |
| --- | --- | --- |
| Message « Collecte BRVM en échec » | brvm.org indisponible ou page modifiée | Relancer plus tard ; si cela persiste, lancer l'essai et transmettre le fichier `page-brvm` (onglet Actions > l'exécution > Artifacts) pour adapter le parseur |
| « ⚠️ cours à vérifier » | Variation anormale ou source de secours | Comparer avec Sika Finance ; aucun signal n'est calculé sur ces cours |
| Pas de message un jour de semaine | Jour férié (statut « pas_de_seance ») ou secrets Telegram erronés | Voir la table `collectes` dans Supabase |
| Supabase « paused » | 7 jours sans activité | Bouton **Restore** ; la collecte quotidienne évite normalement la pause |

## Organisation du code

```
collecte/            script Python de collecte
  brvm.py            lecture de la page des cours (colonnes repérées par mots-clés)
  boc.py             lecture du BOC en PDF (secours)
  controle.py        contrôle de cohérence
  stockage.py        écriture dans Supabase (API REST)
  telegram.py        envoi des messages
  main.py            enchaînement ; option --essai pour ne rien écrire
  tests/             tests automatiques (page simulée)
supabase/schema.sql  tables, vues positions et dernier_cours, sécurité
scripts/             import CSV, sauvegarde, identifiant Telegram
.github/workflows/   collecte quotidienne, essai, sauvegarde hebdomadaire
donnees/             modèle de fichier de transactions
```

## Usage

Usage strictement personnel. Les données collectées ne sont pas republiées. Une seule lecture par jour, avec un identifiant explicite.
