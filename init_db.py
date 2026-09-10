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
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN avatar LONGTEXT NULL")
            except pymysql.err.OperationalError as error:
                if error.args[0] != 1060:
                    raise
    print("       用户头像字段就绪")


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
