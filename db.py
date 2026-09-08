import os
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor


class DatabaseError(RuntimeError):
    """Raised when the MySQL connection or query fails."""



def connection_config(include_database=True):
    config = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", "721382448"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
    }
    if include_database:
        config["database"] = os.getenv("MYSQL_DATABASE", "health_app")
    return config


@contextmanager
def get_connection():
    connection = None
    try:
        connection = pymysql.connect(**connection_config())
        yield connection
        connection.commit()
    except pymysql.MySQLError as error:
        if connection:
            connection.rollback()
        raise DatabaseError(str(error)) from error
    finally:
        if connection:
            connection.close()


@contextmanager
def cursor():
    with get_connection() as connection:
        with connection.cursor() as current_cursor:
            yield current_cursor


def fetch_one(query, params=()):
    with cursor() as current_cursor:
        current_cursor.execute(query, params)
        return current_cursor.fetchone()


def fetch_all(query, params=()):
    with cursor() as current_cursor:
        current_cursor.execute(query, params)
        return current_cursor.fetchall()


def execute(query, params=()):
    with cursor() as current_cursor:
        current_cursor.execute(query, params)
        return current_cursor.lastrowid
