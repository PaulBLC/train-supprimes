import os
import json
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from shiny import App, ui, reactive, render
from pyecharts.charts import Geo
import pyecharts.options as opts
from pyecharts.globals import CurrentConfig, NotebookType
from faicons import icon_svg

# --- Configuration pyecharts pour Jupyter Lab (iframe HTML) ---
CurrentConfig.NOTEBOOK_TYPE = NotebookType.JUPYTER_LAB

# --- Chargement variables d'environnement ---
load_dotenv()
DB_USER = os.getenv("user")
DB_PASSWORD = os.getenv("password")
DB_HOST = os.getenv("host")
DB_PORT = os.getenv("port")
DB_NAME = os.getenv("dbname")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise ValueError("Les variables 'user', 'password', 'host', 'port' et 'dbname' doivent être définies dans .env")

# --- Chargement du GeoJSON pour la France ---
with open("france.geo.json", "r", encoding="utf-8") as f:
    france_geo = json.load(f)

# --- Chargement des données depuis PostgreSQL ---
def load_data():
    try:
        conn = psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME
        )
        query = """
            SELECT t.*, g.nom AS gare_nom, g.position_geographique
            FROM trains_supprimes t
            LEFT JOIN gares g ON t.arrival = g.nom
            WHERE g.position_geographique IS NOT NULL
        """
        df = pd.read_sql(query, conn)
        conn.close()
        # Formatage des dates & heures
        df['departure_date_dt'] = pd.to_datetime(df['departure_date'])
        df['departure_date_fmt'] = df['departure_date_dt'].dt.strftime('%d/%m/%Y')
        df['departure_time_fmt'] = pd.to_datetime(df['departure_time']).dt.strftime('%H:%M')
        df['arrival_time_fmt'] = pd.to_datetime(df['arrival_time']).dt.strftime('%H:%M')
        return df
    except Exception as e:
        print(f"Erreur chargement PostgreSQL: {e}")
        return pd.DataFrame()

# Chargement global des données
data = load_data()

# Mapping des types vers noms courts
type_map = {
    "highSpeedRail:FERRE": "TGV",
    "international:FERRE": "International",
    "longDistance:FERRE": "Intercité GL",
    "interregionalRail:FERRE": "Intercité IR",
    "regionalRail:FERRE": "TER",
    "railShuttle:FERRE": "Navette",
    "tramTrain:FERRE": "Tram train",
    "regionalCoach:ROUTIER": "Car régional",
    "shuttleCoach:ROUTIER": "Navette bus",
    ":ROUTIER": "Car LD"
}
if not data.empty:
    data['type_court'] = data['type'].map(type_map).fillna(data['type'])
else:
    data['type_court'] = []

# --- UI de l'application ---
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.navset_pill(
            ui.nav_panel("Dashboard", value="dashboard"),
            ui.nav_panel("Données", value="donnees"),
            id="nav"
        ),
        ui.input_select(
            "type", "Type de train",
            choices={"": "Tous"} | {t: t for t in sorted(data['type_court'])}
        ),
        ui.input_date_range(
            "date_range", "Période",
            start=(data['departure_date_dt'].min() if not data.empty else None),
            end=(data['departure_date_dt'].max() if not data.empty else None),
            format="dd/mm/yyyy", language="fr", separator=" au ", width="100%"
        ),
        ui.tags.style("""
            .card-graph { background:#fff; border-radius:12px; box-shadow:0 2px 12px rgba(0,0,0,0.08); padding:18px; margin-bottom:18px; }
        """),
        width="280px"
    ),
    ui.output_ui("main_content"),
    title="🚄 Dashboard des trains supprimés"
)

# --- Logique serveur ---
def server(input, output, session):
    @reactive.Calc
    def filtered_data():
        df = data.copy() if not data.empty else pd.DataFrame()
        sel = input.type()
        if sel:
            df = df[df['type_court'] == sel]
        start, end = input.date_range()
        if start and end:
            df = df[(df['departure_date_dt'] >= pd.to_datetime(start)) & (df['departure_date_dt'] <= pd.to_datetime(end))]
        return df

    @output
    @render.ui
    def map_france():
        df = filtered_data()
        if df.empty:
            return ui.tags.div("Aucune donnée à afficher", style="color:#888; padding:1rem;")
        # Extraction lat, lon
        coords = df['position_geographique'].str.split(',', expand=True).astype(float)
        df['lat'], df['lon'] = coords[0], coords[1]
        # Agrégation par gare
        data_map = (
            df.groupby('gare_nom')
              .agg(count=('gare_nom','size'), lon=('lon','first'), lat=('lat','first'))
              .reset_index()
        )
        # Création de la carte
        geo = Geo(init_opts=opts.InitOpts(width="100%", height="500px"))
        # Enregistrement de la carte France
        geo.add_js_funcs(f"echarts.registerMap('France',{json.dumps(france_geo)})")
        geo.add_schema(
            maptype="France",
            itemstyle_opts=opts.ItemStyleOpts(color="#f5f5f5", border_color="#bbb"),
            emphasis_label_opts=opts.LabelOpts(is_show=True)
        )
        # Déclaration des coordonnées
        for _, row in data_map.iterrows():
            geo.add_coordinate(row['gare_nom'], row['lon'], row['lat'])
        # Ajout des points
        geo.add(
            series_name="Suppressions",
            data_pair=[(row['gare_nom'], row['count']) for _, row in data_map.iterrows()],
            type_="effectScatter",
            symbol_size=8,
            label_opts=opts.LabelOpts(formatter="{b}", position="right", is_show=False)
        )
        geo.set_series_opts(effect_opts=opts.EffectOpts(scale=4))
        geo.set_global_opts(
            title_opts=opts.TitleOpts(title="Suppressions de trains en France"),
            visualmap_opts=opts.VisualMapOpts(max_=int(data_map['count'].max()), is_piecewise=True)
        )
        html = geo.render_embed()
        return ui.tags.iframe(srcdoc=html, style="width:100%;height:500px;border:none;")

    @output
    @render.ui
    def filtered_table():
        df = filtered_data()
        table = df[['gare_nom', 'departure_date_fmt']].rename(columns={'gare_nom': 'Gare', 'departure_date_fmt': 'Date'})
        return render.DataTable(table, filters=True, width='100%', height='400px', summary=False)

    @output
    @render.ui
    def main_content():
        if input.nav() == "dashboard":
            return ui.TagList(
                ui.row(ui.column(12, ui.div(ui.output_ui("map_france"), class_="card-graph")))
            )
        else:
            return ui.div(ui.h3("Table données"), ui.output_ui("filtered_table"))

# --- Démarrage de l'application ---
app = App(app_ui, server)

if __name__ == '__main__':
    app.run(port=8001)