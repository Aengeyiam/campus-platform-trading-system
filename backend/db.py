"""
数据库连接模块
所有蓝图通过 from db import query, execute 使用
"""
import psycopg2
import psycopg2.extras
from config import Config


def _connect():
    """获取数据库连接（每次调用新建连接，用完即关）"""
    return psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
    )


def query(sql: str, params: tuple = None) -> list[dict]:
    """执行 SELECT，返回 dict 列表"""
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def query_one(sql: str, params: tuple = None) -> dict | None:
    """执行 SELECT，返回单条 dict 或 None"""
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = None) -> int:
    """执行 INSERT/UPDATE/DELETE，返回影响行数"""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def call_proc(proc_name: str, params: tuple = None) -> list[dict]:
    """调用存储过程，返回结果集"""
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.callproc(proc_name, params or ())
            conn.commit()
            # 存储过程可能返回多个结果集
            results = []
            for row in cur.fetchall():
                results.append(row)
            return results
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
