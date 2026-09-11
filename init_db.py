"""
MoveWell 健康后台  MySQL 数据库初始化脚本

功能:
  1. 自动创建 health_app 数据库
  2. 执行 schema.sql 创建全部数据表
  3. 写入初始数据: 管理员账号 admin/123、近7天健康记录、提醒任务、健康分析

可重复执行 (已存在的账号/记录会跳过或更新)。

用法:
  python init_db.py
"""
import datetime as dt
from pathlib import Path

import pymysql
from pymysql.constants import CLIENT

from werkzeug.security import generate_password_hash

import db

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_FILE = BASE_DIR / "schema.sql"


def connect_server():
    """连接 MySQL 服务 (不指定数据库), 用于建库。"""
    config = db.connection_config(include_database=False)
    config["client_flag"] = CLIENT.MULTI_STATEMENTS
    return pymysql.connect(**config)


def create_database_and_tables():
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    connection = connect_server()
    try:
        with connection.cursor() as cursor:
            # 先执行建库语句, 再执行其余建表语句
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement:
                    cursor.execute(statement)
        connection.commit()
        print("[1/3] 数据库与数据表创建完成 (health_app)")
    finally:
        connection.close()


def apply_schema_updates():
    """为已有数据库补充新字段，重复执行不会报错。"""
    with db.get_connection() as connection:
        with connection.cursor() as cursor:
            for statement in (
                "ALTER TABLE users ADD COLUMN avatar LONGTEXT NULL",
                "ALTER TABLE users ADD COLUMN nickname VARCHAR(50) NULL",
                "ALTER TABLE users ADD COLUMN bio VARCHAR(255) NULL",
                "ALTER TABLE users ADD COLUMN gender VARCHAR(10) NULL",
                "ALTER TABLE users ADD COLUMN birthday DATE NULL",
                "ALTER TABLE users ADD COLUMN country VARCHAR(50) NULL",
                "ALTER TABLE users ADD COLUMN region VARCHAR(100) NULL",
                "ALTER TABLE users ADD COLUMN signature VARCHAR(255) NULL",
                "ALTER TABLE users ADD COLUMN oauth_provider VARCHAR(20) NULL",
                "ALTER TABLE users ADD COLUMN oauth_id VARCHAR(100) NULL",
                "ALTER TABLE users ADD UNIQUE KEY uk_users_oauth (oauth_provider, oauth_id)",
            ):
                try:
                    cursor.execute(statement)
                except pymysql.err.OperationalError as error:
                    if error.args[0] not in (1060, 1061, 1826):
                        raise
    print("       用户资料与第三方登录字段就绪")


def seed_users(cursor):
    """初始管理员账号: admin / 123"""
    password_hash = generate_password_hash("123")
    cursor.execute(
        """
        INSERT INTO users (username, password_hash, name, email, level)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            password_hash = VALUES(password_hash),
            name = VALUES(name), email = VALUES(email), level = VALUES(level)
        """,
        ("admin", password_hash, "Yun", "admin@movewell.app", "管理员"),
    )
    cursor.execute("SELECT id FROM users WHERE username = %s", ("admin",))
    admin_id = cursor.fetchone()["id"]
    print(f"[2/3] 管理员账号就绪: admin / 123  (user_id={admin_id})")
    return admin_id


