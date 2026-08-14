"""
数据库连接模块
所有蓝图通过 from db import query, execute 使用

连接方式：
  - psycopg2：默认连接池方案，适用于 PostgreSQL 或已开启兼容认证的 openGauss
  - jdbc：通过官方 JDBC 驱动连接 openGauss，解决 Windows 下默认 sha256 认证兼容问题
"""
import os
import sys
import threading

from config import Config

try:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import pool as psycopg2_pool
except ImportError:
    psycopg2 = None
    psycopg2_pool = None


_pg_pool = None
_pool_lock = threading.Lock()
_jdbc_local = threading.local()


def _backend() -> str:
    """返回实际使用的数据库驱动，默认 psycopg2。"""
    return (Config.DB_DRIVER or "psycopg2").strip().lower()


def _prepare_jdbc_path():
    """优先使用 ASCII 路径下的 JPype/JayDeBeApi，避免中文用户目录加载 JVM 失败。"""
    pkg_dir = (Config.DB_JDBC_PYTHONPATH or "").strip()
    if pkg_dir and os.path.isdir(pkg_dir) and pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)


def _jdbc_jar() -> str:
    """返回 openGauss 官方 JDBC jar 路径。"""
    jar = (Config.DB_JDBC_JAR or "").strip()
    if jar and os.path.exists(jar):
        return jar

    # 兼容将 jar 放在 backend/vendor/ 下的部署方式
    vendor_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
    if os.path.isdir(vendor_dir):
        for name in os.listdir(vendor_dir):
            if name.lower().endswith(".jar"):
                return os.path.join(vendor_dir, name)

    raise RuntimeError(
        "未找到 openGauss JDBC 驱动，请在 config_local.py 配置 DB_JDBC_JAR"
    )


def _jdbc_get_conn():
    """按线程复用 JDBC 连接，避免每个 SQL 都重新建立连接。"""
    conn = getattr(_jdbc_local, "conn", None)
    if conn is not None:
        try:
            if not conn.jconn.isClosed():
                return conn
        except Exception:
            pass

    conn = _connect()
    _jdbc_local.conn = conn
    return conn


def _connect():
    """创建数据库连接；JDBC 模式每次调用新建连接。"""
    if _backend() == "jdbc":
        _prepare_jdbc_path()
        import jaydebeapi

        conn = jaydebeapi.connect(
            Config.DB_JDBC_CLASS,
            Config.DB_JDBC_URL,
            [Config.DB_USER, Config.DB_PASSWORD],
            _jdbc_jar(),
        )
        conn.jconn.setAutoCommit(False)
        return conn

    if psycopg2 is None:
        raise RuntimeError("缺少 psycopg2，请先安装 backend/requirements.txt")

    return psycopg2.connect(
        host=Config.DB_HOST,
        port=int(Config.DB_PORT),
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        connect_timeout=int(Config.DB_CONNECT_TIMEOUT),
        sslmode=Config.DB_SSLMODE,
        application_name=Config.DB_APPLICATION_NAME,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )


def _get_pg_connection():
    """从 psycopg2 连接池获取连接；首次使用时创建连接池。"""
    global _pg_pool

    if _pg_pool is None:
        with _pool_lock:
            if _pg_pool is None:
                _pg_pool = psycopg2_pool.ThreadedConnectionPool(
                    int(Config.DB_POOL_MIN),
                    int(Config.DB_POOL_MAX),
                    host=Config.DB_HOST,
                    port=int(Config.DB_PORT),
                    dbname=Config.DB_NAME,
                    user=Config.DB_USER,
                    password=Config.DB_PASSWORD,
                    connect_timeout=int(Config.DB_CONNECT_TIMEOUT),
                    sslmode=Config.DB_SSLMODE,
                    application_name=Config.DB_APPLICATION_NAME,
                )
    return _pg_pool.getconn()


def _release_connection(conn):
    """归还或关闭连接。"""
    if _backend() == "jdbc":
        try:
            conn.close()
        except Exception:
            pass
        return

    if _pg_pool is not None:
        _pg_pool.putconn(conn)
    else:
        conn.close()


def _jdbc_rows(cur) -> list[dict]:
    """将 JDBC 游标结果转换为 dict 列表，兼容现有蓝图的字段访问方式。"""
    columns = []
    if cur.description:
        columns = [str(column[0]).lower() for column in cur.description]

    rows = cur.fetchall() or []
    return [dict(zip(columns, row)) for row in rows]


def _jdbc_sql(sql: str) -> str:
    """将 psycopg2 的 %s 占位符转换为 JDBC 使用的 ? 占位符。"""
    return sql.replace("%s", "?")


def _jdbc_query(sql: str, params: tuple) -> list[dict]:
    conn = _jdbc_get_conn()
    try:
        cur = conn.cursor()
        cur.execute(_jdbc_sql(sql), tuple(params or ()))
        rows = _jdbc_rows(cur)
        conn.commit()
        cur.close()
        return rows
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise


def _jdbc_execute(sql: str, params: tuple) -> int:
    conn = _jdbc_get_conn()
    try:
        cur = conn.cursor()
        cur.execute(_jdbc_sql(sql), tuple(params or ()))
        conn.commit()
        rowcount = int(cur.rowcount) if cur.rowcount is not None else 0
        cur.close()
        return rowcount
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise


def query(sql: str, params: tuple = None) -> list[dict]:
    """执行 SELECT，返回 dict 列表"""
    if _backend() == "jdbc":
        return _jdbc_query(sql, params)

    conn = _get_pg_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        _release_connection(conn)


def query_one(sql: str, params: tuple = None) -> dict | None:
    """执行 SELECT，返回单条 dict 或 None"""
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = None) -> int:
    """执行 INSERT/UPDATE/DELETE，返回影响行数"""
    if _backend() == "jdbc":
        return _jdbc_execute(sql, params)

    conn = _get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        _release_connection(conn)


def call_proc(proc_name: str, params: tuple = None) -> list[dict]:
    """调用存储过程，返回结果集"""
    if _backend() == "jdbc":
        conn = _jdbc_get_conn()
        try:
            cur = conn.cursor()
            cur.callproc(proc_name, params or ())
            conn.commit()
            rows = _jdbc_rows(cur)
            cur.close()
            return rows
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise

    conn = _get_pg_connection()
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
        _release_connection(conn)
