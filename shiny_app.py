# -*- coding: utf-8 -*-

import pandas as pd
import json
import time
import io
import os

import psycopg2
from pyecharts.charts import Bar, Line, Pie, Geo
from pyecharts import options as opts
from pyecharts.globals import CurrentConfig, NotebookType
from shiny import App, ui, reactive, render
from dotenv import load_dotenv
from faicons import icon_svg
import shinyswatch

CurrentConfig.NOTEBOOK_TYPE = NotebookType.JUPYTER_LAB

# ── Configuration ─────────────────────────────────────────────────────

load_dotenv()

CACHE_TTL = 300
DAILY_TRAIN_ESTIMATE = 15_000

C_BLUE = "#4361EE"
C_TEAL = "#06D6A0"
C_PIE  = ["#4361EE", "#7209B7", "#F72585", "#4CC9F0", "#06D6A0",
          "#F8961E", "#023E8A", "#560BAD", "#3A86FF", "#FF006E"]

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
    ":ROUTIER": "Car LD",
}

TABLE_RENAME = {
    "type_court": "Type",
    "headsign": "N° Train",
    "departure_date_fmt": "Date",
    "departure": "Départ",
    "arrival": "Arrivée",
    "departure_time_fmt": "Heure Dép.",
    "arrival_time_fmt": "Heure Arr.",
}
TABLE_COLS = ["Type", "N° Train", "Date", "Départ", "Arrivée", "Heure Dép.", "Heure Arr."]


# ── Data loading with cache ──────────────────────────────────────────

_cache: dict = {"data": None, "ts": 0}

with open("france.geo.json", "r", encoding="utf-8") as _f:
    FRANCE_GEOJSON = json.load(_f)


def load_data() -> pd.DataFrame:
    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"].copy()

    try:
        conn = psycopg2.connect(
            user=os.getenv("user"),
            password=os.getenv("password"),
            host=os.getenv("host"),
            port=os.getenv("port"),
            dbname=os.getenv("dbname"),
        )
        query = """
            SELECT t.type, t.arrival, t.headsign, t.departure,
                   t.arrival_time, t.departure_date, t.departure_time,
                   g.nom, g.position_geographique
            FROM trains_supprimes t
            LEFT JOIN gares g ON t.arrival = g.nom
            WHERE departure_date >= '2023-01-01'
        """
        df = pd.read_sql(query, conn)
        conn.close()

        df["departure_date_dt"] = pd.to_datetime(df["departure_date"])
        df["departure_date_fmt"] = df["departure_date_dt"].dt.strftime("%d/%m/%Y")
        df["departure_time_fmt"] = pd.to_datetime(df["departure_time"]).dt.strftime("%H:%M")
        df["arrival_time_fmt"] = pd.to_datetime(df["arrival_time"]).dt.strftime("%H:%M")
        df["type_court"] = df["type"].map(TYPE_TRAIN_COURT).fillna(df["type"])

        _cache["data"] = df
        _cache["ts"] = now
        return df.copy()
    except Exception as exc:
        print(f"Erreur chargement PostgreSQL : {exc}")
        return pd.DataFrame()


data = load_data()


# ── Chart helpers ─────────────────────────────────────────────────────

ECHARTS_RESPONSIVE_PATCH = """
<style>html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:transparent}
body>div:first-child{width:100%!important;height:100%!important}</style>
<script>document.addEventListener('DOMContentLoaded',function(){
var ro=new ResizeObserver(function(){var el=document.querySelector('body>div:first-child');
if(el){var c=echarts.getInstanceByDom(el);if(c)c.resize();}});
ro.observe(document.body);});</script>
"""


def echarts_iframe(chart):
    html = chart.render_embed().replace("</body>", ECHARTS_RESPONSIVE_PATCH + "</body>")
    return ui.tags.iframe(
        srcdoc=html,
        style="width:100%;height:100%;border:none;min-height:400px;",
    )


def chart_init(height="375px"):
    return opts.InitOpts(width="100%", height=height, bg_color="transparent")


