"""
数据库连接模块
所有蓝图通过 from db import query, query_one, execute, call_proc 使用

连接方式：
  - psycopg2：默认连接池方案
  - jdbc：通过官方 JDBC 驱动连接 openGauss
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


# ============================================================
# JDBC
# ============================================================

def _prepare_jdbc_path():
    """优先使用 ASCII 路径下的 JPype/JayDeBeApi。"""
    pkg_dir = (Config.DB_JDBC_PYTHONPATH or "").strip()

    if pkg_dir and os.path.isdir(pkg_dir) and pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)


def _jdbc_jar() -> str:
    """返回 openGauss 官方 JDBC jar 路径。"""
    jar = (Config.DB_JDBC_JAR or "").strip()

    if jar and os.path.exists(jar):
        return jar

    vendor_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "vendor",
    )

    if os.path.isdir(vendor_dir):
        for name in os.listdir(vendor_dir):
            if name.lower().endswith(".jar"):
                return os.path.join(vendor_dir, name)

    raise RuntimeError(
        "未找到 openGauss JDBC 驱动，请在 config_local.py 配置 DB_JDBC_JAR"
    )


def _connect():
    """创建数据库连接。"""

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
        raise RuntimeError(
            "缺少 psycopg2，请先安装 backend/requirements.txt"
        )

    return psycopg2.connect(
        host=Config.DB_HOST,
        port=int(Config.DB_PORT),
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,

        connect_timeout=int(Config.DB_CONNECT_TIMEOUT),
        sslmode=Config.DB_SSLMODE,
        application_name=Config.DB_APPLICATION_NAME,

        # TCP keepalive
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
    )


def _jdbc_get_conn():
    """按线程复用 JDBC 连接。"""

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


def _jdbc_rows(cur) -> list[dict]:
    """将 JDBC 游标结果转换为 dict 列表。"""

    columns = []

    if cur.description:
        columns = [
            str(column[0]).lower()
            for column in cur.description
        ]

    rows = cur.fetchall() or []

    return [
        dict(zip(columns, row))
        for row in rows
    ]


def _jdbc_sql(sql: str) -> str:
    """将 psycopg2 的 %s 转换为 JDBC ?。"""

    return sql.replace("%s", "?")


def _jdbc_query(sql: str, params: tuple = None) -> list[dict]:
    conn = _jdbc_get_conn()

    try:
        cur = conn.cursor()

        cur.execute(
            _jdbc_sql(sql),
            tuple(params or ()),
        )

        rows = _jdbc_rows(cur)

        # SELECT 也结束事务
        conn.commit()

        cur.close()

        return rows

    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

        raise


def _jdbc_execute(sql: str, params: tuple = None) -> int:
    conn = _jdbc_get_conn()

    try:
        cur = conn.cursor()

        cur.execute(
            _jdbc_sql(sql),
            tuple(params or ()),
        )

        rowcount = (
            int(cur.rowcount)
            if cur.rowcount is not None
            else 0
        )

        conn.commit()

        cur.close()

        return rowcount

    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

        raise


# ============================================================
# psycopg2 connection pool
# ============================================================

def _get_pg_connection():
    """
    从 psycopg2 ThreadedConnectionPool 获取连接。
    第一次使用时创建连接池。
    """

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

                    # 防止长期空闲连接被系统直接断掉
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=3,
                )

    return _pg_pool.getconn()


def _release_connection(conn):
    """正常连接归还连接池。"""

    if conn is None:
        return

    if _backend() == "jdbc":
        try:
            conn.close()
        except Exception:
            pass

        return

    if _pg_pool is not None:
        try:
            _pg_pool.putconn(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
    else:
        try:
            conn.close()
        except Exception:
            pass


def _discard_pg_connection(conn):
    """
    丢弃坏掉的 psycopg2 连接。

    注意：
    不能把 OperationalError 的连接重新放回连接池。
    """

    if conn is None:
        return

    if _pg_pool is not None:
        try:
            _pg_pool.putconn(
                conn,
                close=True,
            )
            return
        except Exception:
            pass

    try:
        conn.close()
    except Exception:
        pass


def _get_healthy_pg_connection():
    """
    从连接池获取一条可用连接。

    解决 ThreadedConnectionPool 中 stale connection 被继续复用的问题。
    """

    last_error = None

    # 最多尝试两条连接
    for _ in range(2):

        conn = None

        try:
            conn = _get_pg_connection()

            # psycopg2 已明确标记关闭
            if conn.closed:
                _discard_pg_connection(conn)
                conn = None
                continue

            # 清理上一次可能残留的事务状态
            try:
                conn.rollback()
            except Exception:
                _discard_pg_connection(conn)
                conn = None
                continue

            # 真正探活
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

            # SELECT 1 会开启事务，因此必须结束
            conn.rollback()

            return conn

        except (
            psycopg2.OperationalError,
            psycopg2.InterfaceError,
        ) as exc:

            last_error = exc

            if conn is not None:
                _discard_pg_connection(conn)

        except Exception:

            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass

                _release_connection(conn)

            raise

    if last_error is not None:
        raise last_error

    raise RuntimeError("无法获取可用数据库连接")


# ============================================================
# Public database API
# ============================================================

def query(
    sql: str,
    params: tuple = None,
) -> list[dict]:
    """
    执行查询，返回 dict 列表。

    psycopg2 注意：
    SELECT 也会自动开启事务，因此成功后 rollback，
    将连接恢复为干净状态后再放回连接池。
    """

    if _backend() == "jdbc":
        return _jdbc_query(sql, params)

    conn = None
    broken = False

    try:
        conn = _get_healthy_pg_connection()

        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                sql,
                params,
            )

            rows = cur.fetchall()

        # 对 SELECT 来说 rollback 只是结束事务，
        # 不会撤销任何实际查询结果。
        conn.rollback()

        return rows

    except (
        psycopg2.OperationalError,
        psycopg2.InterfaceError,
    ):
        broken = True

        raise

    except Exception:

        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass

        raise

    finally:

        if conn is not None:
            if broken:
                _discard_pg_connection(conn)
            else:
                _release_connection(conn)


def query_one(
    sql: str,
    params: tuple = None,
) -> dict | None:
    """执行查询，返回第一行。"""

    rows = query(
        sql,
        params,
    )

    return rows[0] if rows else None


def execute(
    sql: str,
    params: tuple = None,
) -> int:
    """
    执行 INSERT / UPDATE / DELETE。

    注意：
    写操作发生网络异常时，不自动重放 SQL，
    因为无法百分百确认服务端是否已经执行成功。
    """

    if _backend() == "jdbc":
        return _jdbc_execute(
            sql,
            params,
        )

    conn = None
    broken = False

    try:
        conn = _get_healthy_pg_connection()

        with conn.cursor() as cur:

            cur.execute(
                sql,
                params,
            )

            rowcount = cur.rowcount

        conn.commit()

        return rowcount

    except (
        psycopg2.OperationalError,
        psycopg2.InterfaceError,
    ):
        broken = True

        raise

    except Exception:

        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass

        raise

    finally:

        if conn is not None:
            if broken:
                _discard_pg_connection(conn)
            else:
                _release_connection(conn)


def execute_returning(
    sql: str,
    params: tuple = None,
) -> dict | None:
    """
    执行 INSERT / UPDATE / DELETE ... RETURNING，提交事务并返回第一行。

    注意：
    query()/query_one() 只用于只读查询（内部用 rollback 结束事务），
    任何带 RETURNING 的写操作必须走本函数，否则数据会被回滚、不会落库。
    """

    if _backend() == "jdbc":
        # JDBC 的 _jdbc_query 会提交事务，语义一致
        rows = _jdbc_query(sql, params)

        return rows[0] if rows else None

    conn = None
    broken = False

    try:
        conn = _get_healthy_pg_connection()

        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                sql,
                params,
            )

            row = cur.fetchone()

        conn.commit()

        return row

    except (
        psycopg2.OperationalError,
        psycopg2.InterfaceError,
    ):
        broken = True

        raise

    except Exception:

        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass

        raise

    finally:

        if conn is not None:
            if broken:
                _discard_pg_connection(conn)
            else:
                _release_connection(conn)


def call_proc(
    proc_name: str,
    params: tuple = None,
) -> list[dict]:
    """调用存储过程。"""

    if _backend() == "jdbc":

        conn = _jdbc_get_conn()

        try:
            cur = conn.cursor()

            cur.callproc(
                proc_name,
                params or (),
            )

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

    conn = None
    broken = False

    try:
        conn = _get_healthy_pg_connection()

        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.callproc(
                proc_name,
                params or (),
            )

            results = []

            try:
                for row in cur.fetchall():
                    results.append(row)
            except psycopg2.ProgrammingError:
                # 某些 procedure 不返回结果集
                pass

        conn.commit()

        return results

    except (
        psycopg2.OperationalError,
        psycopg2.InterfaceError,
    ):
        broken = True

        raise

    except Exception:

        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass

        raise

    finally:

        if conn is not None:
            if broken:
                _discard_pg_connection(conn)
            else:
                _release_connection(conn)
