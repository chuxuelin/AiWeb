import datetime as dt
from decimal import Decimal

import flask
from werkzeug.security import check_password_hash, generate_password_hash

import db

app = flask.Flask(__name__, template_folder="templates")
app.secret_key = "health-demo-secret"


# ----------------------------------------------------------------------
# 辅助函数
# ----------------------------------------------------------------------
def api_error(message, status=400):
    return flask.jsonify({"ok": False, "message": message}), status


def login_required():
    return flask.session.get("user_id") is not None


def to_jsonable(value):
    """把 MySQL 返回的 Decimal/date/datetime 转成可 JSON 序列化的类型。"""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def serialize(row):
    return {key: to_jsonable(val) for key, val in row.items()}


def trend_percent(today, yesterday):
    """与昨日对比, 返回如 '+8%' / '-2%' / '+0%'。"""
    try:
        today = float(today)
        yesterday = float(yesterday)
    except (TypeError, ValueError):
        return "+0%"
    if not yesterday:
        return "+0%"
    percent = round((today - yesterday) / yesterday * 100)
    return f"+{percent}%" if percent >= 0 else f"{percent}%"


# ----------------------------------------------------------------------
# 页面路由
# ----------------------------------------------------------------------
@app.route("/")
@app.route("/login")
@app.route("/dashboard")
def index():
    return flask.render_template("base.html")


@app.route("/admin")
def admin_page():
    return flask.render_template("admin.html")


# ----------------------------------------------------------------------
# 认证 API
# ----------------------------------------------------------------------
@app.get("/api/auth")
def auth_state():
    logged_in = login_required()
    return flask.jsonify({
        "authenticated": logged_in,
        "user": {"email": flask.session.get("username")} if logged_in else None,
    })


@app.post("/api/login")
def login_api():
    payload = flask.request.get_json(silent=True) or {}
    username = str(payload.get("email", "")).strip()
    password = str(payload.get("password", ""))

    user = db.fetch_one(
        "SELECT * FROM users WHERE username = %s", (username,)
    )
    if not user or not check_password_hash(user["password_hash"], password):
        return api_error("账号或密码错误，请使用测试账号：admin / 123", 401)

    flask.session["user_id"] = user["id"]
    flask.session["username"] = user["username"]
    flask.session["name"] = user["name"]
    return flask.jsonify({"ok": True, "user": {"email": user["username"]}})


@app.post("/api/logout")
def logout_api():
    flask.session.clear()
    return flask.jsonify({"ok": True})


# ----------------------------------------------------------------------
# 仪表盘 API (从 MySQL 聚合)
# ----------------------------------------------------------------------
def _build_metrics(today_row, yesterday_row):
    """把每日记录转换成前端 metrics 卡片数组。"""
    yesterday_row = yesterday_row or {}

    def val(row, key, default=0):
        return row.get(key, default) if row else default

    return [
        {"key": "steps", "title": "步数", "value": int(val(today_row, "steps")),
         "unit": "步", "trend": trend_percent(val(today_row, "steps"), val(yesterday_row, "steps")),
         "tone": "up", "note": "同步微信运动数据", "sync": True},
        {"key": "heartRate", "title": "心率", "value": int(val(today_row, "heart_rate")),
         "unit": "", "trend": trend_percent(val(today_row, "heart_rate"), val(yesterday_row, "heart_rate")),
         "tone": "up", "note": "BPM / 正常范围"},
        {"key": "sleep", "title": "睡眠", "value": float(val(today_row, "sleep_hours")),
         "unit": "h", "trend": trend_percent(val(today_row, "sleep_hours"), val(yesterday_row, "sleep_hours")),
         "tone": "up", "note": "深度睡眠 2.1h"},
        {"key": "calories", "title": "热量消耗", "value": int(val(today_row, "calories")),
         "unit": "", "trend": trend_percent(val(today_row, "calories"), val(yesterday_row, "calories")),
         "tone": "up", "note": "KCAL / 今日"},
        {"key": "water", "title": "水分摄入", "value": float(val(today_row, "water_liters")),
         "unit": "L", "trend": trend_percent(val(today_row, "water_liters"), val(yesterday_row, "water_liters")),
         "tone": "down", "note": "目标 2.2L"},
    ]


