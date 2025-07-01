import pandas as pd
from shiny import App, ui, reactive, render
from pyecharts.charts import Bar, Line, Pie
from pyecharts import options as opts
from pyecharts.globals import CurrentConfig, NotebookType
from dotenv import load_dotenv
from supabase import create_client, Client
import os
import psycopg2
import dash
from dash import dcc, html, dash_table
from faicons import icon_svg
import folium

# Configurer pyecharts pour afficher dans un iframe HTML
CurrentConfig.NOTEBOOK_TYPE = NotebookType.JUPYTER_LAB

# Chargement des variables d'environnement
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL et SUPABASE_KEY sont requis")

# Initialisation Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Chargement des données ---
def load_data():
    try:
        connection = psycopg2.connect(
            user=os.getenv("user"),
            password=os.getenv("password"),
            host=os.getenv("host"),
            port=os.getenv("port"),
            dbname=os.getenv("dbname")
        )
        query = """
            SELECT *
            FROM trains_supprimes
            WHERE departure_date >= '2023-01-01'
              AND departure_date <= '2025-12-31'
        """
        df = pd.read_sql(query, connection)
        df['departure_date_dt'] = pd.to_datetime(df['departure_date'])
        df['departure_date_fmt'] = df['departure_date_dt'].dt.strftime('%d/%m/%Y')
        df['departure_time_fmt'] = pd.to_datetime(df['departure_time']).dt.strftime('%H:%M')
        df['arrival_time_fmt'] = pd.to_datetime(df['arrival_time']).dt.strftime('%H:%M')
        connection.close()
        return df
    except Exception as e:
        print(f"Erreur chargement PostgreSQL: {e}")
        return pd.DataFrame()

# Ajout du mapping des types de train vers noms courts
TYPE_TRAIN_COURT = {
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

data = load_data()
data['type_court'] = data['type'].map(TYPE_TRAIN_COURT).fillna(data['type'])

# --- UI ---
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.navset_pill(
            ui.nav_panel("Dashboard", value="dashboard"),
            ui.nav_panel("Données", value="donnees"),
            ui.nav_panel("Map", value="map"),
            id="nav"
        ),
        ui.input_select(
            "type", "Type de train",
            choices={"": "Tous"} | {t: t for t in sorted(data['type_court'].dropna().unique())}
        ),
        ui.input_date_range(
            "date_range", "Période",
            start=data['departure_date_dt'].min(),
            end=data['departure_date_dt'].max(),
            format="dd/mm/yyyy",
            language="fr",
            separator=" au ",
            width="100%"
        ),
        ui.div(
            *[
                ui.input_action_button(f"year_{year}", str(year), class_="btn-year", style="margin:2px;")
                for year in sorted(data['departure_date_dt'].dt.year.unique())
            ],
            style="margin-top:10px;"
        ),
        open="open",
        width="280px"
    ),
    ui.output_ui("main_content"),
    title="🚄 Dashboard des trains supprimés"
)