TEST_USERS = [
    ("test_alice", "Alice", "alice@example.test", "女", "1998-03-14", "中国", "上海市", "保持好奇，保持运动。"),
    ("test_bob", "Bob", "bob@example.test", "男", "1995-07-22", "中国", "北京市", "每天进步一点点。"),
    ("test_cindy", "Cindy", "cindy@example.test", "女", "2001-11-08", "中国", "广东省深圳市", "把生活过成喜欢的样子。"),
    ("test_david", "David", "david@example.test", "男", "1992-01-30", "中国", "浙江省杭州市", "规律训练，认真生活。"),
    ("test_emma", "Emma", "emma@example.test", "女", "1997-05-19", "中国", "江苏省南京市", "向着阳光奔跑。"),
    ("test_frank", "Frank", "frank@example.test", "男", "1990-09-03", "中国", "湖北省武汉市", "训练让生活更有节奏。"),
    ("test_grace", "Grace", "grace@example.test", "女", "1999-12-25", "中国", "四川省成都市", "温柔坚定地前进。"),
    ("test_henry", "Henry", "henry@example.test", "男", "1994-04-11", "中国", "山东省青岛市", "今天也要完成小目标。"),
    ("test_iris", "Iris", "iris@example.test", "女", "2000-06-28", "中国", "福建省厦门市", "保持热爱，持续行动。"),
    ("test_jack", "Jack", "jack@example.test", "男", "1989-10-16", "中国", "重庆市", "自律带来自由。"),
    ("test_kelly", "Kelly", "kelly@example.test", "女", "1996-02-07", "中国", "陕西省西安市", "让每一次呼吸都更从容。"),
    ("test_leo", "Leo", "leo@example.test", "男", "2002-08-21", "中国", "云南省昆明市", "一步一步变得更强。"),
    ("test_mia", "Mia", "mia@example.test", "女", "1993-03-30", "中国", "辽宁省大连市", "平衡工作与健康。"),
    ("test_nick", "Nick", "nick@example.test", "男", "1991-11-12", "中国", "河南省郑州市", "专注当下，稳定成长。"),
]


def seed_test_users(cursor):
    """写入可重复使用的测试账号及虚假个人资料。"""
    password_hash = generate_password_hash("123")
    user_ids = []
    for username, nickname, email, gender, birthday, country, region, signature in TEST_USERS:
        cursor.execute(
            """INSERT INTO users
               (username, password_hash, name, nickname, bio, gender, birthday,
                country, region, signature, email, level)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '普通用户')
               ON DUPLICATE KEY UPDATE
                 password_hash = VALUES(password_hash), name = VALUES(name),
                 nickname = VALUES(nickname), bio = VALUES(bio), gender = VALUES(gender),
                 birthday = VALUES(birthday), country = VALUES(country),
                 region = VALUES(region), signature = VALUES(signature),
                 email = VALUES(email), level = VALUES(level)""",
            (username, password_hash, nickname, nickname,
             f"{nickname} 的健康档案与训练记录（测试数据）", gender, birthday,
             country, region, signature, email),
        )
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user_ids.append(cursor.fetchone()["id"])
    print(f"       测试账号就绪: {len(user_ids)} 个 (统一密码: 123)")
    return user_ids


def seed_test_exercises(cursor, user_ids):
    """为测试账号写入近期运动历史。"""
    today = dt.date.today()
    records = [
        ("running", 32, 260), ("cycling", 45, 310),
        ("yoga", 28, 110), ("strength", 38, 240),
    ]
    for user_id, offset in zip(user_ids, range(len(user_ids))):
        cursor.execute("DELETE FROM exercise_logs WHERE user_id = %s", (user_id,))
        for index, (exercise_type, duration, energy) in enumerate(records):
            day = today - dt.timedelta(days=index + offset)
            cursor.execute(
                """INSERT INTO exercise_logs
                   (user_id, exercise_type, duration_minutes, energy_kcal, record_date)
                   VALUES (%s, %s, %s, %s, %s)""",
                (user_id, exercise_type, duration + offset * 3,
                 energy + offset * 20, day),
            )
        cursor.execute(
            """UPDATE daily_health SET exercise_minutes =
                 (SELECT COALESCE(SUM(duration_minutes), 0) FROM exercise_logs
                  WHERE user_id = %s AND record_date = %s)
               WHERE user_id = %s AND record_date = %s""",
            (user_id, today, user_id, today),
        )
    print("       测试账号运动历史写入完成")