@app.get("/api/dashboard")
def dashboard_api():
    if not login_required():
        return api_error("请先登录", 401)

    user_id = flask.session["user_id"]
    today = dt.date.today()

    user = db.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
    today_row = db.fetch_one(
        "SELECT * FROM daily_health WHERE user_id = %s AND record_date = %s",
        (user_id, today),
    )
    yesterday_row = db.fetch_one(
        "SELECT * FROM daily_health WHERE user_id = %s AND record_date = %s",
        (user_id, today - dt.timedelta(days=1)),
    )

    # 近7天体适能趋势
    week_rows = db.fetch_all(
        """SELECT record_date, fitness_score FROM daily_health
           WHERE user_id = %s AND record_date >= %s
           ORDER BY record_date ASC""",
        (user_id, today - dt.timedelta(days=6)),
    )
    score_by_date = {row["record_date"]: row["fitness_score"] for row in week_rows}
    chart = [int(score_by_date.get(today - dt.timedelta(days=6 - i), 0)) for i in range(7)]

    tasks = [serialize(row) for row in db.fetch_all(
        "SELECT id, title, detail, status, tone FROM health_tasks WHERE user_id = %s ORDER BY id",
        (user_id,),
    )]
    insights = [serialize(row) for row in db.fetch_all(
        "SELECT id, title, text FROM health_insights WHERE user_id = %s ORDER BY id",
        (user_id,),
    )]

    today_row = today_row or {}
    return flask.jsonify({
        "user": {"name": user["name"], "email": user["username"], "level": user["level"]},
        "summary": {
            "fitness": int(today_row.get("fitness_score", 0)),
            "message": today_row.get("summary_message") or "今日暂无健康记录，请在后台添加。",
        },
        "metrics": _build_metrics(today_row, yesterday_row),
        "hero": {
            "steps": int(today_row.get("steps", 0)),
            "sleepQuality": int(today_row.get("sleep_quality", 0)),
            "exerciseMinutes": int(today_row.get("exercise_minutes", 0)),
        },
        "chart": chart,
        "tasks": tasks,
        "insights": insights,
    })


