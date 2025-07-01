# Dashboard Trains Supprimés V2

Version basée sur Shiny pour Python pour la visualisation interactive des trains supprimés SNCF. Plus de HTML/CSS/JS ni FastAPI : tout est géré via Shiny et Python.

## Structure du projet

```
TRAIN-DASHBOARD-V2/
├── shiny_app.py             # Application Shiny pour visualisation interactive
├── import_and_clean_csv.py  # Script d'import et nettoyage des CSV
├── requirements.txt         # Dépendances Python
├── schema.sql               # Schéma SQL Supabase
└── README.md                # Ce fichier
```

## Installation

1. **Installer les dépendances :**
```bash
pip install -r requirements.txt
```

2. **Configurer les variables d'environnement :**
Créer un fichier `.env` avec :
```
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_anon_key_here
user=...         # identifiants PostgreSQL si besoin
password=...
host=...
port=...
dbname=...
```

3. **Importer les données dans Supabase :**
```bash
python import_and_clean_csv.py
```

4. **Lancer l'application Shiny :**
```bash
shiny run --reload shiny_app.py
```

5. **Accéder au dashboard :**
- Shiny : http://localhost:8000 (ou port indiqué par Shiny)

## Fonctionnalités

- ✅ Tableau des trains supprimés avec pagination
- ✅ Statistiques en temps réel
- ✅ Interface interactive Shiny
- ✅ Connexion Supabase
- ✅ Visualisations pyecharts intégrées
- ✅ Carte interactive (Folium)

## Prochaines étapes

- [ ] Filtres avancés
- [ ] Export des données
- [ ] Amélioration de la carte
- [ ] Automatisation de l'import quotidien 