# --- Serveur ---
def server(input, output, session):
    @reactive.Calc
    def filtered_data():
        df = data.copy()
        # Filtre type
        if input.type():
            df = df[df['type_court'] == input.type()]
        # Filtre dates
        start, end = input.date_range()
        # Si aucune date sélectionnée, on prend 2024-01-01 à aujourd'hui
        if not start or not end:
            start = pd.Timestamp("2024-01-01")
            end = pd.Timestamp.today()
        df = df[(df['departure_date_dt'] >= pd.to_datetime(start)) &
                (df['departure_date_dt'] <= pd.to_datetime(end))]
        return df

    @output
    @render.data_frame
    def filtered_table():
        df = filtered_data()

        # Renommage et réordonnancement
        table = (
            df.rename(columns={
                'type_court': 'Type',
                'headsign': 'N° Train',
                'departure_date_fmt': 'Date',
                'departure': 'Départ',
                'arrival': 'Arrivée',
                'departure_time_fmt': 'Heure Dép.',
                'arrival_time_fmt': 'Heure Arr.'
            })[
                ['Type', 'N° Train', 'Date', 'Départ', 'Arrivée', 'Heure Dép.', 'Heure Arr.']
            ]
        )

        return render.DataTable(
            table,
            filters=True,
            width='100%',
            height='400px',
            summary=False,
            styles=[
                {
                    "rows": None,
                    "cols": None,
                    "style": {
                        "font-size": "1rem",
                        "background": "#fff"
                    }
                }
            ]
        )

    @output
    @render.ui
    def bar_chart():
        from shiny import ui as shin_ui
        df = filtered_data()
        counts = df['type_court'].value_counts()
        bar = (
            Bar(init_opts=opts.InitOpts(width="100%", height="375px"))
            .add_xaxis(counts.index.tolist())
            .add_yaxis("Suppression", counts.values.tolist())
            .set_global_opts(
                title_opts=opts.TitleOpts(title="Suppressions par type"),
                xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=30)),
                tooltip_opts=opts.TooltipOpts(trigger="axis")
            )
        )
        html = bar.render_embed()
        return shin_ui.tags.iframe(srcdoc=html, style="width:100%; height:400px; border:none;")

    @output
    @render.ui
    def pie_chart():
        from shiny import ui as shin_ui
        df = filtered_data()
        top = df['departure'].value_counts().head(10)
        pie = (
            Pie(init_opts=opts.InitOpts(width="100%", height="375px"))
            .add(
                "Gares",
                [list(z) for z in zip(top.index.tolist(), top.values.tolist())],
                radius=["40%", "70%"],
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(title="Top 10 gares de départ"),
                legend_opts=opts.LegendOpts(
                    orient="horizontal",
                    pos_top="bottom",
                    pos_left="center"
                )
            )
        )
        html = pie.render_embed()
        return shin_ui.tags.iframe(srcdoc=html, style="width:100%; height:400px; border:none;")

    @output
    @render.ui
    def line_chart():
        from shiny import ui as shin_ui
        df = filtered_data()
        # Grouper par mois
        monthly = df.groupby(df['departure_date_dt'].dt.to_period('M')).size().reset_index(name='count')
        monthly['month'] = monthly['departure_date_dt'].dt.strftime('%m/%Y')
        from pyecharts.charts import Line
        from pyecharts import options as opts
        line = (
            Line(init_opts=opts.InitOpts(width="100%", height="375px"))
            .add_xaxis(monthly['month'].tolist())
            .add_yaxis("Suppressions", monthly['count'].tolist())
            .set_global_opts(
                title_opts=opts.TitleOpts(title="Évolution mensuelle"),
                xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=45)),
                tooltip_opts=opts.TooltipOpts(trigger="axis")
            )
        )
        html = line.render_embed()
        return shin_ui.tags.iframe(srcdoc=html, style="width:50%; height:400px; border:none;")

    # KPI 1 : Nombre moyen de trains supprimés par jour
    @output
    @render.ui
    def kpi_moyenne():
        df = filtered_data()
        val = "-" if df.empty else round(df.groupby('departure_date_dt').size().mean(), 2)
        return ui.value_box(
            "Moyenne/jour",
            f"{val}",
            showcase=icon_svg("chart-bar")
        )

    # KPI 2 : Trains supprimés aujourd'hui (non filtré par période)
    @output
    @render.ui
    def kpi_aujourdhui():
        today = pd.Timestamp.today().normalize()
        count = data[data['departure_date_dt'] == today].shape[0]
        return ui.value_box(
            "Aujourd'hui",
            f"{count}",
            showcase=icon_svg("train")
        )

    # KPI 3 : Source des données (cliquable)
    @output
    @render.ui
    def kpi_source():
        return ui.value_box(
            "Source des données",
            ui.a("data.gouv.fr",
                 href="https://www.data.gouv.fr/fr/datasets/641b456a5374b1bdc9dce4cf",
                 target="_blank"),
            showcase=icon_svg("link")
        )

    @output
    @render.ui
    def main_content():
        nav = input.nav()  # "dashboard" ou "donnees"
        if nav == "dashboard":
            return ui.TagList(
                ui.layout_column_wrap(
                    ui.output_ui("kpi_moyenne"),
                    ui.output_ui("kpi_aujourdhui"),
                    ui.output_ui("kpi_source"),
                ),
                ui.row(
                    ui.column(6, ui.output_ui("bar_chart")),
                    ui.column(6, ui.output_ui("pie_chart"))
                ),
                ui.row(
                    ui.column(12, ui.output_ui("line_chart"))
                ),
            )
        elif nav == "donnees":
            return ui.div(
                ui.h3("Tableau filtré"),
                ui.output_data_frame("filtered_table"),
                style="width:100%; margin:0; padding:0;"
            )

    # Pour chaque bouton année, on crée un observer qui écoute son clic
    def make_year_observer(year):
        @reactive.Effect
        @reactive.event(input[f"year_{year}"])
        def _():
            ui.update_date_range(
                "date_range",                  # id de votre input_date_range
                start=f"{year}-01-01",         # 1er janvier de l'année
                end=f"{year}-12-31",           # 31 décembre de l'année
                session=session                # session pour cibler le client
            )

    # On instancie un observer pour chaque année disponible dans vos données
    for year in sorted(data['departure_date_dt'].dt.year.unique()):
        make_year_observer(year)
    # Ajout de la carte
    @output
    @render.ui
    def map_chart():
        from shiny import ui as shin_ui
        import folium

        df = filtered_data()
        # Vérifie la présence des colonnes nécessaires
        if 'departure' not in df.columns or 'position_geographique' not in df.columns:
            return shin_ui.tags.div("Colonnes nécessaires manquantes", style="color:#888; padding:1rem;")
        # On ne garde que les lignes avec des coordonnées valides
        df = df.dropna(subset=['position_geographique', 'departure'])
        if df.empty:
            return shin_ui.tags.div("Pas de données géo", style="color:#888; padding:1rem;")

        # Grouper par ville de départ et coordonnées, compter les suppressions
        grouped = df.groupby(['departure', 'position_geographique']).size().reset_index(name='nb_suppressions')

        # Génère la carte
        m = folium.Map(location=[46.8,2.3], zoom_start=6, tiles="CartoDB positron")
        for _, row in grouped.iterrows():
            try:
                latlon = row['position_geographique'].split(',')
                if len(latlon) == 2:
                    lat, lon = float(latlon[0]), float(latlon[1])
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=5 + row['nb_suppressions'],  # Rayon proportionnel au nombre de suppressions
                        color='red',
                        fill=True,
                        fill_opacity=0.7,
                        popup=f"{row['departure']}<br>Trains supprimés : {row['nb_suppressions']}"
                    ).add_to(m)
            except Exception as e:
                continue

        carte_html = m.get_root().render()
        return shin_ui.HTML(carte_html)

app = App(app_ui, server)

if __name__ == '__main__':
    app.run(port=8001)