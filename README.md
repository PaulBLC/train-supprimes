# Dashboard des trains supprimés
![image](https://github.com/user-attachments/assets/063508b2-163a-4dc7-a5be-98e47249519c)


Ce projet propose un dashboard interactif pour visualiser les suppressions de trains en France, construit avec [Shiny pour Python](https://shiny.posit.co/py/).

## Fonctionnalités
- ✅ Tableau des trains supprimés avec pagination et export CSV (UTF-8, compatible Excel)
- ✅ Statistiques en temps réel (KPI, moyennes, taux, etc.)
- ✅ Interface interactive Shiny (filtres dynamiques, navigation)
- ✅ Connexion Supabase/PostgreSQL
- ✅ Visualisations pyecharts intégrées (carte, histogrammes, camembert)
- ✅ Filtres avancés (dates, types, années, aujourd'hui/demain)
- ✅ Icônes modernes via Font Awesome (inclus dans l'interface)
- ✅ Téléchargement du tableau filtré au format CSV
- ✅ Cartographie interactive (pyecharts + GeoJSON)

## Mise à jour automatique des données
Les données sont automatiquement mises à jour chaque jour grâce à un workflow [n8n](https://n8n.io/) qui collecte et injecte les nouvelles données dans la base PostgreSQL.

![image](https://github.com/user-attachments/assets/dca503d3-0b99-4b84-a3ba-2f75287b58fa)


## Prérequis
- Python >= 3.10
- Accès à une base PostgreSQL avec les tables attendues (voir `schema.sql`)
- Fichier `.env` avec les variables de connexion (voir exemple ci-dessous)
- Les dépendances listées dans `requirements.txt`

## Lancement local
```bash
pip install -r requirements.txt
python shiny_app.py
```
L'application sera accessible sur [http://localhost:8001]

## Déploiement Docker
Un `Dockerfile` est fourni. Exemple :
```bash
docker build -t train-dashboard .
docker run --env-file .env -p 8001:8001 train-dashboard
```

## Exemple de fichier .env
```
SUPABASE_URL=...
SUPABASE_KEY=...
user=...
password=...
host=...
port=5432
dbname=...
```

## Structure du projet
- `shiny_app.py` : application de test
- `shiny_app_prod.py` : version production (UTF-8, icônes FA)
- `france.geo.json` : données géographiques pour la carte
- `requirements.txt` : dépendances Python
- `schema.sql` : structure de la base de données

## Mise à jour des données
Le workflow n8n s'exécute chaque jour pour alimenter la base de données. Le dashboard affiche donc toujours les données du jour et des jours précédents.

## Schéma de la base de données

Voici le schéma SQL utilisé pour la table principale :

```sql
-- Schéma de la base de données pour le Dashboard Trains Supprimés V2 (sans colonne motif)

-- Supprimer la table si elle existe
DROP TABLE IF EXISTS trains_supprimes;

-- Créer la table trains_supprimes avec les champs du CSV
CREATE TABLE trains_supprimes (
    id BIGSERIAL PRIMARY KEY,
    type TEXT,
    arrival TEXT,
    headsign TEXT,
    departure TEXT,
    arrival_time TIMESTAMP,
    departure_date DATE,
    departure_time TIMESTAMP
);

-- Activer Row Level Security (RLS)
ALTER TABLE trains_supprimes ENABLE ROW LEVEL SECURITY;

-- Créer une politique pour permettre la lecture publique
CREATE POLICY "Permettre lecture publique" ON trains_supprimes
    FOR SELECT USING (true);

-- Créer une politique pour permettre l'insertion avec la clé de service
CREATE POLICY "Permettre insertion service" ON trains_supprimes
    FOR INSERT WITH CHECK (true);

-- Créer une politique pour permettre la mise à jour avec la clé de service
CREATE POLICY "Permettre mise à jour service" ON trains_supprimes
    FOR UPDATE USING (true);

-- Créer une politique pour permettre la suppression avec la clé de service
CREATE POLICY "Permettre suppression service" ON trains_supprimes
    FOR DELETE USING (true); 
```

---

## 🐳 Cheatsheet Docker & Docker Compose

### 🚀 Démarrage & déploiement
| Commande | Description |
|---|---|
| `docker compose up -d --build` | Recrée toutes les images et relance tous les services en arrière-plan |
| `docker compose up -d --build <service1> <service2>` | Rebuild et relance seulement les services spécifiés (sans dépendances) |
| `docker compose up -d` | Relance tous les services sans rebuild |
| `docker compose up -d --no-deps <service>` | Relance le service spécifié sans remonter ses dépendances |
| `docker compose up -d --force-recreate <service>` | Force la recréation d'un service |

### 🔄 Redémarrage
| Commande | Description |
|---|---|
| `docker compose restart <service>` | Arrête & redémarre sans rebuild |
| `docker compose restart` | Redémarre tous les services |
| `docker compose down` | Arrête et supprime les containers, réseaux |

### 📊 Statut & logs
| Commande | Description |
|---|---|
| `docker compose ps` | Liste les services, leur statut et ports |
| `docker compose logs -f <service>` | Affiche les logs en temps réel pour un service |
| `docker compose logs -f` | Affiche les logs de tous les services |
| `docker logs -f <container>` | Logs d'un container par son nom/ID |

### 🔧 Exécution de commandes dans un container
| Commande | Description |
|---|---|
| `docker exec -it <container> sh` | Ouvre un shell dans le container (Debian/Alpine) |
| `docker exec -it <container> bash` | Ouvre un shell Bash si présent |
| `docker exec -it n8n-postgres psql -U <user> -d <db>` | Lancer psql dans Postgres |
| `docker run --rm --network <net> curlimages/curl:7.85.0 curl ...` | Appeler un service interne via HTTP (pour debug réseau) |

### 🛠 Gestion des images & volumes
| Commande | Description |
|---|---|
| `docker images` | Liste les images locales |
| `docker rmi <image>` | Supprime une image |
| `docker volume ls` | Liste les volumes |
| `docker volume rm <volume>` | Supprime un volume (perte de données !) |
| `docker system prune --volumes` | Nettoie containers, réseaux, images et volumes orphelins |

### 🧹 Nettoyage & rebuild complet
```bash
# 1) Arrêt et suppression de la stack
docker compose down

# 2) (Optionnel) Supprimez les volumes de données si vous voulez repartir à zéro
docker volume rm postgres_data n8n_data local-files_n8n_data ollama_data

# 3) Rebuild & relance
docker compose up -d --build
```

### ✏️ Quelques tips
- Inspecter un container :
  ```bash
  docker inspect <container>
  ```
- Voir les networks :
  ```bash
  docker network ls
  docker network inspect <network>
  ```
- Tester un host interne (depuis Traefik network) :
  ```bash
  docker run --rm --network web curlimages/curl:7.85.0 curl -I http://dashboard:8001
  ```
- Forcer la recréation d'un service :
  ```bash
  docker compose up -d --force-recreate <service>
  ```
---
