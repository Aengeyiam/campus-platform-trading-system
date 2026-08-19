"""
管理员蓝图：商品审核 / 认领审核 / 用户管理 / 举报处理 / 审核日志
负责人：刘子懿
所有接口均需 admin_required
"""
from flask import Blueprint, g, request
from db import query, query_one, execute
from auth import admin_required

admin_bp = Blueprint("admin", __name__)


# ============================================================
#  GET  /api/admin/products/pending   待审核商品
# ============================================================
@admin_bp.route("/products/pending", methods=["GET"])
@admin_required
def products_pending():
    rows = query(
        """SELECT p.*, c.category_name, u.user_name AS seller_name,
                  (SELECT image_url FROM product_images WHERE product_id=p.product_id AND is_cover=1 LIMIT 1) AS cover_image
           FROM products p
           JOIN categories c ON p.category_id = c.category_id
           JOIN users u ON p.seller_id = u.user_id
           WHERE p.status = '待审核'
           ORDER BY p.created_at DESC""",
    )
    return {"code": 200, "data": rows}


# ============================================================
#  PUT  /api/admin/products/<id>/audit   审核商品
#  body: { result: "通过"|"驳回", remark? }
# ============================================================
@admin_bp.route("/products/<int:pid>/audit", methods=["PUT"])
@admin_required
def audit_product(pid):
    data = request.get_json()
    result = data.get("result")
    remark = data.get("remark", "")
    auditor_id = g.current_user["user_id"]

    if result not in ("通过", "驳回"):
        return {"code": 400, "msg": "审核结果只能是'通过'或'驳回'"}, 400

    new_status = "已上架" if result == "通过" else "审核驳回"
    execute(
        "UPDATE products SET status=%s, updated_at=NOW() WHERE product_id=%s AND status='待审核'",
        (new_status, pid),
    )
    execute(
        """INSERT INTO audit_logs (auditor_id, audit_type, target_id, result, remark)
           VALUES (%s, '商品审核', %s, %s, %s)""",
        (auditor_id, pid, result, remark),
    )
    return {"code": 200, "msg": "审核完成"}


# ============================================================
#  GET  /api/admin/claims/pending   待审核认领
# ============================================================
@admin_bp.route("/claims/pending", methods=["GET"])
@admin_required
def claims_pending():
    rows = query(
        """SELECT cr.*, lf.title AS lf_title, lf.type AS lf_type,
                  u.user_name AS claimant_name
           FROM claim_requests cr
           JOIN lost_found lf ON cr.lf_id = lf.lf_id
           JOIN users u ON cr.claimant_id = u.user_id
           WHERE cr.status = '待审核'
           ORDER BY cr.created_at DESC""",
    )
    return {"code": 200, "data": rows}


# ============================================================
#  PUT  /api/admin/claims/<id>/audit   审核认领（调用 sp_audit_claim 逻辑）
#  body: { result: "通过"|"拒绝", remark? }
# ============================================================
@admin_bp.route("/claims/<int:cid>/audit", methods=["PUT"])
@admin_required
def audit_claim(cid):
    data = request.get_json()
    result = data.get("result")
    remark = data.get("remark", "")
    auditor_id = g.current_user["user_id"]

    if result not in ("通过", "拒绝"):
        return {"code": 400, "msg": "审核结果只能是'通过'或'拒绝'"}, 400

    claim = query_one("SELECT lf_id, status FROM claim_requests WHERE claim_id=%s FOR UPDATE", (cid,))
    if not claim:
        return {"code": 404, "msg": "认领申请不存在"}, 404
    if claim["status"] != "待审核":
        return {"code": 400, "msg": "该申请已处理"}, 400

    new_status = "已通过" if result == "通过" else "已拒绝"
    execute(
        """UPDATE claim_requests SET status=%s, auditor_id=%s, audit_time=NOW(), audit_remark=%s
           WHERE claim_id=%s""",
        (new_status, auditor_id, remark, cid),
    )

    if result == "通过":
        execute(
            "UPDATE lost_found SET status='已认领', updated_at=NOW() WHERE lf_id=%s",
            (claim["lf_id"],),
        )

    execute(
        """INSERT INTO audit_logs (auditor_id, audit_type, target_id, result, remark)
           VALUES (%s, '认领审核', %s, %s, %s)""",
        (auditor_id, cid, result, remark),
    )
    return {"code": 200, "msg": "审核完成"}


# ============================================================
#  GET  /api/admin/users   用户列表
# ============================================================
@admin_bp.route("/users", methods=["GET"])
@admin_required
def user_list():
    rows = query(
        """SELECT u.user_id, u.student_id, u.user_name, u.phone, u.credit_score,
                  u.status, u.created_at,
                  COALESCE(r.role_name, '学生') AS role_name
           FROM users u
           LEFT JOIN user_roles ur ON u.user_id = ur.user_id
           LEFT JOIN roles r ON ur.role_id = r.role_id
           ORDER BY u.created_at DESC""",
    )
    return {"code": 200, "data": rows}


