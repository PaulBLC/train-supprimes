# Dashboard Trains Supprimés V2

Version simplifiée du dashboard des trains supprimés SNCF avec FastAPI, HTML/CSS/JS et pyecharts.

## Structure du projet

```
TRAIN-DASHBOARD-V2/
├── app.py              # Backend FastAPI
├── static/
│   ├── index.html      # Page principale
│   ├── style.css       # Styles CSS
│   └── script.js       # JavaScript
├── requirements.txt    # Dépendances Python
└── README.md          # Ce fichier
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
```

3. **Lancer l'application :**
```bash
python app.py
```

4. **Accéder au dashboard :**
Ouvrir http://localhost:8000 dans votre navigateur

## Fonctionnalités

- ✅ Tableau des trains supprimés avec pagination
- ✅ Statistiques en temps réel
- ✅ Interface responsive
- ✅ Auto-refresh des données
- ✅ Connexion Supabase

## API Endpoints

- `GET /` - Page d'accueil
- `GET /api/trains` - Données des trains (avec pagination)
- `GET /api/stats` - Statistiques
- `GET /api/health` - Santé de l'API

## Prochaines étapes

- [ ] Ajouter des graphiques avec pyecharts
- [ ] Filtres par date/gare
- [ ] Export des données
- [ ] Carte de France avec heatmap 