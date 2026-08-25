"""
=============================
 校园二手交易与失物招领系统
 campus-trade 配置文件
=============================
复制此文件为 config.py 并修改实际值

使用方法：
  from config import Config
  db = Config.get_db()
"""
import os


class Config:
    # ---- openGauss 数据库 ----
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "15432"))
    DB_NAME = "campus_trade"
    DB_USER = "campus_admin"
    DB_PASSWORD = "password"

    # ---- 数据库连接优化 ----
    DB_DRIVER = os.getenv("DB_DRIVER", "psycopg2")
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))
    DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
    DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))
    DB_SSLMODE = os.getenv("DB_SSLMODE", "disable")
    DB_APPLICATION_NAME = os.getenv("DB_APPLICATION_NAME", "campus-trade")

    # openGauss 官方 JDBC 驱动参数（Windows 本地兼容 sha256 认证）
    DB_JDBC_CLASS = os.getenv("DB_JDBC_CLASS", "org.opengauss.Driver")
    DB_JDBC_URL = os.getenv(
        "DB_JDBC_URL",
        f"jdbc:opengauss://{DB_HOST}:{DB_PORT}/{DB_NAME}",
    )
    DB_JDBC_JAR = os.getenv("DB_JDBC_JAR", "")
    # Windows 中文用户目录会导致 JPype 加载 JVM 失败，这里允许指定纯 ASCII 包目录
    DB_JDBC_PYTHONPATH = os.getenv("DB_JDBC_PYTHONPATH", "")

    # ---- Flask ----
    SECRET_KEY = "change-me-to-random-string-in-production"
    DEBUG = True

    # ---- JWT Token ----
    TOKEN_EXPIRE_HOURS = 24    # 登录有效期

    # ---- 管理员注册邀请码（注册管理员账号时需填写） ----
    # 建议在 config_local.py 中覆盖为你们小组自己商定的口令，避免默认值被公开。
    ADMIN_INVITE_CODE = os.getenv("ADMIN_INVITE_CODE", "campus2026")

    # ---- 上传 ----
    UPLOAD_FOLDER = "../frontend/uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB


# 本地真实连接配置：backend/config_local.py（已被 .gitignore 排除）
try:
    from config_local import Config as LocalConfig

    for _name, _value in vars(LocalConfig).items():
        if not _name.startswith("__") and not callable(_value):
            setattr(Config, _name, _value)
except ImportError:
    pass


# ============================================================
# openGauss 安装后执行（以 omm 用户）：
#
#   gsql -d postgres -p 5432 -r
#   CREATE TABLESPACE campus_ts LOCATION '/opt/opengauss/data/campus';
#   CREATE DATABASE campus_trade TABLESPACE campus_ts ENCODING 'UTF-8';
#   CREATE USER campus_admin WITH PASSWORD 'your_password_here';
#   GRANT ALL PRIVILEGES ON DATABASE campus_trade TO campus_admin;
#   \c campus_trade
#   GRANT ALL ON SCHEMA public TO campus_admin;
# ============================================================
