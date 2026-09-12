import base64
import datetime as dt
import json
import os
import re
import secrets
from decimal import Decimal
from functools import wraps
from urllib.parse import parse_qs, quote, urlencode
from zoneinfo import ZoneInfo

import flask
import requests
from werkzeug.security import check_password_hash, generate_password_hash

import db

app = flask.Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "health-demo-secret")
MAX_IMAGE_SIZE = 10 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024
APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Shanghai"))


@app.errorhandler(db.DatabaseError)
def database_error(error):
    app.logger.exception("Database request failed: %s", error)
    if flask.request.path.startswith("/api/"):
        return api_error("数据库字段可能未更新，请先运行 python init_db.py", 500)
    return "数据库暂时不可用，请稍后重试。", 500


OAUTH_PROVIDERS = {
    "wechat": {
        "client_id": "WECHAT_APP_ID",
        "client_secret": "WECHAT_APP_SECRET",
        "authorize_url": "https://open.weixin.qq.com/connect/qrconnect",
        "scope": "snsapi_login",
    },
    "qq": {
        "client_id": "QQ_APP_ID",
        "client_secret": "QQ_APP_KEY",
        "authorize_url": "https://graph.qq.com/oauth2.0/authorize",
        "scope": "get_user_info",
    },
}


# ----------------------------------------------------------------------
# 辅助函数
# ----------------------------------------------------------------------
def api_error(message, status=400):
    return flask.jsonify({"ok": False, "message": message}), status


def login_required():
    return flask.session.get("user_id") is not None


def is_admin():
    user_id = flask.session.get("user_id")
    if user_id is None:
        return False
    user = db.fetch_one("SELECT level FROM users WHERE id = %s", (user_id,))
    return bool(user and user["level"] == "管理员")