def chart_tooltip(trigger="axis"):
    return opts.TooltipOpts(
        trigger=trigger,
        background_color="rgba(255,255,255,0.97)",
        border_color="#E2E8F0",
        border_width=1,
        textstyle_opts=opts.TextStyleOpts(color="#2D3748"),
    )


def xaxis_opts(rotate=0):
    return opts.AxisOpts(
        axislabel_opts=opts.LabelOpts(rotate=rotate, color="#718096"),
        axisline_opts=opts.AxisLineOpts(linestyle_opts=opts.LineStyleOpts(color="#E2E8F0")),
        splitline_opts=opts.SplitLineOpts(is_show=False),
    )


def yaxis_opts():
    return opts.AxisOpts(
        axislabel_opts=opts.LabelOpts(color="#718096"),
        splitline_opts=opts.SplitLineOpts(
            linestyle_opts=opts.LineStyleOpts(color="#F1F5F9", type_="dashed")
        ),
    )


def empty_chart(msg="Aucune donnée pour cette période"):
    return ui.div(
        icon_svg("chart-area", width="44px", fill="#CBD5E0"),
        ui.p(msg, class_="text-muted mt-3 mb-0 small fw-medium"),
        class_="d-flex flex-column align-items-center justify-content-center h-100",
        style="padding:3rem 1rem;",
    )


def make_table(df, height="600px"):
    if df.empty:
        return render.DataTable(
            pd.DataFrame(columns=TABLE_COLS),
            filters=True, width="100%", height=height, summary=False,
        )
    return render.DataTable(
        df.rename(columns=TABLE_RENAME)[TABLE_COLS],
        filters=True, width="100%", height=height, summary=False,
    )


def card_icon_header(icon_name, label):
    return ui.card_header(
        ui.span(icon_svg(icon_name, width="14px", fill="currentColor"), " ", label)
    )


# ── UI ────────────────────────────────────────────────────────────────

CUSTOM_CSS = """
    html, body, .bslib-page-fill { overflow-y: auto !important; height: auto !important; }

    .card.bslib-card {
        border: 1px solid rgba(0,0,0,.05) !important;
        box-shadow: 0 1px 3px rgba(0,0,0,.04), 0 6px 24px rgba(0,0,0,.04) !important;
        border-radius: 12px !important;
        transition: box-shadow .2s ease;
    }
    .card.bslib-card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,.07), 0 12px 32px rgba(0,0,0,.08) !important;
    }
    .card.bslib-card .card-header {
        background: #F9FAFF !important;
        border-bottom: 1px solid rgba(67,97,238,.1) !important;
        font-weight: 600;
        font-size: .875rem;
        letter-spacing: .02em;
        color: #2D3748;
        border-radius: 12px 12px 0 0 !important;
        padding: .7rem 1.25rem;
    }
    .card.bslib-card .card-body { display: flex; flex-direction: column; }
    .card.bslib-card .card-body > .shiny-html-output {
        flex: 1; display: flex; flex-direction: column; min-height: 400px;
    }
    .card.bslib-card .card-body > .shiny-html-output > iframe { flex: 1; }

    .bslib-value-box {
        border-radius: 12px !important;
        border: none !important;
        box-shadow: 0 1px 3px rgba(0,0,0,.04), 0 6px 24px rgba(0,0,0,.06) !important;
    }

    .bslib-sidebar-layout > .sidebar {
        background: #F7F9FF !important;
        border-right: 1px solid #E8ECF8 !important;
    }

    .bslib-card .bslib-full-screen-enter { opacity: .3 !important; transition: opacity .2s; }
    .bslib-card:hover .bslib-full-screen-enter { opacity: .9 !important; }

    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: #F1F5F9; }
    ::-webkit-scrollbar-thumb { background: #CBD5E0; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

    label.control-label {
        font-size: .78rem; font-weight: 600; color: #4A5568;
        text-transform: uppercase; letter-spacing: .06em;
    }
    .nav-pills .nav-link { font-size: .85rem; font-weight: 500; }
    hr { border-color: #E8ECF8; }
    .navbar-brand { font-weight: 700; }
"""

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.div(
            ui.navset_pill(
                ui.nav_panel("Dashboard", value="dashboard"),
                ui.nav_panel("Données", value="donnees"),
                id="nav",
            ),
            class_="mb-3",
        ),
        ui.input_select(
            "type_train",
            "Type de train",
            choices={"": "Tous"}
            | {t: t for t in sorted(data["type_court"].dropna().unique())}
            if not data.empty
            else {"": "Tous"},
        ),
        ui.input_date_range(
            "date_range",
            "Période",
            start=pd.Timestamp.today(),
            end=pd.Timestamp.today(),
            format="dd/mm/yyyy",
            language="fr",
            separator=" au ",
            width="100%",
        ),
        ui.output_ui("special_day_buttons"),
        ui.output_ui("year_buttons"),
        ui.input_action_button(
            "refresh_data",
            "Rafraîchir les données",
            icon=icon_svg("arrows-rotate"),
            class_="btn btn-outline-secondary btn-sm w-100 mt-3",
        ),
        ui.hr(),
        ui.div(
            ui.a(
                icon_svg("database", width="12px"), " Source : data.gouv.fr",
                href="https://www.data.gouv.fr/fr/datasets/641b456a5374b1bdc9dce4cf",
                target="_blank",
                class_="text-muted small",
            ),
            class_="text-center",
        ),
        open="open",
        width="300px",
    ),
    ui.head_content(ui.tags.style(CUSTOM_CSS)),
    ui.output_ui("main_content"),
    title=ui.TagList(icon_svg("train"), " Trains Supprimés"),
    fillable=False,
    theme=shinyswatch.theme.lux,
)


