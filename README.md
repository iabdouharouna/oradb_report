# dbreport — Rapport standard du parc Oracle

Outil en ligne de commande qui produit un **rapport standard « 360° »** des bases
Oracle de production d'une organisation : inventaire, capacité, objets, santé,
sécurité/conformité et sauvegarde/DR.

La collecte est strictement en **lecture seule** (aucun DDL/DML) et s'appuie sur
`python-oracledb` en mode *thin* — **aucune dépendance à SQL\*Plus**.

## 1. Prérequis

- Python **≥ 3.11**.
- Un **compte de collecte** par base, disposant de préférence des privilèges
  `SELECT_CATALOG_ROLE` (accès `DBA_*` et `V$*`). En l'absence de certains
  privilèges ou de packs optionnels (Diagnostics/ASM…), les sections concernées
  passent en `PARTIEL` sans faire échouer la collecte.

## 2. Démarrage rapide

```bash
cp .env.example .env          # renseigner les mots de passe (ORAREPORT_<NOM>_PASSWORD)
python setup_project.py check     # teste les connexions du parc
python setup_project.py collect   # produit un snapshot horodaté
python setup_project.py report    # génère les rapports (md + html + csv + xlsx)
python setup_project.py run       # enchaîne collect + report
```

Le premier appel crée `.venv/`, installe les dépendances (`oracledb`, `Jinja2`,
`openpyxl`) et se ré-exécute automatiquement dans l'environnement virtuel.

> Auto-test hors base : `python tools/selftest.py` valide l'inventaire, le modèle
> et la génération des rapports sans se connecter à aucune base.

## 3. Configuration

### 3.1. Inventaire du parc — `databases.yaml`

```yaml
databases:
  - name: ORCL_PROD
    dsn: orcl-prod.intra:1521/ORCLPDB1
    user: DBA_REPORT
    environment: prod
    service: primary
    tags: [erp, sao-paulo]
```

Champs : `name` (identifiant logique), `dsn` (Easy Connect), `user` (compte de
collecte), `password` (déconseillé ici), `role` (`SYSDBA`/`SYSOPER`), `environment`,
`service` (`primary`/`standby`), `tags` (filtres libres).

L'inventaire est lu **sans dépendance obligatoire** : un parseur stdlib traite le
sous-ensemble YAML ci-dessus (et accepte aussi un contenu JSON) ; si `PyYAML` est
installé, il est utilisé à la place pour un YAML complet.

### 3.2. `.env`

Les mots de passe sont de préférence fournis par variable d'environnement
`ORAREPORT_<NOM_DE_LA_BASE>_PASSWORD` (nom mis en majuscules). Autres options :
`ORAREPORT_INVENTORY`, `ORAREPORT_OUTPUT_DIR`, `ORAREPORT_CALL_TIMEOUT`,
`ORAREPORT_SECTIONS`, `ORAREPORT_LOG_FILE`, `ORAREPORT_VENV`, `ORAREPORT_ENV_FILE`.

## 4. Commandes

| Commande | Rôle |
|----------|------|
| `check` | Teste chaque connexion et affiche version / utilisateur / conteneur |
| `collect` | Interroge le parc et écrit un snapshot horodaté (`output/<horodatage>/snapshot.json`) |
| `report` | Génère les rapports depuis un snapshot (le plus récent par défaut) |
| `run` | Enchaîne `collect` puis `report` |

Options communes : `--names`, `--tags`, `--sections`, `--dry-run`.
`report`/`run` : `--snapshot`, `--format md|html|csv|xlsx|all`.
Globales : `--inventory`, `--env-file`, `-v`/`-vv`, `--version`.

Exemples :

```bash
python setup_project.py collect --tags prod --sections identity,capacity
python setup_project.py report --format html
python setup_project.py run --names ORCL_PROD
```

## 5. Sections du rapport

