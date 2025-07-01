import pandas as pd
from shiny import App, ui, reactive, render
from pyecharts.charts import Bar, Line, Pie
from pyecharts import options as opts
from pyecharts.globals import CurrentConfig, NotebookType
from dotenv import load_dotenv
from supabase import create_client, Client
import os
import psycopg2

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

data = load_data()

# --- UI ---
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_select(
            "type", "Type de train",
            choices={"": "Tous"} | {t: t for t in sorted(data['type'].dropna().unique())}
        ),
        ui.input_date_range(
            "date_range", "Période",
            start=data['departure_date_dt'].min(),
            end=data['departure_date_dt'].max(),
            format="dd/mm/yyyy",
            language="fr"
        ),
        open="open",
        width="400px"
    ),
    ui.navset_bar(
        ui.nav_panel(
            "Visualisations",
            ui.card(
                ui.row(
                    ui.column(4, ui.output_ui("kpi_moyenne")),
                    ui.column(4, ui.output_ui("kpi_aujourdhui")),
                    ui.column(4, ui.output_ui("kpi_source")),
                ),
                ui.row(
                    ui.column(6, ui.output_ui("bar_chart")),
                    ui.column(6, ui.output_ui("pie_chart"))
                ),
                ui.row(
                    ui.column(6, ui.output_ui("line_chart"))
                )
            )
        ),
        ui.nav_panel(
            "Données",
            ui.div(
                ui.h3("Tableau filtré"),
                ui.output_data_frame("filtered_table"),
                style="width:100%; margin:0; padding:0;"
            )
        ),
        title="Dashboard des trains supprimés"
    )
)

# --- Serveur ---
def server(input, output, session):
    @reactive.Calc
    def filtered_data():
        df = data.copy()
        if input.type():
            df = df[df['type'] == input.type()]
        start, end = input.date_range()
        if start and end:
            df = df[(df['departure_date_dt'] >= pd.to_datetime(start)) &
                    (df['departure_date_dt'] <= pd.to_datetime(end))]
        return df

    @output
    @render.data_frame
    def filtered_table():
        df = filtered_data()
        return pd.DataFrame({
            'Type': df['type'],
            'N° Train': df['headsign'],
            'Date': df['departure_date_fmt'],
            'Départ': df['departure'],
            'Arrivée': df['arrival'],
            'Heure Dép.': df['departure_time_fmt'],
            'Heure Arr.': df['arrival_time_fmt'],
        })

    @output
    @render.ui
    def bar_chart():
        from shiny import ui as shin_ui
        df = filtered_data()
        counts = df['type'].value_counts()
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
        return shin_ui.tags.iframe(srcdoc=html, style="width:100%; height:400px; border:none;")

    # KPI 1 : Nombre moyen de trains supprimés par jour
    @output
    @render.ui
    def kpi_moyenne():
        import html
        df = filtered_data()
        if df.empty:
            val = "-"
        else:
            val = round(df.groupby('departure_date_dt').size().mean(), 2)
        return ui.card(
            ui.div(
                ui.h4("📊 Moyenne/jour"),
            ),
            ui.h3(f"{val}"),
        )

    # KPI 2 : Trains supprimés aujourd'hui (non filtré par période)
    @output
    @render.ui
    def kpi_aujourdhui():
        import html
        today = pd.Timestamp.today().normalize()
        count = data[data['departure_date_dt'] == today].shape[0]
        return ui.card(
            ui.div(
                ui.h4("🚆Aujourd'hui"),
            ),
            ui.h3(f"{count}"),
        )

    # KPI 3 : Source des données (cliquable)
    @output
    @render.ui
    def kpi_source():
        return ui.card(
            ui.div(
                ui.h4("🔗 Source des données"),
            ),
            ui.a("data.gouv.fr", href="https://www.data.gouv.fr/fr/datasets/641b456a5374b1bdc9dce4cf", target="_blank"),
        )

app = App(app_ui, server)

if __name__ == '__main__':
    app.run(port=8001)
