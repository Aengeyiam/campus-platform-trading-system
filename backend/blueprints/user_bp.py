"""
用户主页蓝图：公开查看任意用户的主页（信用分 / 评价 / 被举报记录）
负责人：王博华（新增）
接口均无需登录，供买家查看卖家信誉。
"""
from flask import Blueprint

from db import query, query_one

user_bp = Blueprint("user", __name__)


def _mask_student_id(student_id: str) -> str:
    """学号脱敏：只保留前4位和后2位，中间用 * 遮挡。"""
    sid = (student_id or "").strip()
    if len(sid) <= 6:
        return (sid[:1] + "****") if sid else ""
    return f"{sid[:4]}****{sid[-2:]}"


# ============================================================
#  GET  /api/users/<uid>   用户公开主页
# ============================================================
@user_bp.route("/<int:uid>", methods=["GET"])
def public_profile(uid):
    user = query_one(
        """SELECT user_id, student_id, user_name, nickname, credit_score, created_at
           FROM users WHERE user_id = %s""",
        (uid,),
    )
    if not user:
        return {"code": 404, "msg": "用户不存在"}, 404

    # ---- 统计 ----
    on_sale = query_one(
        "SELECT COUNT(*) AS c FROM products WHERE seller_id=%s AND status='已上架'",
        (uid,),
    )["c"]
    sold = query_one(
        "SELECT COUNT(*) AS c FROM products WHERE seller_id=%s AND status='已售出'",
        (uid,),
    )["c"]
    lostfound = query_one(
        "SELECT COUNT(*) AS c FROM lost_found WHERE publisher_id=%s",
        (uid,),
    )["c"]

    # ---- 最近收到的评价（被评价人 = uid），关联订单和商品 ----
    reviews = query(
        """SELECT rv.rating, rv.comment, rv.created_at,
                  u.user_name AS reviewer_name,
                  o.product_id, p.title AS product_title,
                  (SELECT pi.image_url FROM product_images pi
                   WHERE pi.product_id = p.product_id AND pi.is_cover = 1 LIMIT 1) AS cover_image
           FROM reviews rv
           JOIN users u ON rv.reviewer_id = u.user_id
           JOIN orders o ON rv.order_id = o.order_id
           JOIN products p ON o.product_id = p.product_id
           WHERE rv.reviewee_id = %s
           ORDER BY rv.created_at DESC
           LIMIT 20""",
        (uid,),
    )

    review_count = len(reviews)
    good_count = sum(1 for r in reviews if r["rating"] >= 4)
    avg_rating = (
        round(sum(r["rating"] for r in reviews) / review_count, 1)
        if review_count else None
    )

    # ---- 被举报核实记录（只展示已处理的，保护未证实指控） ----
    # 包括：直接举报该用户，或举报该用户发布的商品
    # 商品举报时附带商品标题与封面，便于展示对应的商品
    reports = query(
        """SELECT r.report_id, r.reported_type, r.reported_id, r.reason,
                  r.handle_result, r.handle_time,
                  CASE WHEN r.reported_type = '商品' THEN p.title ELSE NULL END AS target_name,
                  (SELECT pi.image_url FROM product_images pi
                   WHERE pi.product_id = r.reported_id AND pi.is_cover = 1 LIMIT 1) AS cover_image
           FROM reports r
           LEFT JOIN products p ON r.reported_type = '商品' AND r.reported_id = p.product_id
           WHERE r.status = '已处理'
             AND (
                   (r.reported_type = '用户' AND r.reported_id = %s)
                   OR (r.reported_type = '商品' AND r.reported_id IN (
                       SELECT product_id FROM products WHERE seller_id = %s))
                 )
           ORDER BY r.handle_time DESC
           LIMIT 10""",
        (uid, uid),
    )

    # ---- 该用户的商品（在售 + 已售出，展示交易记录） ----
    products = query(
        """SELECT p.product_id, p.title, p.price, p.condition, p.status,
                  (SELECT image_url FROM product_images
                   WHERE product_id = p.product_id AND is_cover = 1 LIMIT 1) AS cover_image
           FROM products p
           WHERE p.seller_id = %s AND p.status IN ('已上架', '已售出')
           ORDER BY p.created_at DESC
           LIMIT 12""",
        (uid,),
    )

    return {
        "code": 200,
        "data": {
            "user_id": user["user_id"],
            "user_name": user["user_name"],
            "nickname": user["nickname"],
            "student_id": _mask_student_id(user["student_id"]),
            "credit_score": user["credit_score"],
            "created_at": user["created_at"],
            "stats": {
                "on_sale": on_sale,
                "sold": sold,
                "lostfound": lostfound,
                "review_count": review_count,
                "good_count": good_count,
                "avg_rating": avg_rating,
                "report_count": len(reports),
            },
            "reviews": reviews,
            "reports": reports,
            "products": products,
        },
    }
