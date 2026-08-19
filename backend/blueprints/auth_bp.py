"""
认证蓝图：登录 / 注册 / 个人信息
负责人：王博华
"""
from flask import Blueprint, request, g
from db import query, query_one, execute
from auth import generate_token, login_required, hash_password
import psycopg2  # 用于捕获 UniqueViolation / ForeignKeyViolation

auth_bp = Blueprint("auth", __name__)


# ============================================================
#  POST /api/auth/register
#  body: { student_id, user_name, password, phone?, qq? }
# ============================================================
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    student_id = (data.get("student_id") or "").strip()
    user_name = (data.get("user_name") or "").strip()
    password = (data.get("password") or "").strip()

    # 校验
    if not student_id or not user_name or not password:
        return {"code": 400, "msg": "学号、姓名、密码不能为空"}, 400
    if len(password) < 6:
        return {"code": 400, "msg": "密码至少6位"}, 400

    # 学号唯一
    exist = query_one("SELECT user_id FROM users WHERE student_id = %s", (student_id,))
    if exist:
        return {"code": 400, "msg": "该学号已被注册"}, 400

    # 插入用户
    hashed = hash_password(password)
    phone = data.get("phone", "") or ""
    qq = data.get("qq", "") or ""

    # 动态查找 '学生' 角色的 role_id（避免硬编码假定 role_id=1）
    student_role = query_one("SELECT role_id FROM roles WHERE role_name = %s", ("学生",))
    if not student_role:
        # 极端情况：roles 表为空。兜底插入，避免注册链路全断。
        execute(
            "INSERT INTO roles (role_name, description) VALUES (%s, %s) "
            "ON CONFLICT (role_name) DO NOTHING",
            ("学生", "普通学生用户，可买卖商品、发布失物招领"),
        )
        student_role = query_one("SELECT role_id FROM roles WHERE role_name = %s", ("学生",))
        if not student_role:
            return {"code": 500, "msg": "未找到学生角色，请管理员补齐 roles 表"}, 500
    student_role_id = student_role["role_id"]

    try:
        execute(
            """INSERT INTO users (student_id, user_name, password, nickname, phone, qq)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (student_id, user_name, hashed, user_name, phone, qq),
        )
        user = query_one("SELECT user_id FROM users WHERE student_id = %s", (student_id,))
        if not user:
            return {"code": 500, "msg": "用户已写入但回查失败，请重试"}, 500

        # 分配学生角色
        execute(
            "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)",
            (user["user_id"], student_role_id),
        )
    except psycopg2.errors.UniqueViolation:
        return {"code": 400, "msg": "该学号已被注册"}, 400
    except psycopg2.errors.ForeignKeyViolation as e:
        return {"code": 500, "msg": f"角色表关联异常: {e}"}, 500
    except Exception as e:
        return {"code": 500, "msg": f"注册失败: {type(e).__name__}: {e}"}, 500

    return {"code": 200, "msg": "注册成功"}


# ============================================================
#  POST /api/auth/login
#  body: { student_id, password }
#  返回: { token, role }
# ============================================================
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    student_id = (data.get("student_id") or "").strip()
    password = (data.get("password") or "").strip()

    if not student_id or not password:
        return {"code": 400, "msg": "学号或密码不能为空"}, 400

    hashed = hash_password(password)
    # 一个用户可能有多个角色（如学生+管理员），
    # 必须让“管理员”排第一，query_one 才能取到管理员角色。
    user = query_one(
        """SELECT u.user_id, u.student_id, u.user_name, u.status, r.role_name
           FROM users u
           JOIN user_roles ur ON u.user_id = ur.user_id
           JOIN roles r ON ur.role_id = r.role_id
           WHERE u.student_id = %s AND u.password = %s
           ORDER BY CASE WHEN r.role_name = '管理员' THEN 0 ELSE 1 END, ur.role_id""",
        (student_id, hashed),
    )

    if not user:
        return {"code": 401, "msg": "学号或密码错误"}, 401
    if user["status"] == 1:
        return {"code": 403, "msg": "账号已被禁用"}, 403

    token = generate_token(user["user_id"], user["student_id"], user["role_name"])
    return {
        "code": 200,
        "data": {
            "token": token,
            "user_id": user["user_id"],
            "student_id": user["student_id"],
            "user_name": user["user_name"],
            "role": user["role_name"],
        },
    }


# ============================================================
#  GET  /api/auth/profile
#  PUT  /api/auth/profile
# ============================================================
@auth_bp.route("/profile", methods=["GET"])
@login_required
def get_profile():
    user = query_one(
        """SELECT user_id, student_id, user_name, nickname, phone, qq,
                  credit_score, created_at
           FROM users WHERE user_id = %s""",
        (g.current_user["user_id"],),
    )
    if not user:
        return {"code": 404, "msg": "用户不存在"}, 404
    return {"code": 200, "data": user}


@auth_bp.route("/profile", methods=["PUT"])
@login_required
def update_profile():
    data = request.get_json()
    uid = g.current_user["user_id"]
    execute(
        """UPDATE users SET nickname=%s, phone=%s, qq=%s, updated_at=NOW()
           WHERE user_id=%s""",
        (data.get("nickname", ""), data.get("phone", ""), data.get("qq", ""), uid),
    )
    return {"code": 200, "msg": "保存成功"}


# ============================================================
#  GET  /api/auth/credit   当前用户信用分
# ============================================================
@auth_bp.route("/credit", methods=["GET"])
@login_required
def my_credit():
    user = query_one(
        "SELECT credit_score FROM users WHERE user_id = %s",
        (g.current_user["user_id"],),
    )
    return {"code": 200, "data": {"credit_score": user["credit_score"]}}


# ============================================================
#  GET  /api/auth/credit/records   信用记录
# ============================================================
@auth_bp.route("/credit/records", methods=["GET"])
@login_required
def credit_records():
    rows = query(
        """SELECT change_type, change_value, score_after, remark, created_at
           FROM credit_records WHERE user_id = %s
           ORDER BY created_at DESC LIMIT 50""",
        (g.current_user["user_id"],),
    )
    return {"code": 200, "data": rows}
