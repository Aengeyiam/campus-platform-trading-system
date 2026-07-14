"""
失物招领蓝图：发布 / 列表 / 详情 / 编辑 / 关闭 / 认领申请
负责人：王旭坤
"""
from flask import Blueprint, request
from db import query, query_one, execute
from auth import login_required

lostfound_bp = Blueprint("lostfound", __name__)


# ============================================================
#  POST /api/lostfound   发布失物/拾物
#  body: { type, title, description, location, lf_date, contact }
# ============================================================
@lostfound_bp.route("", methods=["POST"])
@login_required
def publish():
    data = request.get_json()
    uid = request.g.current_user["user_id"]

    required = ["type", "title", "description", "location", "lf_date", "contact"]
    for f in required:
        if not data.get(f):
            return {"code": 400, "msg": f"缺少字段: {f}"}, 400
    if data["type"] not in ("失物", "拾物"):
        return {"code": 400, "msg": "类型必须是'失物'或'拾物'"}, 400

    execute(
        """INSERT INTO lost_found (publisher_id, type, title, description, location, lf_date, contact)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (uid, data["type"], data["title"], data["description"],
         data["location"], data["lf_date"], data["contact"]),
    )
    return {"code": 200, "msg": "发布成功"}


# ============================================================
#  GET  /api/lostfound   列表
#  query: ?type=失物|拾物&keyword=&page=1&size=12
# ============================================================
@lostfound_bp.route("", methods=["GET"])
def list_all():
    lf_type = request.args.get("type", "").strip()
    keyword = request.args.get("keyword", "").strip()
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 12))
    offset = (page - 1) * size

    where = "WHERE 1=1"
    params = []
    if lf_type:
        where += " AND lf.type = %s"
        params.append(lf_type)
    if keyword:
        where += " AND (lf.title LIKE %s OR lf.description LIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    count_sql = f"SELECT COUNT(*) AS cnt FROM lost_found lf {where}"
    total = query_one(count_sql, tuple(params))["cnt"]

    rows = query(
        f"""SELECT lf.*, u.user_name AS publisher_name
           FROM lost_found lf
           JOIN users u ON lf.publisher_id = u.user_id
           {where}
           ORDER BY lf.created_at DESC
           LIMIT %s OFFSET %s""",
        tuple(params) + (size, offset),
    )
    return {"code": 200, "data": {"total": total, "page": page, "items": rows}}


# ============================================================
#  GET  /api/lostfound/<id>   详情
# ============================================================
@lostfound_bp.route("/<int:lid>", methods=["GET"])
def detail(lid):
    row = query_one(
        """SELECT lf.*, u.user_name AS publisher_name
           FROM lost_found lf JOIN users u ON lf.publisher_id = u.user_id
           WHERE lf.lf_id = %s""",
        (lid,),
    )
    if not row:
        return {"code": 404, "msg": "不存在"}, 404
    return {"code": 200, "data": row}


# ============================================================
#  PUT  /api/lostfound/<id>   编辑
# ============================================================
@lostfound_bp.route("/<int:lid>", methods=["PUT"])
@login_required
def edit(lid):
    data = request.get_json()
    uid = request.g.current_user["user_id"]

    lf = query_one("SELECT publisher_id FROM lost_found WHERE lf_id=%s", (lid,))
    if not lf:
        return {"code": 404, "msg": "记录不存在"}, 404
    if lf["publisher_id"] != uid:
        return {"code": 403, "msg": "只能编辑自己发布的信息"}, 403

    execute(
        """UPDATE lost_found SET title=%s, description=%s, location=%s,
           contact=%s, updated_at=NOW() WHERE lf_id=%s""",
        (data.get("title"), data.get("description"), data.get("location"),
         data.get("contact"), lid),
    )
    return {"code": 200, "msg": "保存成功"}


# ============================================================
#  PUT  /api/lostfound/<id>/close   关闭
# ============================================================
@lostfound_bp.route("/<int:lid>/close", methods=["PUT"])
@login_required
def close(lid):
    uid = request.g.current_user["user_id"]
    lf = query_one("SELECT publisher_id FROM lost_found WHERE lf_id=%s", (lid,))
    if not lf:
        return {"code": 404, "msg": "记录不存在"}, 404
    if lf["publisher_id"] != uid:
        return {"code": 403, "msg": "无权限"}, 403

    execute(
        "UPDATE lost_found SET status='已关闭', updated_at=NOW() WHERE lf_id=%s",
        (lid,),
    )
    return {"code": 200, "msg": "已关闭"}


# ============================================================
#  GET  /api/lostfound/my   我发布的
# ============================================================
@lostfound_bp.route("/my", methods=["GET"])
@login_required
def my_list():
    rows = query(
        "SELECT * FROM lost_found WHERE publisher_id=%s ORDER BY created_at DESC",
        (request.g.current_user["user_id"],),
    )
    return {"code": 200, "data": rows}


# ============================================================
#  POST /api/lostfound/claims   提交认领申请
#  body: { lf_id, description }
# ============================================================
@lostfound_bp.route("/claims", methods=["POST"])
@login_required
def submit_claim():
    data = request.get_json()
    uid = request.g.current_user["user_id"]
    lf_id = data.get("lf_id")
    desc = (data.get("description") or "").strip()

    if not lf_id or not desc:
        return {"code": 400, "msg": "缺少失物ID或申请说明"}, 400

    lf = query_one("SELECT publisher_id FROM lost_found WHERE lf_id=%s", (lf_id,))
    if not lf:
        return {"code": 404, "msg": "失物信息不存在"}, 404
    if lf["publisher_id"] == uid:
        return {"code": 400, "msg": "不能认领自己发布的物品"}, 400

    execute(
        """INSERT INTO claim_requests (lf_id, claimant_id, description)
           VALUES (%s, %s, %s)""",
        (lf_id, uid, desc),
    )
    return {"code": 200, "msg": "认领申请已提交，等待管理员审核"}


# ============================================================
#  GET  /api/lostfound/claims/my   我的认领申请
# ============================================================
@lostfound_bp.route("/claims/my", methods=["GET"])
@login_required
def my_claims():
    rows = query(
        """SELECT cr.*, lf.title AS lf_title, lf.type AS lf_type
           FROM claim_requests cr
           JOIN lost_found lf ON cr.lf_id = lf.lf_id
           WHERE cr.claimant_id = %s
           ORDER BY cr.created_at DESC""",
        (request.g.current_user["user_id"],),
    )
    return {"code": 200, "data": rows}


# ============================================================
#  GET  /api/lostfound/claims/<id>   认领详情
# ============================================================
@lostfound_bp.route("/claims/<int:cid>", methods=["GET"])
@login_required
def claim_detail(cid):
    row = query_one(
        """SELECT cr.*, lf.title AS lf_title, lf.type AS lf_type,
                  u.user_name AS claimant_name
           FROM claim_requests cr
           JOIN lost_found lf ON cr.lf_id = lf.lf_id
           JOIN users u ON cr.claimant_id = u.user_id
           WHERE cr.claim_id = %s""",
        (cid,),
    )
    if not row:
        return {"code": 404, "msg": "申请不存在"}, 404
    return {"code": 200, "data": row}
