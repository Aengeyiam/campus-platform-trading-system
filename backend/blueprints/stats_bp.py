"""
统计蓝图：商品统计 / 订单统计 / 信用排行 / 失物统计
负责人：王博华
"""
from flask import Blueprint
from db import query
from auth import login_required

stats_bp = Blueprint("stats", __name__)


# ============================================================
#  GET /api/stats/products   商品分类统计（v_product_stats）
# ============================================================
@stats_bp.route("/products", methods=["GET"])
@login_required
def product_stats():
    rows = query(
        """SELECT c.category_name,
                  COUNT(p.product_id) AS total_count,
                  COUNT(CASE WHEN p.status='已上架' THEN 1 END) AS active_count,
                  COUNT(CASE WHEN p.status='已售出' THEN 1 END) AS sold_count,
                  ROUND(AVG(p.price)::numeric, 2) AS avg_price,
                  COALESCE(SUM(CASE WHEN p.status='已售出' THEN p.price ELSE 0 END), 0) AS total_sales
           FROM categories c
           LEFT JOIN products p ON c.category_id = p.category_id
           GROUP BY c.category_id, c.category_name
           ORDER BY total_count DESC""",
    )
    return {"code": 200, "data": rows}


# ============================================================
#  GET /api/stats/orders   订单交易统计（v_order_stats）
# ============================================================
@stats_bp.route("/orders", methods=["GET"])
@login_required
def order_stats():
    rows = query(
        """SELECT DATE(created_at) AS order_date,
                  COUNT(*) AS total_orders,
                  COUNT(CASE WHEN status='已完成' THEN 1 END) AS completed,
                  COUNT(CASE WHEN status='已取消' THEN 1 END) AS cancelled,
                  COALESCE(SUM(amount), 0) AS total_amount,
                  ROUND(
                    COUNT(CASE WHEN status='已完成' THEN 1 END)::decimal
                    / NULLIF(COUNT(*), 0) * 100, 1
                  ) AS complete_rate
           FROM orders
           GROUP BY DATE(created_at)
           ORDER BY order_date DESC
           LIMIT 30""",
    )
    return {"code": 200, "data": rows}


# ============================================================
#  GET /api/stats/credits   用户信用排行（v_credit_ranking）
# ============================================================
@stats_bp.route("/credits", methods=["GET"])
@login_required
def credit_ranking():
    rows = query(
        """SELECT u.user_id, u.student_id, u.user_name, u.credit_score,
                  COUNT(DISTINCT o.order_id) AS trade_count,
                  ROUND(
                    COALESCE(
                      COUNT(CASE WHEN rv.rating >= 4 THEN 1 END)::decimal
                      / NULLIF(COUNT(rv.review_id), 0) * 100, 0
                    ), 1
                  ) AS good_rate
           FROM users u
           LEFT JOIN orders o ON u.user_id = (
             SELECT p.seller_id FROM products p WHERE p.product_id = o.product_id
           ) AND o.status = '已完成'
           LEFT JOIN reviews rv ON u.user_id = rv.reviewee_id
           GROUP BY u.user_id
           ORDER BY u.credit_score DESC
           LIMIT 50""",
    )
    return {"code": 200, "data": rows}


# ============================================================
#  GET /api/stats/lostfound   失物处理统计（v_lost_found_stats）
# ============================================================
@stats_bp.route("/lostfound", methods=["GET"])
@login_required
def lostfound_stats():
    rows = query(
        """SELECT lf.type,
                  COUNT(*) AS publish_count,
                  COUNT(CASE WHEN lf.status='已认领' THEN 1 END) AS claimed_count,
                  COUNT(CASE WHEN lf.status='已关闭' THEN 1 END) AS closed_count,
                  COUNT(DISTINCT cr.claim_id) AS claim_apply_count,
                  ROUND(
                    COUNT(CASE WHEN lf.status='已认领' THEN 1 END)::decimal
                    / NULLIF(COUNT(*), 0) * 100, 1
                  ) AS claim_success_rate
           FROM lost_found lf
           LEFT JOIN claim_requests cr ON lf.lf_id = cr.lf_id
           GROUP BY lf.type""",
    )
    return {"code": 200, "data": rows}
