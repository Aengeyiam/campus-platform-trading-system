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

class Config:
    # ---- openGauss 数据库 ----
    DB_HOST = "localhost"
    DB_PORT = 5432             # openGauss 默认端口
    DB_NAME = "campus_trade"
    DB_USER = "campus_admin"
    DB_PASSWORD = "your_password_here"

    # ---- Flask ----
    SECRET_KEY = "change-me-to-random-string-in-production"
    DEBUG = True

    # ---- JWT Token ----
    TOKEN_EXPIRE_HOURS = 24    # 登录有效期

    # ---- 上传 ----
    UPLOAD_FOLDER = "../frontend/uploads"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB


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
