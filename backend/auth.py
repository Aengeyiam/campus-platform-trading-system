"""
认证模块：token 生成/校验、登录装饰器
用法：
  from auth import generate_token, login_required, get_current_user
"""
import jwt
import hashlib
import datetime
from functools import wraps
from flask import request, g
from config import Config


# ---- Token ----

def generate_token(user_id: int, student_id: str, role: str) -> str:
    """生成 JWT token"""
    payload = {
        "user_id": user_id,
        "student_id": student_id,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=Config.TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> dict | None:
    """校验 token，返回 payload 或 None"""
    try:
        return jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user() -> dict:
    """在请求上下文内获取当前登录用户信息"""
    return g.current_user if hasattr(g, "current_user") else None


# ---- 装饰器 ----

def login_required(f):
    """必须登录"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            token = request.cookies.get("token", "")
        if not token:
            return {"code": 401, "msg": "请先登录"}, 401
        payload = verify_token(token)
        if not payload:
            return {"code": 401, "msg": "登录已过期，请重新登录"}, 401
        g.current_user = payload
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """必须管理员"""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if g.current_user.get("role") != "管理员":
            return {"code": 403, "msg": "需要管理员权限"}, 403
        return f(*args, **kwargs)
    return decorated


# ---- 密码 ----

def hash_password(password: str) -> str:
    """SHA-256 加密"""
    return hashlib.sha256(password.encode()).hexdigest()