# ============================================================
#  PUT  /api/admin/users/<id>/status   启用/禁用
#  body: { status: 0|1 }
# ============================================================
@admin_bp.route("/users/<int:uid>/status", methods=["PUT"])
@admin_required
def toggle_user(uid):
    data = request.get_json()
    new_status = data.get("status")
    if new_status not in (0, 1):
        return {"code": 400, "msg": "status 只能是 0(启用) 或 1(禁用)"}, 400

    action = "启用" if new_status == 0 else "禁用"
    execute("UPDATE users SET status=%s WHERE user_id=%s", (new_status, uid))
    execute(
        """INSERT INTO audit_logs (auditor_id, audit_type, target_id, result, remark)
           VALUES (%s, '用户管理', %s, %s, '')""",
        (g.current_user["user_id"], uid, action),
    )
    return {"code": 200, "msg": f"已{action}"}


# ============================================================
#  GET  /api/admin/reports   举报列表
# ============================================================
@admin_bp.route("/reports", methods=["GET"])
@admin_required
def report_list():
    status = request.args.get("status", "").strip()
    where = ""
    params = []
    if status:
        where = "WHERE r.status = %s"
        params.append(status)
    rows = query(
        f"""SELECT r.*, u1.user_name AS reporter_name, u2.user_name AS handler_name
           FROM reports r
           JOIN users u1 ON r.reporter_id = u1.user_id
           LEFT JOIN users u2 ON r.handler_id = u2.user_id
           {where}
           ORDER BY r.created_at DESC""",
        tuple(params),
    )
    return {"code": 200, "data": rows}


# ============================================================
#  PUT  /api/admin/reports/<id>/handle   处理举报
#  body: { result: "已处理"|"已驳回", handle_result? }
# ============================================================
@admin_bp.route("/reports/<int:rid>/handle", methods=["PUT"])
@admin_required
def handle_report(rid):
    data = request.get_json()
    result = data.get("result")
    handle_result = data.get("handle_result", "")
    auditor_id = g.current_user["user_id"]

    if result not in ("已处理", "已驳回"):
        return {"code": 400, "msg": "处理结果只能是'已处理'或'已驳回'"}, 400

    rpt = query_one(
        "SELECT report_id, reported_type, reported_id, status FROM reports WHERE report_id=%s",
        (rid,),
    )
    if not rpt:
        return {"code": 404, "msg": "举报记录不存在"}, 404
    if rpt["status"] != "待处理":
        return {"code": 400, "msg": "该举报已处理"}, 400

    execute(
        """UPDATE reports SET status=%s, handler_id=%s, handle_result=%s, handle_time=NOW()
           WHERE report_id=%s""",
        (result, auditor_id, handle_result, rid),
    )

    # 举报核实 → 被举报人信用分 -10
    if result == "已处理":
        # 根据举报类型确定被扣分用户
        if rpt["reported_type"] == "商品":
            # reported_id 是 product_id，找出卖家
            product = query_one(
                "SELECT seller_id FROM products WHERE product_id=%s",
                (rpt["reported_id"],),
            )
            target_user_id = product["seller_id"] if product else None
        else:
            # reported_id 直接是 user_id
            target_user_id = rpt["reported_id"]

        if target_user_id:
            execute(
                "UPDATE users SET credit_score = GREATEST(credit_score - 10, 0) WHERE user_id=%s",
                (target_user_id,),
            )
            execute(
                """INSERT INTO credit_records (user_id, change_type, change_value, score_after, related_id, remark)
                   SELECT %s, '举报扣分', -10, credit_score, %s, '被举报核实' FROM users WHERE user_id=%s""",
                (target_user_id, rid, target_user_id),
            )

    execute(
        """INSERT INTO audit_logs (auditor_id, audit_type, target_id, result, remark)
           VALUES (%s, '举报处理', %s, %s, %s)""",
        (auditor_id, rid, result, handle_result),
    )
    return {"code": 200, "msg": "处理完成"}


# ============================================================
#  GET  /api/admin/logs   审核日志
# ============================================================
@admin_bp.route("/logs", methods=["GET"])
@admin_required
def audit_logs():
    audit_type = request.args.get("type", "").strip()
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 20))
    offset = (page - 1) * size

    where = ""
    params = []
    if audit_type:
        where = "WHERE al.audit_type = %s"
        params.append(audit_type)

    total = query_one(f"SELECT COUNT(*) AS cnt FROM audit_logs al {where}", tuple(params))["cnt"]
    rows = query(
        f"""SELECT al.*, u.user_name AS auditor_name
           FROM audit_logs al
           JOIN users u ON al.auditor_id = u.user_id
           {where}
           ORDER BY al.created_at DESC
           LIMIT %s OFFSET %s""",
        tuple(params) + (size, offset),
    )
    return {"code": 200, "data": {"total": total, "items": rows}}