def admin_only(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not login_required():
            if flask.request.path.startswith("/api/"):
                return api_error("请先登录", 401)
            flask.abort(403)
        if not is_admin():
            if flask.request.path.startswith("/api/"):
                return api_error("仅管理员可以访问后台数据", 403)
            flask.abort(403)
        return view(*args, **kwargs)

    return wrapped


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


def current_date():
    return dt.datetime.now(APP_TIMEZONE).date()


def oauth_redirect_uri(provider):
    configured = os.getenv(f"{provider.upper()}_REDIRECT_URI")
    return configured or flask.url_for("oauth_callback", provider=provider, _external=True)


def oauth_error(message):
    return flask.redirect(f"/login?oauth_error={quote(message)}")


def oauth_http_get(url, **params):
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response


def parse_qq_callback(response_text):
    match = re.search(r"callback\s*\(\s*(\{.*\})\s*\)\s*;?", response_text, re.DOTALL)
    if not match:
        raise ValueError("QQ 返回的 openid 格式无效")
    return json.loads(match.group(1))


def sign_in_oauth_user(provider, provider_id, nickname, avatar=None):
    identity = db.fetch_one(
        "SELECT * FROM users WHERE oauth_provider = %s AND oauth_id = %s",
        (provider, provider_id),
    )
    if identity:
        user_id = identity["id"]
        db.execute(
            "UPDATE users SET name = %s, avatar = COALESCE(%s, avatar) WHERE id = %s",
            (nickname or identity["name"], avatar, user_id),
        )
    else:
        username = f"{provider}_{provider_id}"[:50]
        user_id = db.execute(
            """INSERT INTO users
               (username, password_hash, name, email, level, avatar, oauth_provider, oauth_id)
               VALUES (%s, %s, %s, NULL, '普通用户', %s, %s, %s)""",
            (username, generate_password_hash(secrets.token_urlsafe(32)),
             nickname or f"{provider} 用户", avatar, provider, provider_id),
        )

    user = db.fetch_one("SELECT id, username, name FROM users WHERE id = %s", (user_id,))
    flask.session["user_id"] = user["id"]
    flask.session["username"] = user["username"]
    flask.session["name"] = user["name"]


@app.get("/auth/<provider>")
def oauth_start(provider):
    config = OAUTH_PROVIDERS.get(provider)
    client_id = os.getenv(config["client_id"]) if config else None
    client_secret = os.getenv(config["client_secret"]) if config else None
    if not config or not client_id or not client_secret:
        return oauth_error(f"{provider} 登录尚未配置，请联系管理员")

    state = secrets.token_urlsafe(32)
    flask.session[f"oauth_state_{provider}"] = state
    params = {
        "client_id": client_id,
        "redirect_uri": oauth_redirect_uri(provider),
        "response_type": "code",
        "scope": config["scope"],
        "state": state,
    }
    target = f"{config['authorize_url']}?{urlencode(params)}"
    if provider == "wechat":
        target += "#wechat_redirect"
    return flask.redirect(target)


@app.get("/auth/<provider>/callback")
def oauth_callback(provider):
    config = OAUTH_PROVIDERS.get(provider)
    if not config:
        return oauth_error("不支持的登录方式")
    state = flask.request.args.get("state")
    expected_state = flask.session.pop(f"oauth_state_{provider}", None)
    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        return oauth_error("登录请求已失效，请重新尝试")
    if flask.request.args.get("error"):
        return oauth_error("你取消了第三方登录")

    code = flask.request.args.get("code")
    if not code:
        return oauth_error("第三方登录没有返回授权码")

    client_id = os.getenv(config["client_id"])
    client_secret = os.getenv(config["client_secret"])
    try:
        if provider == "wechat":
            token_data = oauth_http_get(
                "https://api.weixin.qq.com/sns/oauth2/access_token",
                appid=client_id, secret=client_secret, code=code,
                grant_type="authorization_code",
            ).json()
            if token_data.get("errcode"):
                raise ValueError(token_data.get("errmsg", "微信授权失败"))
            profile = oauth_http_get(
                "https://api.weixin.qq.com/sns/userinfo",
                access_token=token_data["access_token"],
                openid=token_data["openid"], lang="zh_CN",
            ).json()
            if profile.get("errcode"):
                raise ValueError(profile.get("errmsg", "微信用户信息获取失败"))
            provider_id = profile["openid"]
            nickname = profile.get("nickname")
            avatar = profile.get("headimgurl")
        else:
            token_response = oauth_http_get(
                "https://graph.qq.com/oauth2.0/token",
                grant_type="authorization_code", client_id=client_id,
                client_secret=client_secret, code=code,
                redirect_uri=oauth_redirect_uri(provider),
            )
            token_data = parse_qs(token_response.text)
            access_token = token_data["access_token"][0]
            openid_data = parse_qq_callback(oauth_http_get(
                "https://graph.qq.com/oauth2.0/me", access_token=access_token,
            ).text)
            provider_id = openid_data["openid"]
            profile = oauth_http_get(
                "https://graph.qq.com/user/get_user_info",
                access_token=access_token, oauth_consumer_key=client_id,
                openid=provider_id,
            ).json()
            if profile.get("ret") != 0:
                raise ValueError(profile.get("msg", "QQ 用户信息获取失败"))
            nickname = profile.get("nickname")
            avatar = profile.get("figureurl_qq_2") or profile.get("figureurl_qq_1")

        sign_in_oauth_user(provider, provider_id, nickname, avatar)
        return flask.redirect("/dashboard")
    except (KeyError, ValueError, requests.RequestException) as error:
        app.logger.warning("OAuth %s failed: %s", provider, error)
        return oauth_error("第三方登录失败，请稍后重试")


# ----------------------------------------------------------------------
# 页面路由
# ----------------------------------------------------------------------
@app.route("/")
@app.route("/login")
@app.route("/dashboard")
def index():
    return flask.render_template("base.html")


@app.route("/admin")
@admin_only
def admin_page():
    return flask.render_template("index.html")


# ----------------------------------------------------------------------
# 认证 API
# ----------------------------------------------------------------------
@app.get("/api/auth")
def auth_state():
    logged_in = login_required()
    user = db.fetch_one(
        "SELECT username, level FROM users WHERE id = %s",
        (flask.session.get("user_id"),),
    ) if logged_in else None
    return flask.jsonify({
        "authenticated": logged_in,
        "is_admin": bool(user and user["level"] == "管理员"),
        "user": {"email": user["username"], "level": user["level"]} if user else None,
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


@app.put("/api/profile")
def profile_update_api():
    if not login_required():
        return api_error("请先登录", 401)

    nickname = flask.request.form.get("nickname", "").strip()
    bio = flask.request.form.get("bio", "").strip()
    gender = flask.request.form.get("gender", "").strip()
    birthday = flask.request.form.get("birthday", "").strip() or None
    country = flask.request.form.get("country", "").strip()
    region = flask.request.form.get("region", "").strip()
    signature = flask.request.form.get("signature", "").strip()
    avatar_file = flask.request.files.get("avatar")
    fields = [
        "name = COALESCE(NULLIF(%s, ''), name)", "nickname = %s", "bio = %s", "gender = %s",
        "birthday = %s", "country = %s", "region = %s", "signature = %s",
    ]
    params = [nickname, nickname or None,
              bio or None, gender or None, birthday, country or None,
              region or None, signature or None]
    if avatar_file and avatar_file.filename:
        if not avatar_file.content_type or not avatar_file.content_type.startswith("image/"):
            return api_error("请选择图片文件")
        image_data = avatar_file.read(MAX_IMAGE_SIZE + 1)
        if len(image_data) > MAX_IMAGE_SIZE:
            return api_error("头像图片不能超过 10MB")
        avatar = (
            f"data:{avatar_file.content_type};base64,"
            f"{base64.b64encode(image_data).decode('ascii')}"
        )
        fields.append("avatar = %s")
        params.append(avatar)
    params.append(flask.session["user_id"])
    db.execute(
        f"UPDATE users SET {', '.join(fields)} WHERE id = %s",
        tuple(params),
    )
    user = db.fetch_one(
        """SELECT name, nickname, bio, gender, birthday, country, region,
              signature, username, level, avatar FROM users WHERE id = %s""",
        (flask.session["user_id"],),
    )
    return flask.jsonify({"ok": True, "user": {
        "name": user["name"],
        "nickname": user["nickname"] or user["name"],
        "bio": user["bio"],
        "gender": user["gender"],
        "birthday": user["birthday"].isoformat() if user["birthday"] else "",
        "country": user["country"],
        "region": user["region"],
        "signature": user["signature"],
        "email": user["username"],
        "level": user["level"],
        "is_admin": user["level"] == "管理员",
        "avatar": user["avatar"],
    }})


@app.post("/api/password")
def password_update_api():
    if not login_required():
        return api_error("请先登录", 401)

    payload = flask.request.get_json(silent=True) or {}
    current_password = str(payload.get("current_password", ""))
    new_password = str(payload.get("new_password", ""))
    confirm_password = str(payload.get("confirm_password", ""))
    if not current_password or not new_password or not confirm_password:
        return api_error("请完整填写密码信息")
    if len(new_password) < 6:
        return api_error("新密码至少需要 6 位")
    if new_password != confirm_password:
        return api_error("两次输入的新密码不一致")

    user = db.fetch_one(
        "SELECT password_hash FROM users WHERE id = %s",
        (flask.session["user_id"],),
    )
    if not user or not check_password_hash(user["password_hash"], current_password):
        return api_error("当前密码不正确")

    db.execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (generate_password_hash(new_password), flask.session["user_id"]),
    )
    return flask.jsonify({"ok": True, "message": "密码修改成功"})


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
    today = current_date()

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
        "user": {
            "id": user["id"],
            "name": user["name"],
            "nickname": user.get("nickname") or user["name"],
            "bio": user.get("bio"),
            "gender": user.get("gender"),
            "birthday": user["birthday"].isoformat() if user.get("birthday") else "",
            "country": user.get("country"),
            "region": user.get("region"),
            "signature": user.get("signature"),
            "email": user["username"],
            "level": user["level"],
            "is_admin": user["level"] == "管理员",
            "avatar": user.get("avatar"),
        },
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
    today = current_date()
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


EXERCISE_GUIDES = [
    {"key": "running", "name": "跑步", "icon": "🏃", "guide": "先慢走热身 5 分钟，再保持可以正常说话的节奏，结束后慢走放松。", "tip": "适合提升心肺与耐力"},
    {"key": "cycling", "name": "骑行", "icon": "🚴", "guide": "调整座椅到膝盖微屈，保持稳定踏频，骑行前后各做 5 分钟轻松热身。", "tip": "低冲击有氧运动"},
    {"key": "swimming", "name": "游泳", "icon": "🏊", "guide": "先进行肩颈和踝关节活动，采用舒适泳姿，组间充分休息并注意补水。", "tip": "全身参与、关节负担小"},
    {"key": "yoga", "name": "瑜伽", "icon": "🧘", "guide": "从呼吸和基础体式开始，动作保持平稳，不要强行追求幅度，结束时做放松。", "tip": "改善柔韧性与恢复"},
    {"key": "strength", "name": "力量训练", "icon": "🏋", "guide": "先用轻重量热身，动作过程中保持核心稳定，每组之间休息 60 至 90 秒。", "tip": "增强肌力与基础代谢"},
    {"key": "walking", "name": "快走", "icon": "🚶", "guide": "保持抬头挺胸和自然摆臂，步速以微微出汗但能交谈为宜。", "tip": "容易坚持的入门运动"},
]


@app.get("/api/exercises")
def exercise_list_api():
    if not login_required():
        return api_error("请先登录", 401)
    limit = 200 if flask.request.args.get("all") == "1" else 20
    filters = ["user_id = %s"]
    params = [flask.session["user_id"]]
    record_date = flask.request.args.get("date", "").strip()
    exercise_type = flask.request.args.get("exercise_type", "").strip()
    if record_date:
        filters.append("record_date = %s")
        params.append(record_date)
    if exercise_type and any(item["key"] == exercise_type for item in EXERCISE_GUIDES):
        filters.append("exercise_type = %s")
        params.append(exercise_type)
    params.append(limit)
    rows = db.fetch_all(
        """SELECT id, exercise_type, duration_minutes, energy_kcal, record_date
           FROM exercise_logs WHERE """ + " AND ".join(filters) +
        " ORDER BY record_date DESC, id DESC LIMIT %s",
        tuple(params),
    )
    return flask.jsonify({"ok": True, "guides": EXERCISE_GUIDES,
                          "logs": [serialize(row) for row in rows]})


@app.post("/api/exercises/log")
def exercise_log_api():
    if not login_required():
        return api_error("请先登录", 401)
    payload = flask.request.get_json(silent=True) or {}
    exercise_type = str(payload.get("exercise_type", "")).strip()
    try:
        duration = int(payload.get("duration_minutes", 0))
        energy = int(payload.get("energy_kcal", 0))
    except (TypeError, ValueError):
        return api_error("运动时长和消耗能量必须是数字")
    if not any(item["key"] == exercise_type for item in EXERCISE_GUIDES):
        return api_error("请选择运动项目")
    if duration <= 0 or duration > 1440:
        return api_error("运动时长应在 1 到 1440 分钟之间")
    if energy < 0 or energy > 100000:
        return api_error("消耗能量请输入有效数值")

    today = current_date()
    user_id = flask.session["user_id"]
    db.execute(
        """INSERT INTO exercise_logs
           (user_id, exercise_type, duration_minutes, energy_kcal, record_date)
           VALUES (%s, %s, %s, %s, %s)""",
        (user_id, exercise_type, duration, energy, today),
    )
    db.execute(
        """INSERT INTO daily_health (user_id, record_date, exercise_minutes)
           VALUES (%s, %s, %s)
           ON DUPLICATE KEY UPDATE exercise_minutes =
             (SELECT COALESCE(SUM(duration_minutes), 0) FROM exercise_logs
              WHERE user_id = %s AND record_date = %s)""",
        (user_id, today, duration, user_id, today),
    )
    return flask.jsonify({"ok": True, "message": "运动记录已保存"})


@app.get("/api/community/posts")
def community_posts_api():
    if not login_required():
        return api_error("请先登录", 401)
    user_id = flask.session["user_id"]
    rows = db.fetch_all(
        """SELECT p.id, p.user_id, p.content, p.created_at, u.name, u.avatar,
                  COUNT(DISTINCT c.id) AS comment_count,
                  COUNT(DISTINCT l_all.user_id) AS like_count,
                  MAX(l_me.user_id) IS NOT NULL AS liked
           FROM community_posts p
           JOIN users u ON u.id = p.user_id
           LEFT JOIN community_comments c ON c.post_id = p.id
           LEFT JOIN community_likes l_all ON l_all.post_id = p.id
           LEFT JOIN community_likes l_me ON l_me.post_id = p.id AND l_me.user_id = %s
           GROUP BY p.id, p.content, p.created_at, u.name, u.avatar
           ORDER BY p.created_at DESC LIMIT 50""",
        (user_id,),
    )
    return flask.jsonify({"ok": True, "posts": [serialize(row) for row in rows]})


@app.get("/api/community/users/<int:user_id>")
def community_user_profile_api(user_id):
    if not login_required():
        return api_error("请先登录", 401)
    user = db.fetch_one(
        """SELECT id, name, nickname, bio, gender, birthday, country, region,
                  signature, avatar FROM users WHERE id = %s""",
        (user_id,),
    )
    if not user:
        return api_error("用户不存在", 404)
    current_user_id = flask.session["user_id"]
    posts = db.fetch_all(
        """SELECT p.id, p.content, p.created_at,
                  COUNT(DISTINCT c.id) AS comment_count,
                  COUNT(DISTINCT l.user_id) AS like_count
           FROM community_posts p
           LEFT JOIN community_comments c ON c.post_id = p.id
           LEFT JOIN community_likes l ON l.post_id = p.id
           WHERE p.user_id = %s
           GROUP BY p.id, p.content, p.created_at
           ORDER BY p.created_at DESC LIMIT 50""",
        (user_id,),
    )
    stats = db.fetch_one(
        """SELECT
             (SELECT COUNT(*) FROM community_likes l JOIN community_posts p ON p.id = l.post_id WHERE p.user_id = %s) AS likes_received,
             (SELECT COUNT(*) FROM community_follows WHERE following_id = %s) AS followers_count,
             (SELECT COUNT(*) FROM community_follows WHERE follower_id = %s) AS following_count,
             EXISTS(SELECT 1 FROM community_follows WHERE follower_id = %s AND following_id = %s) AS following""",
        (user_id, user_id, user_id, current_user_id, user_id),
    )
    public_user = serialize(user)
    public_user.update({key: int(value) if key != "following" else bool(value)
                        for key, value in stats.items()})
    return flask.jsonify({"ok": True, "user": public_user,
                          "posts": [serialize(post) for post in posts]})


@app.post("/api/community/users/<int:user_id>/follow")
def community_follow_api(user_id):
    if not login_required():
        return api_error("请先登录", 401)
    follower_id = flask.session["user_id"]
    if follower_id == user_id:
        return api_error("不能关注自己")
    if not db.fetch_one("SELECT id FROM users WHERE id = %s", (user_id,)):
        return api_error("用户不存在", 404)
    relation = db.fetch_one(
        "SELECT follower_id FROM community_follows WHERE follower_id = %s AND following_id = %s",
        (follower_id, user_id),
    )
    if relation:
        db.execute(
            "DELETE FROM community_follows WHERE follower_id = %s AND following_id = %s",
            (follower_id, user_id),
        )
    else:
        db.execute(
            "INSERT INTO community_follows (follower_id, following_id) VALUES (%s, %s)",
            (follower_id, user_id),
        )
    followers = db.fetch_one(
        "SELECT COUNT(*) AS total FROM community_follows WHERE following_id = %s",
        (user_id,),
    )
    return flask.jsonify({"ok": True, "following": not relation,
                          "followers_count": followers["total"]})


@app.get("/api/messages/<int:user_id>")
def private_messages_api(user_id):
    if not login_required():
        return api_error("请先登录", 401)
    current_user_id = flask.session["user_id"]
    if current_user_id == user_id:
        return api_error("不能给自己发送私信")
    if not db.fetch_one("SELECT id FROM users WHERE id = %s", (user_id,)):
        return api_error("用户不存在", 404)
    db.execute(
        """UPDATE private_messages SET read_at = NOW()
           WHERE sender_id = %s AND recipient_id = %s AND read_at IS NULL""",
        (user_id, current_user_id),
    )
    rows = db.fetch_all(
          """SELECT m.id, m.sender_id, m.recipient_id, m.content, m.message_type,
                        m.image_data, m.reply_to_id, m.reply_content, m.created_at,
                        sender.avatar AS sender_avatar, recipient.avatar AS recipient_avatar
              FROM private_messages m
              JOIN users sender ON sender.id = m.sender_id
              JOIN users recipient ON recipient.id = m.recipient_id
            WHERE (m.sender_id = %s AND m.recipient_id = %s)
                OR (m.sender_id = %s AND m.recipient_id = %s)
              ORDER BY m.created_at ASC, m.id ASC LIMIT 200""",
        (current_user_id, user_id, user_id, current_user_id),
    )
    messages = []
    for row in rows:
        message = serialize(row)
        message["mine"] = row["sender_id"] == current_user_id
        messages.append(message)
    return flask.jsonify({"ok": True, "messages": messages})


@app.post("/api/messages/<int:user_id>")
def private_message_create_api(user_id):
    if not login_required():
        return api_error("请先登录", 401)
    current_user_id = flask.session["user_id"]
    if current_user_id == user_id:
        return api_error("不能给自己发送私信")
    if not db.fetch_one("SELECT id FROM users WHERE id = %s", (user_id,)):
        return api_error("用户不存在", 404)
    payload = flask.request.get_json(silent=True) or {}
    content = str(payload.get("content", "")).strip()
    message_type = "text"
    image_data = None
    reply_to_id = None
    reply_content = None
    if flask.request.files:
        content = flask.request.form.get("content", "").strip()
        image_file = flask.request.files.get("image")
        if image_file and image_file.filename:
            if not image_file.content_type or not image_file.content_type.startswith("image/"):
                return api_error("只能发送图片文件")
            image_bytes = image_file.read(MAX_IMAGE_SIZE + 1)
            if len(image_bytes) > MAX_IMAGE_SIZE:
                return api_error("图片不能超过 10MB")
            image_data = "data:{};base64,{}".format(
                image_file.content_type, base64.b64encode(image_bytes).decode("ascii")
            )
            message_type = "image"
        reply_to_id = flask.request.form.get("reply_to_id") or None
        reply_content = flask.request.form.get("reply_content", "").strip() or None
    else:
        reply_to_id = payload.get("reply_to_id") or None
        reply_content = str(payload.get("reply_content", "")).strip() or None
    if not content and not image_data:
        return api_error("消息内容不能为空")
    if len(content) > 2000 or len(reply_content or "") > 2000:
        return api_error("消息不能超过 2000 个字符")
    try:
        reply_to_id = int(reply_to_id) if reply_to_id else None
    except (TypeError, ValueError):
        return api_error("引用消息无效")
    message_id = db.execute(
        """INSERT INTO private_messages (sender_id, recipient_id, content,
                  message_type, image_data, reply_to_id, reply_content)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (current_user_id, user_id, content or None, message_type, image_data,
         reply_to_id, reply_content),
    )
    message = db.fetch_one(
          """SELECT m.id, m.sender_id, m.recipient_id, m.content, m.message_type,
                        m.image_data, m.reply_to_id, m.reply_content, m.created_at,
                        sender.avatar AS sender_avatar, recipient.avatar AS recipient_avatar
              FROM private_messages m
              JOIN users sender ON sender.id = m.sender_id
              JOIN users recipient ON recipient.id = m.recipient_id
              WHERE m.id = %s""",
        (message_id,),
    )
    serialized_message = serialize(message)
    serialized_message["mine"] = True
    return flask.jsonify({"ok": True, "message": serialized_message})


@app.get("/api/social/summary")
def social_summary_api():
    if not login_required():
        return api_error("请先登录", 401)
    current_user_id = flask.session["user_id"]
    read_rows = db.fetch_all(
        "SELECT category, read_at FROM social_reads WHERE user_id = %s",
        (current_user_id,),
    )
    read_at = {row["category"]: row["read_at"] for row in read_rows}
    default_read_at = dt.datetime(1970, 1, 1, tzinfo=APP_TIMEZONE).replace(tzinfo=None)
    followers_read_at = read_at.get("followers", default_read_at)
    notifications_read_at = read_at.get("notifications", default_read_at)
    followers = db.fetch_all(
        """SELECT u.id, u.name, u.nickname, u.avatar
           FROM community_follows f JOIN users u ON u.id = f.follower_id
           WHERE f.following_id = %s ORDER BY f.created_at DESC LIMIT 20""",
        (current_user_id,),
    )
    message_rows = db.fetch_all(
        """SELECT m.id, m.sender_id, m.recipient_id, m.content, m.created_at,
                  u.id AS user_id, u.name, u.nickname, u.avatar
           FROM private_messages m
           JOIN users u ON u.id = IF(m.sender_id = %s, m.recipient_id, m.sender_id)
           WHERE m.sender_id = %s OR m.recipient_id = %s
           ORDER BY m.created_at DESC, m.id DESC LIMIT 200""",
        (current_user_id, current_user_id, current_user_id),
    )
    conversations = {}
    for row in message_rows:
        key = row["user_id"]
        if key not in conversations:
            conversations[key] = serialize(row)
    notifications = db.fetch_all(
        """SELECT id, title, content, created_at
           FROM official_notifications ORDER BY created_at DESC, id DESC LIMIT 20"""
    )
    unread_followers = db.fetch_one(
        """SELECT COUNT(*) AS total FROM community_follows
           WHERE following_id = %s AND created_at > %s""",
        (current_user_id, followers_read_at),
    )["total"]
    unread_messages = db.fetch_one(
        """SELECT COUNT(*) AS total FROM private_messages
           WHERE recipient_id = %s AND read_at IS NULL""",
        (current_user_id,),
    )["total"]
    unread_notifications = db.fetch_one(
        """SELECT COUNT(*) AS total FROM official_notifications
           WHERE created_at > %s""",
        (notifications_read_at,),
    )["total"]
    return flask.jsonify({
        "ok": True,
        "followers": [serialize(row) for row in followers],
        "conversations": list(conversations.values()),
        "notifications": [serialize(row) for row in notifications],
        "unread": {
            "followers": int(unread_followers),
            "messages": int(unread_messages),
            "notifications": int(unread_notifications),
        },
    })


@app.post("/api/social/read/<category>")
def social_mark_read_api(category):
    if not login_required():
        return api_error("请先登录", 401)
    if category not in {"followers", "messages", "notifications"}:
        return api_error("不支持的消息类型")
    current_user_id = flask.session["user_id"]
    if category == "messages":
        db.execute(
            """UPDATE private_messages SET read_at = NOW()
               WHERE recipient_id = %s AND read_at IS NULL""",
            (current_user_id,),
        )
    db.execute(
        """INSERT INTO social_reads (user_id, category, read_at)
           VALUES (%s, %s, NOW())
           ON DUPLICATE KEY UPDATE read_at = NOW()""",
        (current_user_id, category),
    )
    return flask.jsonify({"ok": True})


@app.post("/api/community/posts")
def community_create_post_api():
    if not login_required():
        return api_error("请先登录", 401)
    payload = flask.request.get_json(silent=True) or {}
    content = str(payload.get("content", "")).strip()
    if not content:
        return api_error("帖子内容不能为空")
    if len(content) > 2000:
        return api_error("帖子内容不能超过 2000 字")
    post_id = db.execute(
        "INSERT INTO community_posts (user_id, content) VALUES (%s, %s)",
        (flask.session["user_id"], content),
    )
    return flask.jsonify({"ok": True, "id": post_id})


@app.get("/api/community/posts/<int:post_id>/comments")
def community_comments_api(post_id):
    if not login_required():
        return api_error("请先登录", 401)
    rows = db.fetch_all(
        """SELECT c.id, c.content, c.created_at, u.name, u.avatar
           FROM community_comments c JOIN users u ON u.id = c.user_id
           WHERE c.post_id = %s ORDER BY c.created_at ASC""",
        (post_id,),
    )
    return flask.jsonify({"ok": True, "comments": [serialize(row) for row in rows]})


@app.post("/api/community/posts/<int:post_id>/comments")
def community_create_comment_api(post_id):
    if not login_required():
        return api_error("请先登录", 401)
    content = str((flask.request.get_json(silent=True) or {}).get("content", "")).strip()
    if not content:
        return api_error("评论内容不能为空")
    if len(content) > 500:
        return api_error("评论不能超过 500 字")
    if not db.fetch_one("SELECT id FROM community_posts WHERE id = %s", (post_id,)):
        return api_error("帖子不存在", 404)
    db.execute(
        "INSERT INTO community_comments (post_id, user_id, content) VALUES (%s, %s, %s)",
        (post_id, flask.session["user_id"], content),
    )
    return flask.jsonify({"ok": True})


@app.post("/api/community/posts/<int:post_id>/like")
def community_like_api(post_id):
    if not login_required():
        return api_error("请先登录", 401)
    user_id = flask.session["user_id"]
    if not db.fetch_one("SELECT id FROM community_posts WHERE id = %s", (post_id,)):
        return api_error("帖子不存在", 404)
    liked = db.fetch_one(
        "SELECT post_id FROM community_likes WHERE post_id = %s AND user_id = %s",
        (post_id, user_id),
    )
    if liked:
        db.execute("DELETE FROM community_likes WHERE post_id = %s AND user_id = %s", (post_id, user_id))
    else:
        db.execute("INSERT INTO community_likes (post_id, user_id) VALUES (%s, %s)", (post_id, user_id))
    count = db.fetch_one("SELECT COUNT(*) AS total FROM community_likes WHERE post_id = %s", (post_id,))
    return flask.jsonify({"ok": True, "liked": not liked, "like_count": count["total"]})


# ----------------------------------------------------------------------
# 后台管理 API —— 用户管理
# ----------------------------------------------------------------------
@app.get("/api/admin/users")
@admin_only
def admin_list_users():
    if not login_required():
        return api_error("请先登录", 401)
    rows = db.fetch_all(
        "SELECT id, username, name, email, level, created_at FROM users ORDER BY id"
    )
    return flask.jsonify({"ok": True, "data": [serialize(r) for r in rows]})


@app.post("/api/admin/users")
@admin_only
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
@admin_only
def admin_update_user(user_id):
    if not login_required():
        return api_error("请先登录", 401)
    payload = flask.request.get_json(silent=True) or {}
    fields, params = [], []
    username = str(payload.get("username", "")).strip()
    if "username" in payload:
        if not username:
            return api_error("登录账号不能为空")
        duplicate = db.fetch_one(
            "SELECT id FROM users WHERE username = %s AND id <> %s",
            (username, user_id),
        )
        if duplicate:
            return api_error("登录账号已存在")
        fields.append("username = %s")
        params.append(username)
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
@admin_only
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
@admin_only
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
@admin_only
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
@admin_only
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
@admin_only
def admin_delete_record(record_id):
    if not login_required():
        return api_error("请先登录", 401)
    db.execute("DELETE FROM daily_health WHERE id = %s", (record_id,))
    return flask.jsonify({"ok": True})


# ----------------------------------------------------------------------
# 后台管理 API —— 健康提醒任务
# ----------------------------------------------------------------------
@app.get("/api/admin/tasks")
@admin_only
def admin_list_tasks():
    if not login_required():
        return api_error("请先登录", 401)
    user_id = flask.request.args.get("user_id", flask.session["user_id"])
    rows = db.fetch_all(
        "SELECT * FROM health_tasks WHERE user_id = %s ORDER BY id", (user_id,)
    )
    return flask.jsonify({"ok": True, "data": [serialize(r) for r in rows]})


@app.post("/api/admin/tasks")
@admin_only
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
@admin_only
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
@admin_only
def admin_delete_task(task_id):
    if not login_required():
        return api_error("请先登录", 401)
    db.execute("DELETE FROM health_tasks WHERE id = %s", (task_id,))
    return flask.jsonify({"ok": True})


# ----------------------------------------------------------------------
# 后台管理 API —— 健康分析/建议
# ----------------------------------------------------------------------
@app.get("/api/admin/insights")
@admin_only
def admin_list_insights():
    if not login_required():
        return api_error("请先登录", 401)
    user_id = flask.request.args.get("user_id", flask.session["user_id"])
    rows = db.fetch_all(
        "SELECT * FROM health_insights WHERE user_id = %s ORDER BY id", (user_id,)
    )
    return flask.jsonify({"ok": True, "data": [serialize(r) for r in rows]})


@app.post("/api/admin/insights")
@admin_only
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
@admin_only
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
@admin_only
def admin_delete_insight(insight_id):
    if not login_required():
        return api_error("请先登录", 401)
    db.execute("DELETE FROM health_insights WHERE id = %s", (insight_id,))
    return flask.jsonify({"ok": True})


if __name__ == "__main__":
    # 支持通过 PORT 覆盖服务端口，本地默认使用 8080。
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
