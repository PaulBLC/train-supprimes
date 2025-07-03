import pandas as pd
import json
from shiny import App, ui, reactive, render
from pyecharts.charts import Bar, Line, Pie, Geo
from pyecharts import options as opts
from pyecharts.globals import CurrentConfig, NotebookType
from dotenv import load_dotenv
from supabase import create_client, Client
import os
import psycopg2
import io
from faicons import icon_svg

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
            SELECT t.*, g.nom, g.position_geographique
            FROM trains_supprimes t
            LEFT JOIN gares g
            ON t.arrival = g.nom
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
            id="nav"
        ),
        ui.input_select(
            "type", "Type de train",
            choices={"": "Tous"} | {t: t for t in sorted(data['type_court'].dropna().unique())}
        ),
        ui.input_date_range(
            "date_range", "Période",
            start=pd.Timestamp.today(),
            end=pd.Timestamp.today(),
            format="dd/mm/yyyy",
            language="fr",
            separator=" au ",
            width="100%"
        ),
        ui.tags.style("""
        .btn-year {
            background: #f0f0f0;
            color: #333;
            border: 1px solid #bbb;
            border-radius: 4px;
            padding: 8px 0;
            margin: 2px;
            cursor: pointer;
            font-weight: normal;
            min-width: 110px;
            width: 110px;
            display: inline-block;
            text-align: center;
        }
        .btn-year-active {
            background: #1976d2;
            color: #fff;
            border: 1.5px solid #1976d2;
            font-weight: bold;
        }
        .btn-year-disabled {
            background: #e0e0e0 !important;
            color: #aaa !important;
            border: 1px solid #ccc !important;
            cursor: not-allowed !important;
            opacity: 0.7;
        }
        .btn-row {
            display: flex;
            flex-direction: row;
            justify-content: center;
            margin-bottom: 4px;
        }
        .card-graph {
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 2px 12px 0 rgba(0,0,0,0.08), 0 1.5px 4px 0 rgba(0,0,0,0.08);
            padding: 18px 18px 10px 18px;
            margin-bottom: 18px;
        }
        body {
            font-family: 'Segoe UI Emoji', 'Noto Color Emoji', 'Apple Color Emoji', 'Segoe UI', Arial, sans-serif;
        }
        """),
        ui.output_ui("special_day_buttons"),
        ui.output_ui("year_buttons"),
        ui.div(
            ui.a(
                "Source des données : data.gouv.fr",
                href="https://www.data.gouv.fr/fr/datasets/641b456a5374b1bdc9dce4cf",
                target="_blank",
                style="font-size: 0.85em; color: #888; text-decoration: underline; display: block; margin-top: 30px; text-align: center;"
            ),
            ui.a(
                "Cartes GeoJSON : france-geojson.gregoiredavid.fr",
                href="https://france-geojson.gregoiredavid.fr/",
                target="_blank",
                style="font-size: 0.8em; color: #888; text-decoration: underline; display: block; margin-top: 4px; text-align: center;"
            )
        ),
        open="open",
        width="280px"
    ),
    ui.output_ui("main_content"),
    title=ui.TagList(
        ui.tags.i(class_="fas fa-train", style="margin-right:8px;"),
        "Dashboard des trains supprimés"
    )
)

