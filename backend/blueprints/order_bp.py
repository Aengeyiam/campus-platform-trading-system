"""
订单蓝图：下单 / 支付 / 确认收货 / 取消 / 评价 / 信用记录
负责人：吴裕勇

信用分规则（V1.1，以小组进度报告为准）：
  交易完成 +2  |  5星 +3  |  4星 +2  |  3星 0  |  2星 -2  |  1星 -5  |  举报 -10
  需求规格书V1.0的旧值（+5/+5/+3/0/-3/-3/-10）已废弃，请勿使用。
"""
from flask import Blueprint, request
from db import query, query_one, execute
from auth import login_required

order_bp = Blueprint("order", __name__)


# ============================================================
#  POST /api/orders   创建订单（调用存储过程 sp_create_order）
#  body: { product_id }
# ============================================================
@order_bp.route("", methods=["POST"])
@login_required
def create_order():
    data = request.get_json()
    buyer_id = request.g.current_user["user_id"]
    product_id = data.get("product_id")

    if not product_id:
        return {"code": 400, "msg": "缺少商品ID"}, 400

    # ① 校验商品状态
    product = query_one(
        "SELECT product_id, seller_id, price, status FROM products WHERE product_id = %s FOR UPDATE",
        (product_id,),
    )
    if not product:
        return {"code": 404, "msg": "商品不存在"}, 404
    if product["status"] != "已上架":
        return {"code": 400, "msg": "该商品当前不可购买"}, 400
    if product["seller_id"] == buyer_id:
        return {"code": 400, "msg": "不能购买自己发布的商品"}, 400

    # ② 生成订单编号
    import time, random
    order_no = f"ORD{int(time.time())}{random.randint(1000, 9999)}"

    # ③ 锁定商品 + 插入订单（事务）
    try:
        execute(
            "UPDATE products SET status='已锁定' WHERE product_id=%s",
            (product_id,),
        )
        execute(
            """INSERT INTO orders (order_no, buyer_id, product_id, amount, status)
               VALUES (%s, %s, %s, %s, '待付款')""",
            (order_no, buyer_id, product_id, product["price"]),
        )
    except Exception:
        return {"code": 500, "msg": "下单失败，请重试"}, 500

    return {"code": 200, "msg": "下单成功", "data": {"order_no": order_no}}


# ============================================================
#  GET  /api/orders   我的订单列表
#  query: ?role=buyer|seller&status=待付款|已支付|已完成|已取消
# ============================================================
@order_bp.route("", methods=["GET"])
@login_required
def list_orders():
    uid = request.g.current_user["user_id"]
    role = request.args.get("role", "buyer")
    status = request.args.get("status", "").strip()

    if role == "seller":
        # 我卖出的：通过 product_id 关联
        where = "WHERE p.seller_id = %s"
    else:
        where = "WHERE o.buyer_id = %s"

    params = [uid]
    if status:
        where += " AND o.status = %s"
        params.append(status)

    rows = query(
        f"""SELECT o.*, p.title AS product_title, p.seller_id,
                  u_buyer.user_name AS buyer_name,
                  u_seller.user_name AS seller_name,
                  (SELECT image_url FROM product_images
                   WHERE product_id = p.product_id AND is_cover = 1 LIMIT 1) AS cover_image
           FROM orders o
           JOIN products p ON o.product_id = p.product_id
           JOIN users u_buyer ON o.buyer_id = u_buyer.user_id
           JOIN users u_seller ON p.seller_id = u_seller.user_id
           {where}
           ORDER BY o.created_at DESC""",
        tuple(params),
    )
    return {"code": 200, "data": rows}


# ============================================================
#  GET  /api/orders/<id>   订单详情
# ============================================================
@order_bp.route("/<int:oid>", methods=["GET"])
@login_required
def detail(oid):
    row = query_one(
        """SELECT o.*, p.title AS product_title, p.seller_id, p.description AS product_desc,
                  u_buyer.user_name AS buyer_name, u_buyer.student_id AS buyer_student_id,
                  u_seller.user_name AS seller_name, u_seller.student_id AS seller_student_id
           FROM orders o
           JOIN products p ON o.product_id = p.product_id
           JOIN users u_buyer ON o.buyer_id = u_buyer.user_id
           JOIN users u_seller ON p.seller_id = u_seller.user_id
           WHERE o.order_id = %s""",
        (oid,),
    )
    if not row:
        return {"code": 404, "msg": "订单不存在"}, 404
    return {"code": 200, "data": row}


# ============================================================
#  PUT  /api/orders/<id>/pay   模拟支付
# ============================================================
@order_bp.route("/<int:oid>/pay", methods=["PUT"])
@login_required
def pay(oid):
    uid = request.g.current_user["user_id"]

    order = query_one(
        "SELECT order_id, buyer_id, amount, status FROM orders WHERE order_id=%s FOR UPDATE",
        (oid,),
    )
    if not order:
        return {"code": 404, "msg": "订单不存在"}, 404
    if order["buyer_id"] != uid:
        return {"code": 403, "msg": "仅买家可支付"}, 403
    if order["status"] != "待付款":
        return {"code": 400, "msg": f"当前状态'{order['status']}'不可支付"}, 400

    execute(
        "UPDATE orders SET status='已支付', paid_at=NOW() WHERE order_id=%s",
        (oid,),
    )
    execute(
        """INSERT INTO payments (order_id, payer_id, pay_amount, pay_method, paid_at)
           VALUES (%s, %s, %s, '模拟支付', NOW())""",
        (oid, uid, order["amount"]),
    )
    return {"code": 200, "msg": "支付成功"}