@app.post("/api/sync-steps")
def sync_steps_api():
    """微信扫码同步: 今日步数 +140 并持久化到数据库。"""
    if not login_required():
        return api_error("请先登录", 401)

    user_id = flask.session["user_id"]
    today = dt.date.today()
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO daily_health (user_id, record_date, steps)
               VALUES (%s, %s, 140)
               ON DUPLICATE KEY UPDATE steps = steps + 140""",
            (user_id, today),
        )
        cur.execute(
            "SELECT steps FROM daily_health WHERE user_id = %s AND record_date = %s",
            (user_id, today),
        )
        steps = cur.fetchone()["steps"]
    return flask.jsonify({"ok": True, "steps": int(steps)})


# ----------------------------------------------------------------------
# 后台管理 API —— 用户管理
# ----------------------------------------------------------------------
@app.get("/api/admin/users")
def admin_list_users():
    if not login_required():
        return api_error("请先登录", 401)
    rows = db.fetch_all(
        "SELECT id, username, name, email, level, created_at FROM users ORDER BY id"
    )
    return flask.jsonify({"ok": True, "data": [serialize(r) for r in rows]})


@app.post("/api/admin/users")
def admin_create_user():
    if not login_required():
        return api_error("请先登录", 401)
    payload = flask.request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    name = str(payload.get("name", "")).strip() or username
    if not username or not password:
        return api_error("账号和密码不能为空")
    if db.fetch_one("SELECT id FROM users WHERE username = %s", (username,)):
        return api_error("账号已存在")
    user_id = db.execute(
        "INSERT INTO users (username, password_hash, name, email, level) VALUES (%s,%s,%s,%s,%s)",
        (username, generate_password_hash(password), name,
         payload.get("email"), payload.get("level", "普通用户")),
    )
    return flask.jsonify({"ok": True, "id": user_id})


@app.put("/api/admin/users/<int:user_id>")
def admin_update_user(user_id):
    if not login_required():
        return api_error("请先登录", 401)
    payload = flask.request.get_json(silent=True) or {}
    fields, params = [], []
    for column in ("name", "email", "level"):
        if column in payload:
            fields.append(f"{column} = %s")
            params.append(payload[column])
    if payload.get("password"):
        fields.append("password_hash = %s")
        params.append(generate_password_hash(str(payload["password"])))
    if not fields:
        return api_error("没有需要更新的字段")
    params.append(user_id)
    db.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", tuple(params))
    return flask.jsonify({"ok": True})


@app.delete("/api/admin/users/<int:user_id>")
def admin_delete_user(user_id):
    if not login_required():
        return api_error("请先登录", 401)
    if user_id == flask.session.get("user_id"):
        return api_error("不能删除当前登录账号")
    db.execute("DELETE FROM users WHERE id = %s", (user_id,))
    return flask.jsonify({"ok": True})


# ----------------------------------------------------------------------
# 后台管理 API —— 每日健康记录
# ----------------------------------------------------------------------
RECORD_FIELDS = [
    "record_date", "steps", "heart_rate", "sleep_hours", "calories",
    "water_liters", "sleep_quality", "exercise_minutes", "fitness_score", "summary_message",
]


@app.get("/api/admin/records")
def admin_list_records():
    if not login_required():
        return api_error("请先登录", 401)
    user_id = flask.request.args.get("user_id", flask.session["user_id"])
    rows = db.fetch_all(
        """SELECT * FROM daily_health WHERE user_id = %s ORDER BY record_date DESC LIMIT 60""",
        (user_id,),
    )
    return flask.jsonify({"ok": True, "data": [serialize(r) for r in rows]})


@app.post("/api/admin/records")
def admin_create_record():
    if not login_required():
        return api_error("请先登录", 401)
    payload = flask.request.get_json(silent=True) or {}
    record_date = payload.get("record_date")
    if not record_date:
        return api_error("记录日期不能为空")
    user_id = payload.get("user_id", flask.session["user_id"])
    values = [user_id, record_date] + [payload.get(f) for f in RECORD_FIELDS if f != "record_date"]
    placeholders = ", ".join(["%s"] * len(values))
    columns = ", ".join(["user_id"] + RECORD_FIELDS)
    updates = ", ".join(f"{f} = VALUES({f})" for f in RECORD_FIELDS if f != "record_date")
    new_id = db.execute(
        f"INSERT INTO daily_health ({columns}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}",
        tuple(values),
    )
    return flask.jsonify({"ok": True, "id": new_id})


@app.put("/api/admin/records/<int:record_id>")
def admin_update_record(record_id):
    if not login_required():
        return api_error("请先登录", 401)
    payload = flask.request.get_json(silent=True) or {}
    fields, params = [], []
    for column in RECORD_FIELDS:
        if column in payload:
            fields.append(f"{column} = %s")
            params.append(payload[column])
    if not fields:
        return api_error("没有需要更新的字段")
    params.append(record_id)
    db.execute(f"UPDATE daily_health SET {', '.join(fields)} WHERE id = %s", tuple(params))
    return flask.jsonify({"ok": True})


@app.delete("/api/admin/records/<int:record_id>")
def admin_delete_record(record_id):
    if not login_required():
        return api_error("请先登录", 401)
    db.execute("DELETE FROM daily_health WHERE id = %s", (record_id,))
    return flask.jsonify({"ok": True})


# ----------------------------------------------------------------------
# 后台管理 API —— 健康提醒任务
# ----------------------------------------------------------------------
@app.get("/api/admin/tasks")
def admin_list_tasks():
    if not login_required():
        return api_error("请先登录", 401)
    user_id = flask.request.args.get("user_id", flask.session["user_id"])
    rows = db.fetch_all(
        "SELECT * FROM health_tasks WHERE user_id = %s ORDER BY id", (user_id,)
    )
    return flask.jsonify({"ok": True, "data": [serialize(r) for r in rows]})


@app.post("/api/admin/tasks")
def admin_create_task():
    if not login_required():
        return api_error("请先登录", 401)
    payload = flask.request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    if not title:
        return api_error("任务标题不能为空")
    user_id = payload.get("user_id", flask.session["user_id"])
    new_id = db.execute(
        "INSERT INTO health_tasks (user_id, title, detail, status, tone) VALUES (%s,%s,%s,%s,%s)",
        (user_id, title, payload.get("detail"), payload.get("status", "正常"),
         payload.get("tone", "normal")),
    )
    return flask.jsonify({"ok": True, "id": new_id})


@app.put("/api/admin/tasks/<int:task_id>")
def admin_update_task(task_id):
    if not login_required():
        return api_error("请先登录", 401)
    payload = flask.request.get_json(silent=True) or {}
    fields, params = [], []
    for column in ("title", "detail", "status", "tone"):
        if column in payload:
            fields.append(f"{column} = %s")
            params.append(payload[column])
    if not fields:
        return api_error("没有需要更新的字段")
    params.append(task_id)
    db.execute(f"UPDATE health_tasks SET {', '.join(fields)} WHERE id = %s", tuple(params))
    return flask.jsonify({"ok": True})


@app.delete("/api/admin/tasks/<int:task_id>")
def admin_delete_task(task_id):
    if not login_required():
        return api_error("请先登录", 401)
    db.execute("DELETE FROM health_tasks WHERE id = %s", (task_id,))
    return flask.jsonify({"ok": True})


# ----------------------------------------------------------------------
# 后台管理 API —— 健康分析/建议
# ----------------------------------------------------------------------
@app.get("/api/admin/insights")
def admin_list_insights():
    if not login_required():
        return api_error("请先登录", 401)
    user_id = flask.request.args.get("user_id", flask.session["user_id"])
    rows = db.fetch_all(
        "SELECT * FROM health_insights WHERE user_id = %s ORDER BY id", (user_id,)
    )
    return flask.jsonify({"ok": True, "data": [serialize(r) for r in rows]})


@app.post("/api/admin/insights")
def admin_create_insight():
    if not login_required():
        return api_error("请先登录", 401)
    payload = flask.request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    text = str(payload.get("text", "")).strip()
    if not title or not text:
        return api_error("标题和内容不能为空")
    user_id = payload.get("user_id", flask.session["user_id"])
    new_id = db.execute(
        "INSERT INTO health_insights (user_id, title, text) VALUES (%s,%s,%s)",
        (user_id, title, text),
    )
    return flask.jsonify({"ok": True, "id": new_id})


@app.put("/api/admin/insights/<int:insight_id>")
def admin_update_insight(insight_id):
    if not login_required():
        return api_error("请先登录", 401)
    payload = flask.request.get_json(silent=True) or {}
    fields, params = [], []
    for column in ("title", "text"):
        if column in payload:
            fields.append(f"{column} = %s")
            params.append(payload[column])
    if not fields:
        return api_error("没有需要更新的字段")
    params.append(insight_id)
    db.execute(f"UPDATE health_insights SET {', '.join(fields)} WHERE id = %s", tuple(params))
    return flask.jsonify({"ok": True})


@app.delete("/api/admin/insights/<int:insight_id>")
def admin_delete_insight(insight_id):
    if not login_required():
        return api_error("请先登录", 401)
    db.execute("DELETE FROM health_insights WHERE id = %s", (insight_id,))
    return flask.jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
