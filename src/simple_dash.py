import os
import json
import dash
from dash import html, dcc, Input, Output, State
import plotly.graph_objs as go


def build_fig(xs=None, ys=None, title=None):
    """Build a scatter-only figure with consistent dark styling."""
    fig = go.Figure()
    fig.update_layout(
        height=300,
        margin=dict(l=10, r=6, t=40, b=12),
        title=title or None,
        template="plotly_dark",
        paper_bgcolor="#1a1a1a",
        plot_bgcolor="#111",
        xaxis_title="line",
        yaxis_title="d Y",
    )
    if xs and ys:
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", name="elapsed_ms"))
    return fig


# ----------------------------------------
# Dash アプリ本体の生成
# ----------------------------------------
app = dash.Dash(__name__)

# ======================================================
# layout = 画面に「何をどう配置するか」を定義する部分
# ======================================================
app.layout = html.Div([
    dcc.Store(id="selected-file"),
    dcc.Store(id="selected-run-id"),

    html.Div(
        style={
            "display": "flex",
            "gap": "20px",
            "backgroundColor": "#111",
            "color": "#eee",
            "minHeight": "100vh",
            "padding": "16px",
        },
        children=[
            # 左カラム: 入力とリスト類
            html.Div(
                style={
                    "width": "19%",
                    "minWidth": "180px",
                    "backgroundColor": "#1a1a1a",
                    "padding": "10px",
                    "border": "1px solid #333",
                    "borderRadius": "6px",
                },
                children=[
                    html.H2("Dash Test"),
                    html.Div([
                        html.Div("log Path", style={"fontWeight": "bold", "marginTop": "10px"}),
                        dcc.Input(
                            id="text",
                            value="./logs",
                            type="text",
                            style={
                                "padding": "4px",
                                "border": "1px solid #444",
                                "marginBottom": "4px",
                                "fontSize": "16px",
                                "backgroundColor": "#222",
                                "color": "#eee",
                            },
                        ),
                    ]),
                    html.Div([
                        html.Div("file list", style={"fontWeight": "bold", "marginTop": "10px"}),
                        html.Div(id="file-list", style={"marginTop": "4px", "fontSize": "16px"}),
                    ]),
                    html.Div([
                        html.Div("run id list", style={"fontWeight": "bold", "marginTop": "10px"}),
                        html.Div(id="runid-list", style={"marginTop": "4px", "fontSize": "16px"}),
                    ]),
                ]
            ),
            # 右カラム: グラフ＋ファイル内容
            html.Div(
                style={
                    "flex": "1",
                    "backgroundColor": "#1a1a1a",
                    "padding": "10px",
                    "border": "1px solid #333",
                    "borderRadius": "6px",
                },
                children=[
                    dcc.Graph(
                        id="detail-graph",
                        style={"height": "340px", "margin": "0"},
                        figure=build_fig(),
                    ),
                    html.Div("ファイル内容", style={"fontWeight": "bold", "marginTop": "10px"}),
                    dcc.Textarea(
                        id="file-content",
                        style={
                            "width": "100%",
                            "height": "300px",
                            "whiteSpace": "pre",
                            "backgroundColor": "#111",
                            "color": "#eee",
                            "border": "1px solid #333",
                        },
                        readOnly=True,
                    ),
                ]
            ),
        ]
    )
])


# 3) パス直下のファイル一覧を表示する callback
@app.callback(
    Output("file-list", "children"),
    Input("text", "value"),
    Input("selected-file", "data"),
    prevent_initial_call=False,
)
def show_files(path, selected_path):
    if not path:
        return "パスを入力するとファイル一覧を表示します。"
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return f"存在しないパスです: {abs_path}"
    if not os.path.isdir(abs_path):
        return f"ディレクトリを指定してください: {abs_path}"

    try:
        entries = [e for e in sorted(os.listdir(abs_path)) if e.endswith(".jsonl")]
    except Exception as e:
        return f"読み取りに失敗しました: {e}"

    if not entries:
        return f"jsonlファイルがありません: {abs_path}"

    return [
        html.Div(
            e,
            id={"type": "jsonl-item", "path": os.path.join(abs_path, e)},
            n_clicks=0,
            style={
                "padding": "6px",
                "border": "1px solid #333",
                "marginBottom": "4px",
                "cursor": "pointer",
                "borderRadius": "4px",
                "backgroundColor": "#2f6eff" if os.path.join(abs_path, e) == selected_path else "#181818",
                "color": "#fff" if os.path.join(abs_path, e) == selected_path else "#eee",
            }
        )
        for e in entries
    ]


