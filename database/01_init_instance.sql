-- ============================================================
--  campus-trade 数据库初始化脚本
--  用途：表空间 + 数据库 + 用户（通过 omm 账户执行）
-- ============================================================

-- 1. 创建表空间
CREATE TABLESPACE campus_ts
  LOCATION '/opt/opengauss/data/campus';

-- 2. 创建数据库
CREATE DATABASE campus_trade
  TABLESPACE campus_ts
  ENCODING 'UTF-8';

-- 3. 创建应用用户
CREATE USER campus_admin WITH PASSWORD 'Campus@2026';

-- 4. 授权
GRANT ALL PRIVILEGES ON DATABASE campus_trade TO campus_admin;

-- 切换到 campus_trade 数据库后执行：
-- \c campus_trade
-- GRANT ALL ON SCHEMA public TO campus_admin;

-- ============================================================
-- 表空间位置说明：
--   请根据实际 openGauss 安装路径修改 LOCATION
--   常用路径：
--     /opt/opengauss/data/campus
--     /home/omm/opengauss/data/campus
-- ============================================================