def seed_daily_health(cursor, user_id):
    """近7天健康记录 (最后一天=今天, 与首页仪表盘数据一致)。"""
    today = dt.date.today()
    # 近7天体适能评分 -> 首页"一周健康趋势"柱状图
    week_fitness = [48, 64, 72, 84, 66, 90, 78]
    week_steps = [6200, 7100, 7800, 9100, 6800, 9600, 8420]
    week_exercise = [25, 30, 35, 48, 30, 55, 42]
    week_sleep_quality = [62, 68, 70, 74, 65, 80, 76]

    for i in range(7):
        day = today - dt.timedelta(days=6 - i)
        is_today = i == 6
        cursor.execute(
            """
            INSERT INTO daily_health
                (user_id, record_date, steps, heart_rate, sleep_hours, calories,
                 water_liters, sleep_quality, exercise_minutes, fitness_score, summary_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                steps = VALUES(steps), heart_rate = VALUES(heart_rate),
                sleep_hours = VALUES(sleep_hours), calories = VALUES(calories),
                water_liters = VALUES(water_liters), sleep_quality = VALUES(sleep_quality),
                exercise_minutes = VALUES(exercise_minutes), fitness_score = VALUES(fitness_score),
                summary_message = VALUES(summary_message)
            """,
            (
                user_id, day,
                week_steps[i],
                72 if is_today else 68 + i % 5,
                7.6 if is_today else round(6.5 + i * 0.2, 1),
                560 if is_today else 420 + i * 25,
                1.8 if is_today else round(1.5 + i * 0.06, 1),
                week_sleep_quality[i],
                week_exercise[i],
                week_fitness[i],
                "当前整体健康状态良好，恢复能力稳定，建议保持今日训练强度。" if is_today
                else "近期状态稳步提升，保持规律作息与训练节奏。",
            ),
        )
    print(f"       近7天健康记录写入完成 ({today - dt.timedelta(days=6)} ~ {today})")


def seed_tasks(cursor, user_id):
    tasks = [
        ("步数目标", "完成率 82%", "达标", "normal"),
        ("补水提醒", "还差 0.4L", "提醒", "warning"),
        ("恢复建议", "建议减少高强度训练", "注意", "danger"),
    ]
    cursor.execute("DELETE FROM health_tasks WHERE user_id = %s", (user_id,))
    for title, detail, status, tone in tasks:
        cursor.execute(
            "INSERT INTO health_tasks (user_id, title, detail, status, tone) VALUES (%s,%s,%s,%s,%s)",
            (user_id, title, detail, status, tone),
        )
    print("       健康提醒任务: 3 条")


def seed_insights(cursor, user_id):
    insights = [
        ("综合评估", "整体健康状态处于良好区间，连续三天运动达标，恢复能力增强明显。"),
        ("建议", "今日保持中等强度训练，继续补充水分，并安排 20 分钟轻度拉伸恢复。"),
    ]
    cursor.execute("DELETE FROM health_insights WHERE user_id = %s", (user_id,))
    for title, text in insights:
        cursor.execute(
            "INSERT INTO health_insights (user_id, title, text) VALUES (%s,%s,%s)",
            (user_id, title, text),
        )
    print("       健康分析建议: 2 条")


def seed_data():
    with db.get_connection() as connection:
        with connection.cursor() as cursor:
            admin_id = seed_users(cursor)
            seed_daily_health(cursor, admin_id)
            seed_tasks(cursor, admin_id)
            seed_insights(cursor, admin_id)
            test_user_ids = seed_test_users(cursor)
            for user_id in test_user_ids:
                seed_daily_health(cursor, user_id)
                seed_tasks(cursor, user_id)
                seed_insights(cursor, user_id)
            seed_test_exercises(cursor, test_user_ids)
    print("[3/3] 初始数据写入完成")


def main():
    print("=" * 50)
    print("MoveWell 健康后台  MySQL 初始化")
    print(f"目标: {db.connection_config()['host']}:{db.connection_config()['port']}"
          f" / 数据库 {db.connection_config()['database']}")
    print("=" * 50)
    create_database_and_tables()
    apply_schema_updates()
    seed_data()
    print("-" * 50)
    print("全部完成! 现在可以启动: python app.py")
    print("登录账号: admin   密码: 123")


if __name__ == "__main__":
    main()