@app.callback(
    Output("file-content", "value"),
    Output("selected-file", "data"),
    Output("detail-graph", "figure"),
    Input({"type": "jsonl-item", "path": dash.dependencies.ALL}, "n_clicks"),
    Input("selected-run-id", "data"),
    State("selected-file", "data"),
    prevent_initial_call=True,
)
def show_file_content(n_clicks, selected_run_id, current_file):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, build_fig()

    trig = ctx.triggered_id
    triggered_by_run = trig == "selected-run-id"

    path = None
    new_selected = dash.no_update

    if triggered_by_run:
        path = current_file
    else:
        # ファイルクリック時
        if not n_clicks or all((c is None or c == 0) for c in n_clicks):
            return dash.no_update, dash.no_update, build_fig()
        if isinstance(trig, dict):
            path = trig.get("path")
        else:
            try:
                path = json.loads(ctx.triggered[0]["prop_id"].split(".")[0]).get("path")
            except Exception:
                return dash.no_update, dash.no_update, build_fig()
        new_selected = path

    if not path or not os.path.isfile(path):
        return dash.no_update, dash.no_update, build_fig()

    try:
        with open(path, "r") as f:
            lines = f.readlines()
    except Exception as e:
        return f"読み取りに失敗しました: {e}", new_selected, build_fig()

    if selected_run_id:
        filtered = []
        xs = []
        ys = []
        for line in lines:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("run_id") == selected_run_id:
                filtered.append(line.rstrip("\n"))
                if "frame_id" in obj and "elapsed_ms" in obj:
                    xs.append(obj.get("frame_id"))
                    ys.append(obj.get("elapsed_ms"))
        content = "\n".join(filtered) if filtered else "選択した run_id の行はありません。"
        fig = build_fig(xs, ys, title=f"{os.path.basename(path)} / run_id={selected_run_id}" if xs and ys else None)
    else:
        content = "".join(lines)
        fig = build_fig()

    return content, new_selected, fig


@app.callback(
    Output("runid-list", "children"),
    Input("selected-file", "data"),
    Input("selected-run-id", "data"),
)
def update_runid_list(selected_path, selected_run_id):
    if not selected_path or not os.path.isfile(selected_path):
        return ""

    run_ids = []
    try:
        with open(selected_path, "r") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") == "run_end" and "run_id" in obj:
                    rid = obj.get("run_id")
                    if rid not in run_ids:
                        run_ids.append(rid)
    except Exception as e:
        return f"run_id抽出に失敗しました: {e}"

    if not run_ids:
        return "run_end の run_id が見つかりません。"

    return [
        html.Div(
            rid,
            id={"type": "runid-item", "runid": rid},
            n_clicks=0,
            style={
                "padding": "6px",
                "border": "1px solid #333",
                "marginBottom": "4px",
                "cursor": "pointer",
                "borderRadius": "4px",
                "backgroundColor": "#2f6eff" if rid == selected_run_id else "#181818",
                "color": "#fff" if rid == selected_run_id else "#eee",
            },
        )
        for rid in run_ids
    ]


@app.callback(
    Output("selected-run-id", "data"),
    Input({"type": "runid-item", "runid": dash.dependencies.ALL}, "n_clicks"),
    State("selected-run-id", "data"),
    prevent_initial_call=True,
)
def select_run_id(n_clicks, current_selected):
    ctx = dash.callback_context
    if not ctx.triggered or not n_clicks or all((c is None or c == 0) for c in n_clicks):
        return dash.no_update

    trig = ctx.triggered_id
    if isinstance(trig, dict):
        rid = trig.get("runid")
    else:
        try:
            rid = json.loads(ctx.triggered[0]["prop_id"].split(".")[0]).get("runid")
        except Exception:
            return dash.no_update

    if not rid:
        return dash.no_update

    # 同じ run_id を再クリックしたら選択解除
    if rid == current_selected:
        return None

    return rid


# ======================================================
# 実行エントリポイント
# ======================================================
if __name__ == "__main__":
    app.run(debug=True)