# --- Serveur ---
def server(input, output, session):
    # Initialisation : sélectionne "Aujourd'hui" au lancement
    selected_year = reactive.Value("today")
    today = pd.Timestamp.today().strftime('%Y-%m-%d')
    tomorrow = (pd.Timestamp.today() + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    date_max = data['departure_date_dt'].max().strftime('%Y-%m-%d')
    if not hasattr(server, '_init_done'):
        ui.update_date_range(
            "date_range",
            start=today,
            end=today,
            session=session
        )
        server._init_done = True

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
            height='800px',
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
        if df.empty:
            return shin_ui.tags.div("Aucune donnée à afficher pour cette période", style="color:#888; padding:1rem;")
        counts = df['type_court'].value_counts()
        if counts.empty:
            return shin_ui.tags.div("Aucune donnée à afficher pour cette période", style="color:#888; padding:1rem;")
        bar = (
            Bar(init_opts=opts.InitOpts(width="100%", height="375px"))
            .add_xaxis(counts.index.tolist())
            .add_yaxis("Suppression", counts.values.tolist())
            .set_global_opts(
                title_opts=opts.TitleOpts(title="Suppressions par type"),
                xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=30)),
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                legend_opts=opts.LegendOpts(is_show=False)
            )
        )
        html = bar.render_embed()
        return shin_ui.tags.iframe(srcdoc=html, style="width:100%; height:400px; border:none;")

    # Carte France (remplace pie_chart)
    @output
    @render.ui
    def map_france():
        df = filtered_data()
        if df.empty:
            return ui.tags.div("Aucune donnée à afficher", style="color:#888; padding:1rem;")
        coords = df['position_geographique'].str.split(',', expand=True).astype(float)
        df['lat'], df['lon'] = coords[0], coords[1]
        data_map = (
            df.groupby('nom')
              .agg(count=('nom','size'), lon=('lon','first'), lat=('lat','first'))
              .reset_index()
        )
        with open("france.geo.json", "r", encoding="utf-8") as f:
            france_geo = json.load(f)
        geo = Geo(init_opts=opts.InitOpts(width="100%", height="375px"))
        geo.add_js_funcs(f"echarts.registerMap('France',{json.dumps(france_geo)})")
        geo.add_schema(
            maptype="France",
            itemstyle_opts=opts.ItemStyleOpts(color="#f5f5f5", border_color="#bbb"),
            emphasis_label_opts=opts.LabelOpts(is_show=True)
        )
        for _, row in data_map.iterrows():
            geo.add_coordinate(row['nom'], row['lon'], row['lat'])
        geo.add(
            series_name="Suppressions",
            data_pair=[(row['nom'], row['count']) for _, row in data_map.iterrows()],
            type_="effectScatter", symbol_size=8,
            label_opts=opts.LabelOpts(formatter="{b}", position="right", is_show=False)
        )
        geo.set_series_opts(effect_opts=opts.EffectOpts(scale=4))
        geo.set_global_opts(
            title_opts=opts.TitleOpts(title="Suppressions de trains en France"),
            visualmap_opts=opts.VisualMapOpts(max_=int(data_map['count'].max()), is_piecewise=True),
            legend_opts=opts.LegendOpts(is_show=False)
        )
        html = geo.render_embed()
        from shiny import ui as shin
        return shin.tags.iframe(srcdoc=html, style="width:100%; height:400px; border:none;")
    
    @output
    @render.ui
    def line_chart():
        from shiny import ui as shin_ui
        df = filtered_data()
        if df.empty:
            return shin_ui.tags.div("Aucune donnée à afficher pour cette période", style="color:#888; padding:1rem;")
        # Grouper par mois
        monthly = df.groupby(df['departure_date_dt'].dt.to_period('M')).size().reset_index(name='count')
        if monthly.empty:
            return shin_ui.tags.div("Aucune donnée à afficher pour cette période", style="color:#888; padding:1rem;")
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
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                legend_opts=opts.LegendOpts(
                    orient="vertical",
                    pos_top="top",
                    pos_right="0%"
                )
            )
        )
        html = line.render_embed()
        return shin_ui.tags.iframe(srcdoc=html, style="width:100%; height:400px; border:none;")

    @output
    @render.ui
    def histo_heure():
        from shiny import ui as shin_ui
        df = filtered_data()
        if df.empty or 'departure_time_fmt' not in df.columns:
            return shin_ui.tags.div("Aucune donnée à afficher pour cette période", style="color:#888; padding:1rem;")
        df['heure'] = pd.to_datetime(df['departure_time_fmt'], format='%H:%M', errors='coerce').dt.hour
        counts = df['heure'].value_counts().sort_index()
        if counts.empty:
            return shin_ui.tags.div("Aucune donnée à afficher pour cette période", style="color:#888; padding:1rem;")
        from pyecharts.charts import Bar
        from pyecharts import options as opts
        bar = (
            Bar(init_opts=opts.InitOpts(width="100%", height="375px"))
            .add_xaxis([f"{h:02d}h" for h in counts.index])
            .add_yaxis("Suppressions", counts.values.tolist())
            .set_global_opts(
                title_opts=opts.TitleOpts(title="Suppressions par heure"),
                xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=0)),
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                legend_opts=opts.LegendOpts(is_show=False)
            )
        )
        html = bar.render_embed()
        return shin_ui.tags.iframe(srcdoc=html, style="width:100%; height:400px; border:none;")

    # --- KPI Dashboard 1 : un seul jour ---
    @output
    @render.ui
    def kpi_total_supp():
        df = filtered_data()
        count = df.shape[0]
        return ui.value_box(
            "Trains supprimés",
            f"{count}",
            showcase=icon_svg("train")
        )

    @output
    @render.ui
    def kpi_gare_max():
        df = filtered_data()
        if df.empty:
            gare = "-"
            nb = "-"
        else:
            top = df['departure'].value_counts().idxmax()
            nb = df['departure'].value_counts().max()
            gare = f"{top} ({nb})"
        return ui.value_box(
            "Gare la plus impactée",
            gare,
            showcase=icon_svg("location-dot")
        )

    @output
    @render.ui
    def kpi_taux_supp():
        df = filtered_data()
        count = df.shape[0]
        taux = round(100 * count / 15000, 2)
        return ui.value_box(
            "% trains supprimés",
            f"{taux} %",
            showcase=icon_svg("percent")
        )

    # --- KPI Dashboard 2 : plage de dates ---
    @output
    @render.ui
    def kpi_total_supp_period():
        df = filtered_data()
        count = df.shape[0]
        return ui.value_box(
            "Trains supprimés",
            f"{count}",
            showcase=icon_svg("train")
        )

    @output
    @render.ui
    def kpi_moyenne_jour():
        df = filtered_data()
        if df.empty:
            val = "-"
        else:
            val = round(df.groupby('departure_date_dt').size().mean(), 2)
        return ui.value_box(
            "Moyenne/jour",
            f"{val}",
            showcase=icon_svg("chart-bar")
        )

    @output
    @render.ui
    def kpi_taux_moyen():
        df = filtered_data()
        if df.empty:
            taux = "-"
        else:
            jours = df['departure_date_dt'].nunique()
            taux = round(100 * (df.shape[0] / (jours * 15000)), 2) if jours else "-"
        return ui.value_box(
            "Taux moyen de suppression",
            f"{taux} %",
            showcase=icon_svg("percent")
        )

    @output
    @render.data_frame
    def table_jour():
        df = filtered_data()
        if df.empty:
            return render.DataTable(
                pd.DataFrame(),
                filters=True,
                width='100%',
                height='100%',
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
    def pie_chart():
        from shiny import ui as shin_ui
        df = filtered_data()
        if df.empty:
            return shin_ui.tags.div("Aucune donnée à afficher pour cette période", style="color:#888; padding:1rem;")
        top = df['departure'].value_counts().head(10)
        if top.empty:
            return shin_ui.tags.div("Aucune donnée à afficher pour cette période", style="color:#888; padding:1rem;")
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
                    orient="vertical",
                    pos_top="top",
                    pos_right="0%"
                )
            )
        )
        html = pie.render_embed()
        return shin_ui.tags.iframe(srcdoc=html, style="width:100%; height:400px; border:none;")

    @output
    @render.ui
    def main_content():
        nav = input.nav()
        start, end = input.date_range()
        if nav == "dashboard":
            if start == end:
                # Dashboard 1
                return ui.TagList(
                    ui.row(
                        ui.column(4, ui.output_ui("kpi_total_supp")),
                        ui.column(4, ui.output_ui("kpi_gare_max")),
                        ui.column(4, ui.output_ui("kpi_taux_supp")),
                    ),
                    ui.row(
                        ui.column(6, ui.div(ui.output_ui("bar_chart"), class_="card-graph")),
                        ui.column(6, ui.div(ui.output_ui("map_france"), class_="card-graph"))
                    ),
                    ui.row(
                        ui.column(6, ui.div(ui.output_ui("histo_heure"), class_="card-graph")),
                        ui.column(6, ui.output_data_frame("table_jour"))
                        
                    ),
                )
            else:
                # Dashboard 2
                return ui.TagList(
                    ui.row(
                        ui.column(4, ui.output_ui("kpi_total_supp_period")),
                        ui.column(4, ui.output_ui("kpi_moyenne_jour")),
                        ui.column(4, ui.output_ui("kpi_taux_moyen")),
                    ),
                    ui.row(
                        ui.column(6, ui.div(ui.output_ui("bar_chart"), class_="card-graph")),
                        ui.column(6, ui.div(ui.output_ui("pie_chart"), class_="card-graph"))
                    ),
                    ui.row(
                        ui.column(6, ui.div(ui.output_ui("line_chart"), class_="card-graph")),
                        ui.column(6, ui.div(ui.output_ui("histo_heure"), class_="card-graph"))
                    ),
                )
        elif nav == "donnees":
            return ui.div(
                ui.div(
                    ui.h3("Tableau filtré", style="display:inline-block; vertical-align:middle; margin-right:18px; margin-bottom:0;"),
                    ui.download_button("download_csv", "CSV", class_="btn-year", style="margin-right:10px; display:inline-block; vertical-align:middle;"),
                    style="margin-bottom: 12px; display: flex; align-items: center; gap: 10px;"
                ),
                ui.output_data_frame("filtered_table"),
                style="width:100%; margin:0; padding:0;"
            )

    special_days = [("today", "Aujourd'hui"), ("tomorrow", "Demain")]

    @output
    @render.ui
    def special_day_buttons():
        # Désactive "Demain" si la date max de la BDD < demain
        demain_disabled = pd.to_datetime(date_max) < pd.to_datetime(tomorrow)
        return ui.div(
            *[
                ui.input_action_button(
                    f"special_{key}",
                    label,
                    class_="btn-year" + (" btn-year-active" if selected_year.get() == key else "") + (" btn-year-disabled" if key == "tomorrow" and demain_disabled else ""),
                    style="margin:2px;",
                    disabled=demain_disabled if key == "tomorrow" else False,
                    title="Aucune donnée pour demain" if key == "tomorrow" and demain_disabled else ""
                )
                for key, label in special_days
            ],
            class_="btn-row"
        )

    @output
    @render.ui
    def year_buttons():
        return ui.div(
            *[
                ui.input_action_button(
                    f"year_{year}",
                    str(year),
                    class_="btn-year" + (" btn-year-active" if selected_year.get() == year else ""),
                    style="margin:2px;"
                )
                for year in sorted(data['departure_date_dt'].dt.year.unique())
            ],
            class_="btn-row"
        )

    # Observers pour les boutons année
    def make_year_observer(year):
        @reactive.Effect
        @reactive.event(input[f"year_{year}"])
        def _():
            selected_year.set(year)
            if year == data['departure_date_dt'].dt.year.max():
                start = f"{year}-01-01"
                end = data[data['departure_date_dt'].dt.year == year]['departure_date_dt'].max().strftime('%Y-%m-%d')
            else:
                start = f"{year}-01-01"
                end = f"{year}-12-31"
            ui.update_date_range(
                "date_range",
                start=start,
                end=end,
                session=session
            )
    for year in sorted(data['departure_date_dt'].dt.year.unique()):
        make_year_observer(year)

    # Observers pour les boutons spéciaux
    @reactive.Effect
    @reactive.event(input.special_today)
    def _():
        selected_year.set("today")
        today = pd.Timestamp.today().strftime('%Y-%m-%d')
        ui.update_date_range(
            "date_range",
            start=today,
            end=today,
            session=session
        )

    @reactive.Effect
    @reactive.event(input.special_tomorrow)
    def _():
        selected_year.set("tomorrow")
        tomorrow = (pd.Timestamp.today() + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        ui.update_date_range(
            "date_range",
            start=tomorrow,
            end=tomorrow,
            session=session
        )

    @output
    @render.download(filename="trains_supprimes.csv")
    def download_csv():
        df = filtered_data()
        buf = io.BytesIO()
        # Ajout du BOM UTF-8 pour compatibilité Excel et accents
        csv_data = df.to_csv(index=False, sep=";", encoding="utf-8-sig")
        buf.write(csv_data.encode("utf-8-sig"))
        buf.seek(0)
        return buf

app = App(app_ui, server)

if __name__ == '__main__':
    app.run(port=8001)