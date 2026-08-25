# 校园二手交易与失物招领管理系统

> Flask + openGauss 项目骨架 | 2026-07-14 | 5人小组分工

---

## 快速开始

### 1. 克隆与装依赖
```bash
git clone <仓库地址>
cd campus-trade-system/backend
pip install -r requirements.txt
```

### 2. 配置数据库（不要上传真实密码）
```bash
cp config.py config_local.py
# 编辑 config_local.py 填 DB_PASSWORD，改 app.py 第7行为 from config_local import Config
```

### 3. 初始化数据库（以 omm 用户执行）
```bash
gsql -d postgres -p 5432 -r -f ../database/01_init_instance.sql
```

### 4. 依次执行数据库脚本（以 campus_admin 用户执行）
```bash
gsql -d campus_trade -U campus_admin -p 5432 -r -f ../database/02_create_tables.sql
gsql -d campus_trade -U campus_admin -p 5432 -r -f ../database/03_create_views.sql
gsql -d campus_trade -U campus_admin -p 5432 -r -f ../database/04_create_triggers.sql
gsql -d campus_trade -U campus_admin -p 5432 -r -f ../database/05_create_procedures.sql
gsql -d campus_trade -U campus_admin -p 5432 -r -f ../database/06_insert_sample_data.sql
```

### 5. 启动后端
```bash
cd backend
python app.py
# → http://localhost:5000
```

### 6. 访问前端
浏览器打开 `http://localhost:5000`

---

## 项目结构（文件 → 负责人）