# ── Server ────────────────────────────────────────────────────────────


def server(input, output, session):
    selected_period = reactive.Value("today")
    today_str = pd.Timestamp.today().strftime("%Y-%m-%d")
    tomorrow_str = (pd.Timestamp.today() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    # ── Reactive: filtered data ───────────────────────────────────────

    @reactive.calc
    def filtered_data():
        d = load_data()
        if d.empty:
            return d
        if input.type_train():
            d = d[d["type_court"] == input.type_train()]
        start, end = input.date_range()
        if not start or not end:
            start, end = pd.Timestamp("2024-01-01"), pd.Timestamp.today()
        return d[
            (d["departure_date_dt"] >= pd.to_datetime(start))
            & (d["departure_date_dt"] <= pd.to_datetime(end))
        ]

    # ── Refresh ───────────────────────────────────────────────────────

    @reactive.effect
    @reactive.event(input.refresh_data)
    def _refresh():
        _cache["ts"] = 0
        ui.notification_show("Données rafraîchies !", type="message", duration=3)

    # ── Charts ────────────────────────────────────────────────────────

    @render.ui
    def bar_chart():
        df = filtered_data()
        if df.empty:
            return empty_chart()
        counts = df["type_court"].value_counts()
        bar = (
            Bar(init_opts=chart_init())
            .add_xaxis(counts.index.tolist())
            .add_yaxis(
                "Suppressions", counts.values.tolist(),
                itemstyle_opts=opts.ItemStyleOpts(color=C_BLUE),
            )
            .set_global_opts(
                xaxis_opts=xaxis_opts(rotate=30),
                yaxis_opts=yaxis_opts(),
                tooltip_opts=chart_tooltip(),
                legend_opts=opts.LegendOpts(is_show=False),
            )
        )
        return echarts_iframe(bar)

    @render.ui
    def map_france():
        df = filtered_data()
        if df.empty or "position_geographique" not in df.columns:
            return empty_chart("Aucune donnée géographique")

        geo_df = df.dropna(subset=["position_geographique"]).copy()
        if geo_df.empty:
            return empty_chart("Aucune donnée géographique")

        coords = geo_df["position_geographique"].str.split(",", expand=True).astype(float)
        geo_df["lat"] = coords[0]
        geo_df["lon"] = coords[1]

        data_map = (
            geo_df.groupby("nom")
            .agg(count=("nom", "size"), lon=("lon", "first"), lat=("lat", "first"))
            .reset_index()
        )

        geo = Geo(init_opts=chart_init())
        geo.add_js_funcs(f"echarts.registerMap('France',{json.dumps(FRANCE_GEOJSON)})")
        geo.add_schema(
            maptype="France",
            itemstyle_opts=opts.ItemStyleOpts(color="#EEF2FF", border_color="#C7D2FE"),
            emphasis_label_opts=opts.LabelOpts(is_show=True),
        )
        for _, row in data_map.iterrows():
            geo.add_coordinate(row["nom"], row["lon"], row["lat"])
        geo.add(
            series_name="Suppressions",
            data_pair=list(zip(data_map["nom"], data_map["count"])),
            type_="effectScatter",
            symbol_size=8,
            label_opts=opts.LabelOpts(is_show=False),
        )
        geo.set_series_opts(effect_opts=opts.EffectOpts(scale=4))
        geo.set_global_opts(
            visualmap_opts=opts.VisualMapOpts(
                max_=int(data_map["count"].max()),
                is_piecewise=True,
                textstyle_opts=opts.TextStyleOpts(color="#4A5568"),
            ),
            legend_opts=opts.LegendOpts(is_show=False),
            tooltip_opts=chart_tooltip(trigger="item"),
        )
        return echarts_iframe(geo)

    @render.ui
    def pie_chart():
        df = filtered_data()
        if df.empty:
            return empty_chart()
        top = df["departure"].value_counts().head(10)
        pie = (
            Pie(init_opts=chart_init())
            .add(
                "Gares",
                [list(z) for z in zip(top.index.tolist(), top.values.tolist())],
                radius=["42%", "72%"],
                label_opts=opts.LabelOpts(formatter="{b}: {d}%", font_size=11),
            )
            .set_colors(C_PIE)
            .set_global_opts(
                legend_opts=opts.LegendOpts(
                    orient="vertical", pos_top="top", pos_right="0%",
                    textstyle_opts=opts.TextStyleOpts(color="#4A5568", font_size=11),
                ),
                tooltip_opts=chart_tooltip(trigger="item"),
            )
        )
        return echarts_iframe(pie)

    @render.ui
    def line_chart():
        df = filtered_data()
        if df.empty:
            return empty_chart()
        monthly = (
            df.groupby(df["departure_date_dt"].dt.to_period("M"))
            .size()
            .reset_index(name="count")
        )
        monthly["month"] = monthly["departure_date_dt"].dt.strftime("%m/%Y")
        line = (
            Line(init_opts=chart_init())
            .add_xaxis(monthly["month"].tolist())
            .add_yaxis(
                "Suppressions",
                monthly["count"].tolist(),
                is_smooth=True,
                color=C_BLUE,
                linestyle_opts=opts.LineStyleOpts(width=2.5, color=C_BLUE),
                areastyle_opts=opts.AreaStyleOpts(opacity=0.12, color=C_BLUE),
                itemstyle_opts=opts.ItemStyleOpts(color=C_BLUE),
            )
            .set_global_opts(
                xaxis_opts=xaxis_opts(rotate=45),
                yaxis_opts=yaxis_opts(),
                tooltip_opts=chart_tooltip(),
                legend_opts=opts.LegendOpts(is_show=False),
            )
        )
        return echarts_iframe(line)

    @render.ui
    def histo_heure():
        df = filtered_data()
        if df.empty or "departure_time_fmt" not in df.columns:
            return empty_chart()
        hours = pd.to_datetime(df["departure_time_fmt"], format="%H:%M", errors="coerce").dt.hour
        counts = hours.value_counts().sort_index()
        bar = (
            Bar(init_opts=chart_init())
            .add_xaxis([f"{h:02d}h" for h in counts.index])
            .add_yaxis(
                "Suppressions", counts.values.tolist(),
                itemstyle_opts=opts.ItemStyleOpts(color=C_TEAL),
            )
            .set_global_opts(
                xaxis_opts=xaxis_opts(),
                yaxis_opts=yaxis_opts(),
                tooltip_opts=chart_tooltip(),
                legend_opts=opts.LegendOpts(is_show=False),
            )
        )
        return echarts_iframe(bar)

    # ── KPIs ──────────────────────────────────────────────────────────

    @render.ui
    def kpi_total():
        count = filtered_data().shape[0]
        return ui.value_box(
            "Trains supprimés",
            f"{count:,}".replace(",", " "),
            showcase=icon_svg("train"),
            theme="primary",
        )

    @render.ui
    def kpi_gare_max():
        df = filtered_data()
        if df.empty:
            return ui.value_box(
                "Gare la + impactée", "—",
                showcase=icon_svg("location-dot"), theme="info",
            )
        top = df["departure"].value_counts()
        return ui.value_box(
            "Gare la + impactée",
            f"{top.idxmax()} ({top.max()})",
            showcase=icon_svg("location-dot"),
            theme="info",
        )

    @render.ui
    def kpi_taux():
        df = filtered_data()
        count = df.shape[0]
        days = max(df["departure_date_dt"].nunique(), 1) if not df.empty else 1
        taux = round(100 * count / (days * DAILY_TRAIN_ESTIMATE), 2)
        return ui.value_box(
            "Taux de suppression",
            f"{taux} %",
            showcase=icon_svg("percent"),
            theme="warning",
        )

    @render.ui
    def kpi_moyenne():
        df = filtered_data()
        val = (
            "—" if df.empty
            else f"{round(df.groupby('departure_date_dt').size().mean(), 1):,}".replace(",", " ")
        )
        return ui.value_box(
            "Moyenne / jour",
            str(val),
            showcase=icon_svg("chart-line"),
            theme="info",
        )

    # ── Tables ────────────────────────────────────────────────────────

    @render.data_frame
    def filtered_table():
        return make_table(filtered_data(), height="800px")

    @render.data_frame
    def table_jour():
        return make_table(filtered_data(), height="400px")

    # ── Download ──────────────────────────────────────────────────────

    @render.download(filename="trains_supprimes.csv")
    def download_csv():
        df = filtered_data()
        buf = io.BytesIO()
        buf.write(df.to_csv(index=False, sep=";").encode("utf-8-sig"))
        buf.seek(0)
        return buf

    # ── Main content (dynamic layout) ────────────────────────────────

    @render.ui
    def main_content():
        nav = input.nav()
        start, end = input.date_range()

        if nav == "dashboard":
            is_single_day = start == end

            if is_single_day:
                kpi_row = ui.row(
                    ui.column(4, ui.output_ui("kpi_total")),
                    ui.column(4, ui.output_ui("kpi_gare_max")),
                    ui.column(4, ui.output_ui("kpi_taux")),
                    class_="mb-3",
                )
                return ui.TagList(
                    kpi_row,
                    ui.row(
                        ui.column(6, ui.card(
                            card_icon_header("train", "Par type de train"),
                            ui.output_ui("bar_chart"),
                            full_screen=True,
                        )),
                        ui.column(6, ui.card(
                            card_icon_header("map", "Carte des suppressions"),
                            ui.output_ui("map_france"),
                            full_screen=True,
                        )),
                        class_="mb-3",
                    ),
                    ui.row(
                        ui.column(6, ui.card(
                            card_icon_header("clock", "Répartition horaire"),
                            ui.output_ui("histo_heure"),
                            full_screen=True,
                        )),
                        ui.column(6, ui.card(
                            card_icon_header("table", "Détail des trains"),
                            ui.output_data_frame("table_jour"),
                        )),
                    ),
                )
            else:
                kpi_row = ui.row(
                    ui.column(4, ui.output_ui("kpi_total")),
                    ui.column(4, ui.output_ui("kpi_moyenne")),
                    ui.column(4, ui.output_ui("kpi_taux")),
                    class_="mb-3",
                )
                return ui.TagList(
                    kpi_row,
                    ui.row(
                        ui.column(6, ui.card(
                            card_icon_header("train", "Par type de train"),
                            ui.output_ui("bar_chart"),
                            full_screen=True,
                        )),
                        ui.column(6, ui.card(
                            card_icon_header("chart-pie", "Top 10 gares de départ"),
                            ui.output_ui("pie_chart"),
                            full_screen=True,
                        )),
                        class_="mb-3",
                    ),
                    ui.row(
                        ui.column(6, ui.card(
                            card_icon_header("chart-line", "Tendance mensuelle"),
                            ui.output_ui("line_chart"),
                            full_screen=True,
                        )),
                        ui.column(6, ui.card(
                            card_icon_header("clock", "Répartition horaire"),
                            ui.output_ui("histo_heure"),
                            full_screen=True,
                        )),
                    ),
                )

        elif nav == "donnees":
            return ui.card(
                ui.card_header(
                    ui.div(
                        ui.span(
                            icon_svg("table", width="14px"),
                            " ",
                            ui.span("Tableau filtré", class_="fw-bold fs-5"),
                        ),
                        ui.download_button(
                            "download_csv",
                            ui.TagList(icon_svg("download", width="12px"), " Exporter CSV"),
                            class_="btn btn-sm btn-outline-primary",
                        ),
                        class_="d-flex align-items-center justify-content-between w-100",
                    )
                ),
                ui.output_data_frame("filtered_table"),
            )

    # ── Quick-date buttons ────────────────────────────────────────────

    SPECIAL_DAYS = [("today", "Aujourd'hui"), ("tomorrow", "Demain")]

    @render.ui
    def special_day_buttons():
        date_max_str = (
            data["departure_date_dt"].max().strftime("%Y-%m-%d")
            if not data.empty
            else today_str
        )
        demain_disabled = pd.to_datetime(date_max_str) < pd.to_datetime(tomorrow_str)

        buttons = []
        for key, label in SPECIAL_DAYS:
            is_active = selected_period.get() == key
            is_disabled = key == "tomorrow" and demain_disabled
            cls = "btn btn-sm me-1 mb-1 "
            cls += "btn-primary" if is_active else "btn-outline-secondary"
            buttons.append(
                ui.input_action_button(
                    f"special_{key}", label, class_=cls, disabled=is_disabled,
                )
            )
        return ui.div(*buttons, class_="d-flex justify-content-center mb-2")

    @render.ui
    def year_buttons():
        if data.empty:
            return ui.div()
        years = sorted(data["departure_date_dt"].dt.year.unique())
        buttons = []
        for y in years:
            is_active = selected_period.get() == y
            cls = "btn btn-sm me-1 mb-1 "
            cls += "btn-primary" if is_active else "btn-outline-secondary"
            buttons.append(ui.input_action_button(f"year_{y}", str(y), class_=cls))
        return ui.div(*buttons, class_="d-flex justify-content-center flex-wrap")

    # ── Year observers ────────────────────────────────────────────────

    def make_year_observer(year):
        @reactive.effect
        @reactive.event(input[f"year_{year}"])
        def _():
            selected_period.set(year)
            year_data = data[data["departure_date_dt"].dt.year == year]
            end_date = (
                year_data["departure_date_dt"].max().strftime("%Y-%m-%d")
                if not year_data.empty
                else f"{year}-12-31"
            )
            ui.update_date_range(
                "date_range", start=f"{year}-01-01", end=end_date, session=session,
            )

    if not data.empty:
        for yr in sorted(data["departure_date_dt"].dt.year.unique()):
            make_year_observer(yr)

    # ── Special-day observers ─────────────────────────────────────────

    @reactive.effect
    @reactive.event(input.special_today)
    def _set_today():
        selected_period.set("today")
        t = pd.Timestamp.today().strftime("%Y-%m-%d")
        ui.update_date_range("date_range", start=t, end=t, session=session)

    @reactive.effect
    @reactive.event(input.special_tomorrow)
    def _set_tomorrow():
        selected_period.set("tomorrow")
        t = (pd.Timestamp.today() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        ui.update_date_range("date_range", start=t, end=t, session=session)


app = App(app_ui, server)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)
