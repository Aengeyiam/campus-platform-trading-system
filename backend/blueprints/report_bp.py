"""
举报蓝图：用户提交举报
负责人：王博华（新增）
举报提交后状态为「待处理」，由管理员在后台审核；核实后自动扣被举报人信用分。
"""
from flask import Blueprint, request, g

from db import query_one, execute
from auth import login_required

report_bp = Blueprint("report", __name__)

MAX_REASON_LEN = 500


# ============================================================
#  POST /api/reports   提交举报
#  body: { reported_type: "商品"|"用户", reported_id, reason }
# ============================================================
@report_bp.route("", methods=["POST"])
@login_required
def submit_report():
    data = request.get_json(silent=True) or {}
    uid = g.current_user["user_id"]

    reported_type = (data.get("reported_type") or "").strip()
    reported_id = data.get("reported_id")
    reason = (data.get("reason") or "").strip()

    # ---- 参数校验 ----
    if reported_type not in ("商品", "用户"):
        return {"code": 400, "msg": "举报类型不合法"}, 400
    if reported_id is None or reported_id == "":
        return {"code": 400, "msg": "缺少举报对象"}, 400
    if not reason:
        return {"code": 400, "msg": "请填写举报理由"}, 400
    if len(reason) > MAX_REASON_LEN:
        return {"code": 400, "msg": f"举报理由不能超过 {MAX_REASON_LEN} 字"}, 400

    try:
        reported_id = int(reported_id)
    except (TypeError, ValueError):
        return {"code": 400, "msg": "举报对象参数错误"}, 400

    # ---- 校验对象存在 + 定位被举报用户 ----
    target_user_id = None
    if reported_type == "商品":
        product = query_one(
            "SELECT seller_id FROM products WHERE product_id=%s",
            (reported_id,),
        )
        if not product:
            return {"code": 404, "msg": "商品不存在"}, 404
        target_user_id = product["seller_id"]
    else:
        user = query_one("SELECT user_id FROM users WHERE user_id=%s", (reported_id,))
        if not user:
            return {"code": 404, "msg": "用户不存在"}, 404
        target_user_id = reported_id

    # ---- 不能举报自己 ----
    if target_user_id == uid:
        return {"code": 400, "msg": "不能举报自己"}, 400

    # ---- 防重复举报（同一对象处于待处理中） ----
    exist = query_one(
        """SELECT report_id FROM reports
           WHERE reporter_id=%s AND reported_type=%s AND reported_id=%s
             AND status='待处理'""",
        (uid, reported_type, reported_id),
    )
    if exist:
        return {"code": 400, "msg": "您已举报过该对象，请等待管理员处理"}, 400

    execute(
        """INSERT INTO reports (reporter_id, reported_type, reported_id, reason)
           VALUES (%s, %s, %s, %s)""",
        (uid, reported_type, reported_id, reason),
    )
    return {"code": 200, "msg": "举报已提交，等待管理员审核"}
