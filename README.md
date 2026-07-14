# 校园二手交易与失物招领系统

> Flask + openGauss 项目骨架 | 2026-07-14

## 快速开始

### 1. 安装依赖
```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置数据库
```bash
# 复制并修改配置
cp config.py config_local.py
# 编辑 config_local.py 中的 DB_HOST / DB_PASSWORD
# 然后在 app.py 中改为 from config_local import Config
```

### 3. 初始化数据库（以 omm 用户执行）
```bash
gsql -d postgres -p 5432 -f ../database/01_init_instance.sql
```

### 4. 建表（以 campus_admin 用户执行）
```bash
gsql -d campus_trade -U campus_admin -p 5432 -f ../database/03_create_tables.sql
```

### 5. 启动后端
```bash
cd backend
python app.py
# → http://localhost:5000
```

### 6. 访问前端
浏览器打开 `http://localhost:5000`，自动跳转登录页。

## 项目结构

```
campus-trade-system/
├── backend/
│   ├── app.py                 # Flask 主入口
│   ├── config.py              # 配置文件（DB/JWT/上传）
│   ├── db.py                  # 数据库连接模块（query/execute）
│   ├── auth.py                # JWT token / login_required 装饰器
│   ├── requirements.txt       # Python 依赖
│   └── blueprints/
│       ├── auth_bp.py         # 登录/注册/个人信息
│       ├── product_bp.py      # 商品 CRUD + 收藏
│       ├── order_bp.py        # 下单/支付/确认/评价
│       ├── lostfound_bp.py    # 失物招领 + 认领
│       ├── admin_bp.py        # 管理员审核/用户管理/举报
│       └── stats_bp.py        # 数据统计
├── frontend/
│   ├── login.html             # 登录页
│   ├── register.html          # 注册页
│   ├── index.html             # 首页（商品列表）
│   ├── product_detail.html    # 商品详情 + 立即购买
│   ├── product_publish.html   # 发布商品
│   ├── my_orders.html         # 我的订单（付款/确认/取消/评价）
│   ├── lost_found.html        # 失物招领列表 + 发布 + 认领
│   ├── personal.html          # 个人中心 + 信用记录
│   ├── css/style.css          # 自定义样式
│   ├── js/api.js              # fetch 统一封装
│   ├── js/components.js       # 导航栏/商品卡片/Toast
│   └── admin/
│       ├── statistics.html    # 数据统计面板
│       ├── product_audit.html # 商品审核
│       ├── claim_audit.html   # 认领审核
│       ├── user_manage.html   # 用户管理
│       └── logs.html          # 审核日志
├── database/
│   └── 01_init_instance.sql   # 表空间+数据库+用户
└── README.md
```

## API 统一响应格式

```json
{ "code": 200, "data": {...}, "msg": "ok" }
{ "code": 400, "msg": "参数错误" }
{ "code": 401, "msg": "请先登录" }
{ "code": 403, "msg": "需要管理员权限" }
```

## 前端开发规范

- 所有 fetch 请求通过 `API.get/post/put/delete` 调用
- `API.user()` 获取当前登录用户，`API.token()` 获取 token
- 登录成功自动存 token 到 localStorage
- 401 响应自动跳转登录页
- Toast 提示用 `showToast(msg, 'success'|'error')`
- 页面需引入顺序: Bootstrap CSS → style.css → Bootstrap JS → api.js → components.js

## 后端开发规范

- 路由装饰器: `@login_required`（必须登录）/ `@admin_required`（必须管理员）
- 数据库操作: `query(sql, params)` / `query_one(sql, params)` / `execute(sql, params)`
- 不要在 API 里写复杂 SQL——复杂逻辑放存储过程
- 所有金额用 DECIMAL(10,2)，前端用 `Number(x).toFixed(2)` 显示

## 各成员负责的蓝图文件

| 成员 | 文件 | 前缀 |
|------|------|------|
| 王博华 | `auth_bp.py` + `stats_bp.py` | `/api/auth/*` `/api/stats/*` |
| 熊倡 | `product_bp.py` | `/api/products/*` |
| 吴裕勇 | `order_bp.py` | `/api/orders/*` |
| 王旭坤 | `lostfound_bp.py` | `/api/lostfound/*` |
| 刘子懿 | `admin_bp.py` | `/api/admin/*` |
