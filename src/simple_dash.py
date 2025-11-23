import os
import json
import dash  # Dash本体。Flask + React + Plotly をまとめたフレームワーク
from dash import html, dcc, Input, Output, State  # html: HTMLタグ, dcc: Dash Core Components, Input/Output/State: コールバックの入出力宣言
import plotly.graph_objs as go
from datetime import datetime


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


def parse_time(value):
    """Parse time field to a float timestamp (None on failure)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value
        if "T" in s:
            try:
                return datetime.fromisoformat(s).timestamp()
            except ValueError:
                # truncate fractional seconds to 6 digits if longer
                try:
                    if "." in s:
                        base, frac = s.split(".", 1)
                        frac_digits = "".join(ch for ch in frac if ch.isdigit())
                        frac_adj = (frac_digits[:6]).ljust(6, "0")
                        return datetime.fromisoformat(f"{base}.{frac_adj}").timestamp()
                except Exception:
                    return None
            except Exception:
                return None
        try:
            return float(s)
        except Exception:
            return None
    return None


# ----------------------------------------
# Dash アプリ本体の生成
# ----------------------------------------
app = dash.Dash(__name__)

# ======================================================
# layout = 画面に「何をどう配置するか」を定義する部分
# ======================================================
app.layout = html.Div([
    # dcc.Store: クライアントサイドの軽量ストレージ。ページリロードしない限り値を保持できる。
    # ここでは選択中ファイル/ run_id/ そのrun_idの時刻/ ファイル更新バージョンを保存し、コールバック間で共有する。
    dcc.Store(id="selected-file"),
    dcc.Store(id="selected-run-id"),
    dcc.Store(id="selected-run-id-time"),
    dcc.Store(id="selected-file-version", data={"version": 0, "mtime": None}),
    dcc.Store(id="sidebar-collapsed", data=False),
    # dcc.Interval: 一定間隔でイベントを発火させるコンポーネント。自動更新用に利用。
    dcc.Interval(id="auto-refresh-interval", interval=2000, disabled=True),

    # html.Div: HTMLのdiv要素。styleでCSS指定し、childrenで中に入れるコンポーネントを列挙する。
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
                id="sidebar",
                style={
                    "width": "19%",
                    "minWidth": "180px",
                    "backgroundColor": "#1a1a1a",
                    "padding": "10px",
                    "border": "1px solid #333",
                    "borderRadius": "6px",
                    "transition": "all 0.25s ease",
                },
                children=[
                    html.Div(
                        html.Button(
                            "≡",
                            id="toggle-sidebar",
                            n_clicks=0,
                            style={
                                "padding": "4px 8px",
                                "cursor": "pointer",
                                "border": "1px solid #333",
                                "backgroundColor": "#222",
                                "color": "#eee",
                            },
                        ),
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "flex-end",
                            "gap": "6px",
                            "marginBottom": "8px",
                        },
                    ),
                    html.Div(
                        id="sidebar-content",
                        children=[
                            html.H2("Graph View"),  # タイトル
                            html.Div(
                                html.Button("自動更新", id="auto-refresh", n_clicks=0),
                                style={"marginBottom": "8px"},
                            ),
                            html.Div([
                                # ログディレクトリの入力
                                html.Div("log Path", style={"fontWeight": "bold", "marginTop": "10px"}),
                                # dcc.Input: ユーザーがテキストを入力するフィールド（valueがコールバックの入力に使われる）
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
                                # .jsonl ファイルの一覧（mtime 降順）
                                html.Div("file list", style={"fontWeight": "bold", "marginTop": "10px"}),
                                # html.Div 内で動的に子要素を差し替える。子要素には id={"type":"jsonl-item",...} のDivを入れる。
                                html.Div(id="file-list", style={"marginTop": "4px", "fontSize": "14px"}),
                            ]),
                            html.Div([
                                # run_end から抽出した run_id 一覧（time 新しい順）
                                html.Div("run id list", style={"fontWeight": "bold", "marginTop": "10px"}),
                                html.Div(id="runid-list", style={"marginTop": "4px", "fontSize": "14px"}),
                            ]),
                        ],
                    ),
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
                    # dcc.Graph: Plotly図を描画するコンポーネント。figureはPlotlyのFigureを渡す。
                    dcc.Graph(
                        id="detail-graph",
                        style={"height": "340px", "margin": "0"},
                        figure=build_fig(),
                    ),
                    # ファイル内容（run_id 選択時はフィルタリング）
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
    """
    ログパスの .jsonl を mtime 新しい順に並べ、クリック可能なリストで返す。
    Dashのコールバックは「Outputをどう埋めるか」を定義する関数。
    Input/Stateの値が変わるとこの関数が呼ばれ、返り値がOutputに反映される。
    """
    if not path:
        return "パスを入力するとファイル一覧を表示します。"
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        return f"存在しないパスです: {abs_path}"
    if not os.path.isdir(abs_path):
        return f"ディレクトリを指定してください: {abs_path}"

    try:
        candidates = [e for e in os.listdir(abs_path) if e.endswith(".jsonl")]
        entries = sorted(
            candidates,
            key=lambda name: os.path.getmtime(os.path.join(abs_path, name)),
            reverse=True,
        )
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
    """
    ファイルクリック or run_id 変更で発火。
    - ファイルを選択したら内容を表示し、selected-file を更新。
    - run_id が選択されていれば、その run_id の行だけを表示し、同じデータでグラフ描画。
    DashのInput/Outputは宣言的: Outputで指定したコンポーネント属性を、この関数の返り値で置き換える。
    Stateは「監視はしないが現在値を読みたい」入力。
    """
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
    Input("selected-file-version", "data"),
)
def update_runid_list(selected_path, selected_run_id, _version):
    """選択中ファイルの run_end から run_id を抽出し、time 新しい順で表示。_version は監視用ダミー。"""
    if not selected_path or not os.path.isfile(selected_path):
        return ""

    run_times = {}
    try:
        with open(selected_path, "r") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") == "run_end" and "run_id" in obj:
                    rid = obj.get("run_id")
                    t_val = parse_time(obj.get("time"))
                    prev = run_times.get(rid)
                    if prev is None or (t_val is not None and (prev is None or t_val > prev)):
                        run_times[rid] = t_val
    except Exception as e:
        return f"run_id抽出に失敗しました: {e}"

    if not run_times:
        return "run_end の run_id が見つかりません。"

    # sort by time desc (None is treated as oldest)
    sorted_run_ids = [
        rid for rid, _ in sorted(
            run_times.items(),
            key=lambda kv: kv[1] if kv[1] is not None else float("-inf"),
            reverse=True,
        )
    ]

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
        for rid in sorted_run_ids
    ]


@app.callback(
    Output("selected-run-id", "data"),
    Output("selected-run-id-time", "data"),
    Input({"type": "runid-item", "runid": dash.dependencies.ALL}, "n_clicks"),
    Input("selected-file-version", "data"),
    State("selected-run-id", "data"),
    State("selected-file", "data"),
    prevent_initial_call=True,
)
def select_run_id(n_clicks, _version, current_selected, selected_file):
    """
    run_id をクリックしたら選択/解除。自動更新でファイルが変わった場合、最新の run_id に自動で切り替え。
    """
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update

    # ユーザークリックか自動更新かを判断
    triggered_id = ctx.triggered_id

    # ユーティリティ: ファイルから run_end 時刻を辞書で返す
    def load_run_times(path):
        times = {}
        if not path or not os.path.isfile(path):
            return times
        try:
            with open(path, "r") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if obj.get("type") == "run_end" and "run_id" in obj:
                        rid = obj.get("run_id")
                        t_val = parse_time(obj.get("time"))
                        prev = times.get(rid)
                        if prev is None or (t_val is not None and (prev is None or t_val > prev)):
                            times[rid] = t_val
        except Exception:
            return times
        return times

    run_times = load_run_times(selected_file)

    # クリック時の処理
    if isinstance(triggered_id, dict):
        rid = triggered_id.get("runid")
        if not rid:
            return dash.no_update, dash.no_update
        if rid == current_selected:
            return None, None  # トグル解除
        return rid, run_times.get(rid)

    # 自動更新（selected-file-version）の場合
    if not run_times:
        return dash.no_update, dash.no_update

    # 現在選択の時刻
    current_time = run_times.get(current_selected)

    # 最新の run_id を探す（time 最大）
    latest_rid = None
    latest_time = None
    for rid, t in run_times.items():
        if latest_time is None or (t is not None and (latest_time is None or t > latest_time)):
            latest_rid = rid
            latest_time = t

    # 新しい run_id が増えた/より新しい場合のみ切り替え
    if latest_rid and (current_selected is None or current_time is None or (latest_time is not None and latest_time > current_time)):
        return latest_rid, latest_time

    return dash.no_update, dash.no_update


@app.callback(
    Output("auto-refresh", "children"),
    Output("auto-refresh", "style"),
    Output("auto-refresh-interval", "disabled"),
    Input("auto-refresh", "n_clicks"),
)
def toggle_auto_refresh(n_clicks):
    """自動更新ボタンの ON/OFF 表示と Interval の有効/無効を切り替え。"""
    on = bool(n_clicks and n_clicks % 2 == 1)
    label = "自動更新 ON" if on else "自動更新 OFF"
    base_style = {
        "padding": "6px 10px",
        "border": "1px solid #333",
        "borderRadius": "4px",
        "cursor": "pointer",
        "backgroundColor": "#2f6eff" if on else "#222",
        "color": "#fff" if on else "#eee",
    }
    return label, base_style, (not on)


@app.callback(
    Output("selected-file-version", "data"),
    Input("auto-refresh-interval", "n_intervals"),
    State("selected-file", "data"),
    State("selected-file-version", "data"),
)
def refresh_selected_file_version(_, selected_file, current):
    """
    自動更新が ON のときだけ走る。
    選択ファイルの mtime が変わったら version をインクリメントし、run_id リストを更新させる。
    """
    if not selected_file or not os.path.isfile(selected_file):
        return dash.no_update

    try:
        mtime = os.path.getmtime(selected_file)
    except OSError:
        return dash.no_update

    current = current or {"version": 0, "mtime": None}
    if current.get("mtime") == mtime:
        return dash.no_update

    return {"version": current.get("version", 0) + 1, "mtime": mtime}

# ---- サイドバー表示切替 ----
@app.callback(
    Output("sidebar", "style"),
    Output("sidebar-content", "style"),
    Output("toggle-sidebar", "children"),
    Input("toggle-sidebar", "n_clicks"),
)
def toggle_sidebar(n):
    """
    サイドバーの表示/非表示を切り替える。ボタンは常に右上に残し、コンテンツのみ畳む。
    """
    base_style = {
        "width": "19%",
        "minWidth": "180px",
        "backgroundColor": "#1a1a1a",
        "padding": "10px",
        "border": "1px solid #333",
        "borderRadius": "6px",
        "transition": "all 0.25s ease",
    }
    collapsed = bool(n and n % 2 == 1)
    if collapsed:
        content_style = {"display": "none"}
        collapsed_style = {
            "width": "46px",
            "minWidth": "46px",
            "backgroundColor": "#1a1a1a",
            "padding": "8px",
            "border": "1px solid #333",
            "borderRadius": "6px",
            "transition": "all 0.25s ease",
        }
        return collapsed_style, content_style, "▶"

    content_style = {"display": "block"}
    return base_style, content_style, "≡"


# ======================================================
# 実行エントリポイント
# ======================================================
if __name__ == "__main__":
    app.run(debug=True)