> 每个文件标注了责任人，**改自己的文件，不要改别人的**。

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
│       ├── stats_bp.py        # 数据统计
│       ├── user_bp.py         # 用户公开主页（信用/评价/商品/举报）
│       └── report_bp.py       # 举报提交
├── frontend/
│   ├── login.html             # 登录页
│   ├── register.html          # 注册页
│   ├── index.html             # 首页（商品列表）
│   ├── product_detail.html    # 商品详情 + 立即购买
│   ├── product_publish.html   # 发布商品
│   ├── my_orders.html         # 我的订单（付款/确认/取消/评价）
│   ├── lost_found.html        # 失物招领列表 + 发布 + 认领
│   ├── personal.html          # 个人中心 + 信用记录
│   ├── user_profile.html      # 用户公开主页
│   ├── css/style.css          # 自定义样式
│   ├── js/api.js              # fetch 统一封装
│   ├── js/components.js       # 导航栏/商品卡片/Toast
│   └── admin/
│       ├── statistics.html    # 数据统计面板
│       ├── product_audit.html # 商品审核
│       ├── claim_audit.html   # 认领审核
│       ├── user_manage.html   # 用户管理
│       ├── reports.html       # 举报管理
│       └── logs.html          # 审核日志
├── database/
│   └── 01_init_instance.sql   # 表空间+数据库+用户
└── README.md
```

### backend/ 后端

| 文件 | 负责人 | 功能 |
|------|--------|------|
| `app.py` | **王博华** | Flask 主入口，8个蓝图已注册 |
| `config.py` | **王博华** | 数据库 / JWT / 上传 / 管理员邀请码 配置 |
| `db.py` | **王博华** | 数据库连接模块（query / execute） |
| `auth.py` | **王博华** | JWT token + `@login_required` + `@admin_required` |
| `requirements.txt` | **王博华** | pip 依赖清单 |
| `blueprints/auth_bp.py` | **王博华** | 登录 / 注册（学生+管理员）/ 个人信息 / 信用记录 |
| `blueprints/product_bp.py` | **熊倡** | 商品发布 / 列表 / 搜索 / 详情 / 收藏 |
| `blueprints/order_bp.py` | **吴裕勇** | 下单 / 支付 / 确认收货 / 评价 |
| `blueprints/lostfound_bp.py` | **王旭坤** | 失物发布 / 列表 / 认领申请 |
| `blueprints/admin_bp.py` | **刘子懿** | 商品审核 / 认领审核 / 用户管理 / 举报 / 日志 |
| `blueprints/stats_bp.py` | **王博华** | 4个统计视图的查询接口 |
| `blueprints/user_bp.py` | **王博华** | 用户公开主页（信用分 / 评价 / 在售商品 / 被举报记录） |
| `blueprints/report_bp.py` | **王博华** | 举报提交（校验对象 / 禁止自举报 / 防重复） |

### frontend/ 前端页面

| 文件 | 负责人 | 功能 |
|------|--------|------|
| `login.html` | **王博华** | 登录页 |
| `register.html` | **王博华** | 注册页（学生 / 管理员 + 邀请码） |
| `personal.html` | **王博华** | 个人中心 + 信用记录 + 收到的评价 + 被举报记录 |
| `user_profile.html` | **王博华** | 用户公开主页（信用分 / 商品 / 评价 / 违规记录） |
| `index.html` | **熊倡** | 首页（分类侧栏 + 搜索 + 商品卡片分页） |
| `product_detail.html` | **熊倡** | 商品详情 + 立即购买按钮 |
| `product_publish.html` | **熊倡** | 发布商品表单 |
| `my_orders.html` | **吴裕勇** | 我的订单（付款 / 确认收货 / 取消 / 评价按钮） |
| `lost_found.html` | **王旭坤** | 失物招领列表 + 发布弹窗 + 认领 |
| `css/style.css` | **王博华** | 暖色主题（公共样式 / 卡片悬停 / 后台侧栏） |
| `js/api.js` | **王博华** | fetch 统一封装（token 注入 / 401 跳转） |
| `js/components.js` | **王博华** | 导航栏 / 商品卡片 / Toast 公共组件 |
| `admin/statistics.html` | **王博华** | 数据统计面板（4 个统计视图） |
| `admin/product_audit.html` | **刘子懿** | 商品审核（通过 / 驳回） |
| `admin/claim_audit.html` | **刘子懿** | 认领申请审核 |
| `admin/user_manage.html` | **刘子懿** | 用户管理（启用 / 禁用） |
| `admin/reports.html` | **王博华** | 举报管理（待处理 / 核实扣分 / 驳回） |
| `admin/logs.html` | **刘子懿** | 审核日志 |

### database/ 数据库脚本

| 文件 | 负责人 | 说明 |
|------|--------|------|
| `01_init_instance.sql` | **王博华** | 表空间 + 数据库 + 用户授权 |
| `02a_tables_auth.sql` | **王博华** | users / roles / user_roles 3 张表 DDL |
| `02b_tables_product.sql` | **熊倡** | categories / products / product_images / favorites 4 张表 DDL |
| `02c_tables_order.sql` | **吴裕勇** | orders / payments / reviews / credit_records 4 张表 DDL |
| `02d_tables_lostfound.sql` | **王旭坤** | lost_found / claim_requests 2 张表 DDL |
| `02e_tables_admin.sql` | **刘子懿** | reports / audit_logs 2 张表 DDL |
| `02_create_tables.sql` | **王博华（整合）** | 收集以上 5 份 DDL，合并为全量建表脚本 |
| `03_create_views.sql` | **王博华** | 4 个统计视图 |
| `04_create_triggers.sql` | **吴裕勇** | trg_order_complete / trg_review_insert |
| `05_create_procedures.sql` | **吴裕勇 ×2 + 刘子懿 ×1** | sp_create_order / sp_confirm_order / sp_audit_claim |
| `06_insert_sample_data.sql` | **王博华** | 测试样本数据（每表 ≥ 5 条） |

### docs/ 文档

| 文件 | 负责人 | 说明 |
|------|--------|------|
| `需求规格说明书` | **王博华** | V1.0 基准文档 |
| `大作业简介及分工情况` | **王博华** | 已确认的分工 |
| `实验报告` | **王博华** | 主笔（各人提供模块素材） |
| `测试用例` | **王博华** | 覆盖答辩 8 步演示流程 |
| `演示视频` | **王博华** | 答辩演示录屏 |
| `答辩 PPT` | **王博华** | |
| `个人模块文档` | **各成员** | 自己模块的表字段说明 + API 列表 + 页面截图 |

---

## Git 分支策略

```
main  ← 稳定可演示版本（仅从 dev 合并）
└── dev ← 所有人日常工作分支
```

**日常开发**（所有人）：
```bash
git checkout dev && git pull origin dev
# 改自己负责的文件
git add . && git commit -m "feat: 说明改了什么"
git push origin dev
```

**王博华验证后合到 main**：
```bash
git checkout main && git merge dev && git push origin main
```

---

## API 统一响应格式

```json
{ "code": 200, "data": {...}, "msg": "ok" }
{ "code": 400, "msg": "参数错误" }
{ "code": 401, "msg": "请先登录" }
{ "code": 403, "msg": "需要管理员权限" }
```

---

## 前端开发规范

- fetch 请求全部通过 `API.get/post/put/delete` 调用
- `API.user()` 获取当前登录用户，`API.token()` 获取 token
- 登录成功自动存 token 到 localStorage，401 自动跳转登录页
- Toast 提示用 `showToast(msg, 'success'|'error')`
- 页面引入顺序：Bootstrap CSS → style.css → Bootstrap JS → api.js → components.js

---

## 后端开发规范

- 路由装饰器：`@login_required`（必须登录）/ `@admin_required`（必须管理员）
- 数据库操作：`query(sql, params)` / `query_one(sql, params)` / `execute(sql, params)`
- **复杂 SQL 逻辑放存储过程**，API 仅负责调用
- 所有金额用 DECIMAL(10,2)，前端用 `Number(x).toFixed(2)` 显示

---

## 信用分规则（V1.1）

| 触发事件 | 变动 |
|----------|------|
| 交易完成 | +2 |
| 收到 5 星 | +3 |
| 收到 4 星 | +2 |
| 收到 3 星 | 0 |
| 收到 2 星 | -2 |
| 收到 1 星 | -5 |
| 被举报核实 | -10 |
| 新用户初始 | 100 |

> ⚠️ V1.0 旧值（+5/+5/+3/0/-3/-3/-10）已废弃。

---

## 各成员负责速查表

| 成员 | 后端蓝图 | 前端页面 | 数据库对象 |
|------|----------|----------|-----------|
| **王博华** | auth_bp + stats_bp + user_bp + report_bp + app/db/auth/config | login / register / personal / user_profile / statistics / reports + css/js | 3张表 + 4视图 + 整合 + 样本数据 + 全部文档 |
| **熊倡** | product_bp | index / product_detail / product_publish | 4张表 DDL + 索引 |
| **吴裕勇** | order_bp | my_orders | 4张表 + 2触发器 + 2存储过程 |
| **王旭坤** | lostfound_bp | lost_found | 2张表 DDL |
| **刘子懿** | admin_bp | admin/ 审核与用户管理页面 | 2张表 + 1存储过程 |