# ============================================================
#  PUT  /api/orders/<id>/confirm   确认收货（触发器自动更新商品+信用分）
# ============================================================
@order_bp.route("/<int:oid>/confirm", methods=["PUT"])
@login_required
def confirm(oid):
    uid = request.g.current_user["user_id"]

    order = query_one(
        "SELECT order_id, buyer_id, status FROM orders WHERE order_id=%s FOR UPDATE",
        (oid,),
    )
    if not order:
        return {"code": 404, "msg": "订单不存在"}, 404
    if order["buyer_id"] != uid:
        return {"code": 403, "msg": "仅买家可确认收货"}, 403
    if order["status"] != "已支付":
        return {"code": 400, "msg": "当前状态不可确认收货"}, 400

    execute(
        "UPDATE orders SET status='已完成', completed_at=NOW() WHERE order_id=%s",
        (oid,),
    )
    # 后续由 trg_order_complete 触发器自动：
    #   → products.status='已售出'
    #   → users.credit_score += 2
    #   → INSERT credit_records
    return {"code": 200, "msg": "确认收货成功"}


# ============================================================
#  PUT  /api/orders/<id>/cancel   取消订单
# ============================================================
@order_bp.route("/<int:oid>/cancel", methods=["PUT"])
@login_required
def cancel(oid):
    uid = request.g.current_user["user_id"]
    reason = (request.get_json() or {}).get("reason", "")

    order = query_one(
        "SELECT order_id, buyer_id, product_id, status FROM orders WHERE order_id=%s FOR UPDATE",
        (oid,),
    )
    if not order:
        return {"code": 404, "msg": "订单不存在"}, 404
    if order["buyer_id"] != uid:
        return {"code": 403, "msg": "仅买家可取消"}, 403
    if order["status"] != "待付款":
        return {"code": 400, "msg": "仅待付款状态可取消"}, 400

    execute(
        "UPDATE orders SET status='已取消', cancelled_at=NOW(), cancel_reason=%s WHERE order_id=%s",
        (reason, oid),
    )
    execute(
        "UPDATE products SET status='已上架' WHERE product_id=%s",
        (order["product_id"],),
    )
    return {"code": 200, "msg": "订单已取消"}


# ============================================================
#  POST /api/orders/reviews   提交评价
#  body: { order_id, rating(1-5), comment? }
#  （触发器 trg_review_insert 自动处理信用分）
# ============================================================
@order_bp.route("/reviews", methods=["POST"])
@login_required
def submit_review():
    data = request.get_json()
    uid = request.g.current_user["user_id"]
    order_id = data.get("order_id")
    rating = data.get("rating")
    comment = data.get("comment", "")

    if not order_id or not rating:
        return {"code": 400, "msg": "缺少订单ID或评分"}, 400
    if rating < 1 or rating > 5:
        return {"code": 400, "msg": "评分范围1-5"}, 400

    # 校验订单
    order = query_one(
        "SELECT order_id, buyer_id, product_id, status FROM orders WHERE order_id=%s",
        (order_id,),
    )
    if not order:
        return {"code": 404, "msg": "订单不存在"}, 404
    if order["status"] != "已完成":
        return {"code": 400, "msg": "仅已完成订单可评价"}, 400

    # 确定 reviewer_id 和 reviewee_id
    product = query_one("SELECT seller_id FROM products WHERE product_id=%s", (order["product_id"],))
    if uid == order["buyer_id"]:
        reviewee_id = product["seller_id"]
    elif uid == product["seller_id"]:
        reviewee_id = order["buyer_id"]
    else:
        return {"code": 403, "msg": "非订单参与方不能评价"}, 403

    # 检查是否已评价
    exist = query_one(
        "SELECT review_id FROM reviews WHERE order_id=%s AND reviewer_id=%s",
        (order_id, uid),
    )
    if exist:
        return {"code": 400, "msg": "您已评价过该订单"}, 400

    execute(
        """INSERT INTO reviews (order_id, reviewer_id, reviewee_id, rating, comment)
           VALUES (%s, %s, %s, %s, %s)""",
        (order_id, uid, reviewee_id, rating, comment),
    )
    # 触发器 trg_review_insert 自动处理信用分变更
    return {"code": 200, "msg": "评价成功"}


# ============================================================
#  GET  /api/orders/reviews/user/<id>   用户收到的评价
# ============================================================
@order_bp.route("/reviews/user/<int:uid>", methods=["GET"])
def user_reviews(uid):
    rows = query(
        """SELECT rv.*, u.user_name AS reviewer_name
           FROM reviews rv
           JOIN users u ON rv.reviewer_id = u.user_id
           WHERE rv.reviewee_id = %s
           ORDER BY rv.created_at DESC""",
        (uid,),
    )
    return {"code": 200, "data": rows}