| Section | Contenu |
|---------|---------|
| `identity` | Nom/DBID, instance, hôte, version/édition, rôle (primary/standby), mode archive, CDB/PDB, démarrage |
| `capacity` | Taille base, tablespaces (utilisé/libre/%/autoextend), datafiles/tempfiles, redo logs, control files, FRA, groupes ASM |
| `objects` | Compteurs par type, objets invalides, statistiques obsolètes, top segments, jobs `DBMS_SCHEDULER` en échec |
| `health` | SGA/PGA, paramètres clés, top attentes, licences (`v$option`), disponibilité AWR |
| `security` | Comptes (ouverts/verrouillés/expirés), rôles d'admin, utilisateurs privilégiés, profils, audit, historique de patchs |
| `backup` | Jobs RMAN et ancienneté de la dernière sauvegarde, jobs Datapump |
| `dataguard` | Configuration DG (v$dataguard_config), sync par standby (v$archive_dest_status), mode protection, stats (apply/transport lag), alertes |

## 6. Sorties produites

Pour chaque exécution, un dossier horodaté `output/<AAAAMMJJThhmmssZ>/` contient :

- `snapshot.json` — données brutes normalisées (réutilisable, comparable d'un run à l'autre) ;
- `rapport.md` — rapport lisible (synthèse du parc + détail par base) ;
- `rapport.html` — rapport autonome (CSS + JS inclus) : tableau de bord à
  **onglets** (vue « Synthèse » + une base à la fois) avec cartes d'indicateurs,
  badges d'état, **recherche de base** et navigation depuis la synthèse — adapté
  aux parcs comportant de nombreuses bases ;
- `rapport.xlsx` — classeur Excel : feuille « Synthese » du parc + **une feuille
  dédiée par base de données** (faits, tableaux et messages par section) ;
- `csv/` — un fichier par base / section / tableau (+ `*__facts.csv`).

Chaque section porte un statut : `OK`, `PARTIEL` (droits ou objets partiellement
disponibles) ou `NON_DISPONIBLE` (aucune requête n'a abouti).

## 7. Comportement et garanties

- **Lecture seule** : seules des requêtes `SELECT` sont émises.
- **Isolation des pannes** : une base injoignable ou un manque de droits n'interrompt
  pas le traitement des autres bases ; l'erreur est journalisée et le rapport reste produit.
- **Détection des privilèges** : chaque requête optionnelle est isolée ; son échec
  (`ORA-00942`, `ORA-01031`…) est consigné sans casser la section.
- **Codes de retour** : `0` succès, `1` échec fonctionnel (toutes les bases en échec),
  `2` erreur de configuration/usage.
- **Aucun secret versionné** : `.env` et `output/` sont ignorés par Git ; les mots de
  passe ne sont jamais affichés.

## 8. Architecture

```
oracle/
├── setup_project.py            # bootstrap (venv + deps) et point d'entree de la CLI
├── requirements.txt            # oracledb, Jinja2 (PyYAML optionnel)
├── databases.yaml              # inventaire du parc
├── .env.example                # modele de configuration
└── tools/dbreport/
    ├── cli.py                  # commandes check / collect / report / run
    ├── config.py               # inventaire + variables d'environnement
    ├── db.py                   # connexion oracledb thin, infos de session
    ├── collect.py              # orchestration + persistance des snapshots
    ├── model.py                # snapshot et resultats de section
    ├── report.py               # rendu Markdown / HTML / CSV / Excel
    ├── logging_utils.py        # journal console + fichier
    ├── collectors/             # un module par section
    │   ├── _base.py            # utilitaires partagés
    │   ├── identity.py         # identification base
    │   ├── capacity.py         # capacité / tablespaces
    │   ├── objects.py          # objets / segments
    │   ├── health.py           # santé / performance
    │   ├── security.py         # sécurité / comptes
    │   ├── backup.py           # sauvegarde RMAN / Datapump
    │   └── dataguard.py        # Data Guard sync / config
    └── templates/report.html.j2
```

## 9. Limites connues

- Les sections de performance avancées (AWR/ASH) nécessitent le pack *Diagnostics* ;
  à défaut, la section `health` reste exploitable via `V$` uniquement.
- Les tablespaces temporaires sont rapportées via `DBA_TEMP_FREE_SPACE`.
- Le mode *thin* ne gère pas tous les cas d'authentification externe ; `SYSDBA`
  peut exiger `python-oracledb` en mode *thick* selon l'environnement.

