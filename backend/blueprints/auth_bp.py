"""
认证蓝图：登录 / 注册 / 个人信息
负责人：王博华
"""
from flask import Blueprint, request
from db import query, query_one, execute
from auth import generate_token, login_required, hash_password

auth_bp = Blueprint("auth", __name__)


# ============================================================
#  POST /api/auth/register
#  body: { student_id, user_name, password, phone?, qq? }
# ============================================================
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
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
    phone = data.get("phone", "")
    qq = data.get("qq", "")
    execute(
        """INSERT INTO users (student_id, user_name, password, nickname, phone, qq)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (student_id, user_name, hashed, user_name, phone, qq),
    )
    user = query_one("SELECT user_id FROM users WHERE student_id = %s", (student_id,))

    # 分配学生角色 (role_id=1)
    execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES (%s, 1)",
        (user["user_id"],),
    )

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
    user = query_one(
        """SELECT u.user_id, u.student_id, u.user_name, u.status, r.role_name
           FROM users u
           JOIN user_roles ur ON u.user_id = ur.user_id
           JOIN roles r ON ur.role_id = r.role_id
           WHERE u.student_id = %s AND u.password = %s""",
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
        (request.g.current_user["user_id"],),
    )
    if not user:
        return {"code": 404, "msg": "用户不存在"}, 404
    return {"code": 200, "data": user}


@auth_bp.route("/profile", methods=["PUT"])
@login_required
def update_profile():
    data = request.get_json()
    uid = request.g.current_user["user_id"]
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
        (request.g.current_user["user_id"],),
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
        (request.g.current_user["user_id"],),
    )
    return {"code": 200, "data": rows}
