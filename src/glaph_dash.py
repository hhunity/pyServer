import dash
from dash import html, dcc, Input, Output
import plotly.graph_objs as go
import pandas as pd
import json
import os

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))

def load_runcodes():
    """logs 内の jsonl ファイル名一覧を返す（例：test123.jsonl）"""
    if not os.path.isdir(LOG_DIR):
        return []
    return sorted([f for f in os.listdir(LOG_DIR) if f.endswith(".jsonl")])

def load_log(path):
    """JSONL を DataFrame に変換"""
    rows = []
    with open(path, "r") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except:
                pass
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame()

def extract_run_ids(df: pd.DataFrame):
    """type == run_end の run_id をユニークに抽出"""
    if df.empty:
        return []
    run_end_rows = df[df.get("type") == "run_end"]
    if run_end_rows.empty:
        return []
    ids = run_end_rows.get("run_id", pd.Series(dtype=object)).dropna().unique().tolist()
    return ids

# Dash アプリ作成
app = dash.Dash(__name__)

app.layout = html.Div(style={"display": "flex"}, children=[

    dcc.Store(id="selected-file"),
    dcc.Store(id="selected-run-id"),

    # --------------------
    # 左側 RunCode / RunID 一覧
    # --------------------
    html.Div(style={"width": "25%", "padding": "10px", "border-right": "1px solid #ccc"}, children=[
        html.H3("RunCode List"),
        dcc.Interval(id="interval_list", interval=2000, n_intervals=0),
        html.Div(id="runcode-list"),
        html.Hr(),
        html.H4("run_id List"),
        html.Div(id="runid-list"),
    ]),

    # --------------------
    # 右側 グラフエリア
    # --------------------
    html.Div(style={"flex-grow": "1", "padding": "10px"}, children=[
        html.H3("Latest Graph"),
        dcc.Graph(
            id="main-graph",
            style={"height": "60vh", "minHeight": "320px"}
        ),
    ]),
])

# RunCode 一覧更新
@app.callback(
    Output("runcode-list", "children"),
    Input("interval_list", "n_intervals")
)

def update_runcode_list(_):
    print("[DEBUG] update_runcode_list triggered")
    print("[DEBUG] LOG_DIR =", LOG_DIR)
    print("[DEBUG] dir exists =", os.path.isdir(LOG_DIR))
    files = load_runcodes()
    return [
        html.Div(
            f,
            id={"type": "runcode-item", "index": f},
            n_clicks=0,
            style={
                "padding": "5px",
                "border": "1px solid #aaa",
                "margin-bottom": "5px",
                "cursor": "pointer"
            }
        ) for f in files
    ]


@app.callback(
    Output("selected-file", "data"),
    Input({"type": "runcode-item", "index": dash.dependencies.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_file(n_clicks):
    ctx = dash.callback_context

    if not ctx.triggered or not n_clicks or all((c is None or c == 0) for c in n_clicks):
        return dash.no_update

    triggered_id = ctx.triggered_id
    if isinstance(triggered_id, dict):
        filename = triggered_id.get("index")
    else:
        try:
            triggered_raw = ctx.triggered[0]["prop_id"].split(".")[0]
            filename = json.loads(triggered_raw).get("index")
        except Exception:
            return dash.no_update

    if not filename:
        return dash.no_update

    return filename


@app.callback(
    Output("runid-list", "children"),
    Output("selected-run-id", "data"),
    Input("selected-file", "data"),
)
def update_runid_list(selected_filename):
    if not selected_filename:
        return [], None

    df = load_log(os.path.join(LOG_DIR, selected_filename))
    run_ids = extract_run_ids(df)
    if not run_ids:
        return [html.Div("run_id not found", style={"color": "#888"})], None

    return [
        html.Div(
            rid,
            id={"type": "runid-item", "index": rid},
            n_clicks=0,
            style={
                "padding": "5px",
                "border": "1px solid #aaa",
                "margin-bottom": "5px",
                "cursor": "pointer"
            }
        ) for rid in run_ids
    ], None


@app.callback(
    Output("selected-run-id", "data"),
    Input({"type": "runid-item", "index": dash.dependencies.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_run_id(n_clicks):
    ctx = dash.callback_context

    if not ctx.triggered or not n_clicks or all((c is None or c == 0) for c in n_clicks):
        return dash.no_update

    triggered_id = ctx.triggered_id
    if isinstance(triggered_id, dict):
        rid = triggered_id.get("index")
    else:
        try:
            triggered_raw = ctx.triggered[0]["prop_id"].split(".")[0]
            rid = json.loads(triggered_raw).get("index")
        except Exception:
            return dash.no_update

    if not rid:
        return dash.no_update

    return rid


# RunCode クリック時にグラフ更新
@app.callback(
    Output("main-graph", "figure"),
    Input("selected-file", "data"),
    Input("selected-run-id", "data"),
)
def update_graph(selected_filename, selected_run_id):
    def empty_fig():
        fig = go.Figure()
        fig.update_layout(height=500)
        return fig

    if not selected_filename or not selected_run_id:
        return empty_fig()

    df = load_log(os.path.join(LOG_DIR, selected_filename))
    if df.empty:
        return empty_fig()

    # run_id で絞り込み
    df = df[(df.get("type") == "frame_result") & (df.get("run_id") == selected_run_id)]
    if df.empty:
        return empty_fig()

    x = df.get("frame_id", [])
    y = df.get("elapsed_ms", [])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name="elapsed_ms"))

    fig.update_layout(title=f"Graph: {selected_filename} / run_id={selected_run_id}", height=500)

    return fig


if __name__ == "__main__":
    app.run(debug=False)
