"""
商品蓝图：发布 / 列表 / 搜索 / 详情 / 收藏 / 图片
负责人：熊倡
"""
from flask import Blueprint, request
from db import query, query_one, execute
from auth import login_required

product_bp = Blueprint("product", __name__)


# ============================================================
#  GET  /api/products/categories  全部分类
# ============================================================
@product_bp.route("/categories", methods=["GET"])
def categories():
    rows = query("SELECT category_id, category_name, parent_id FROM categories ORDER BY sort_order")
    return {"code": 200, "data": rows}


# ============================================================
#  POST /api/products   发布商品
#  body: { title, description, price, original_price?, category_id, condition }
# ============================================================
@product_bp.route("", methods=["POST"])
@login_required
def publish():
    data = request.get_json()
    uid = request.g.current_user["user_id"]

    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    price = data.get("price")
    category_id = data.get("category_id")
    condition = data.get("condition")

    if not all([title, description, price, category_id, condition]):
        return {"code": 400, "msg": "标题、描述、价格、分类、新旧程度不能为空"}, 400

    execute(
        """INSERT INTO products (seller_id, category_id, title, description,
           price, original_price, condition, status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,'待审核')""",
        (uid, category_id, title, description, price,
         data.get("original_price"), condition),
    )

    # 插入图片（前端已上传，这里接收 URL 列表）
    # product = query_one("SELECT product_id FROM products WHERE title=%s AND seller_id=%s ORDER BY created_at DESC LIMIT 1", (title, uid))
    # for url in data.get("images", []):
    #     execute("INSERT INTO product_images (product_id, image_url) VALUES (%s,%s)", (product["product_id"], url))

    return {"code": 200, "msg": "发布成功，等待管理员审核"}


# ============================================================
#  GET  /api/products   商品列表
#  query: ?category_id=&keyword=&page=1&size=12
# ============================================================
@product_bp.route("", methods=["GET"])
def list_products():
    category_id = request.args.get("category_id", "")
    keyword = request.args.get("keyword", "").strip()
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 12))
    offset = (page - 1) * size

    where = "WHERE p.status = '已上架'"
    params = []

    if category_id:
        where += " AND p.category_id = %s"
        params.append(category_id)
    if keyword:
        where += " AND (p.title LIKE %s OR p.description LIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    count_sql = f"SELECT COUNT(*) AS cnt FROM products p {where}"
    total = query_one(count_sql, tuple(params))["cnt"]

    data_sql = f"""
        SELECT p.product_id, p.title, p.price, p.condition, p.status,
               p.view_count, p.created_at,
               c.category_name,
               u.user_name AS seller_name, u.credit_score AS seller_credit,
               (SELECT image_url FROM product_images
                WHERE product_id = p.product_id AND is_cover = 1 LIMIT 1) AS cover_image
        FROM products p
        JOIN categories c ON p.category_id = c.category_id
        JOIN users u ON p.seller_id = u.user_id
        {where}
        ORDER BY p.created_at DESC
        LIMIT %s OFFSET %s
    """
    rows = query(data_sql, tuple(params) + (size, offset))

    return {"code": 200, "data": {"total": total, "page": page, "size": size, "items": rows}}


# ============================================================
#  GET  /api/products/my   我的发布
# ============================================================
@product_bp.route("/my", methods=["GET"])
@login_required
def my_products():
    rows = query(
        """SELECT p.*, c.category_name,
                  (SELECT image_url FROM product_images
                   WHERE product_id = p.product_id AND is_cover = 1 LIMIT 1) AS cover_image
           FROM products p
           JOIN categories c ON p.category_id = c.category_id
           WHERE p.seller_id = %s
           ORDER BY p.created_at DESC""",
        (request.g.current_user["user_id"],),
    )
    return {"code": 200, "data": rows}


# ============================================================
#  GET  /api/products/<id>   商品详情
# ============================================================
@product_bp.route("/<int:pid>", methods=["GET"])
def detail(pid):
    product = query_one(
        """SELECT p.*, c.category_name,
                  u.user_id AS seller_id, u.user_name AS seller_name,
                  u.credit_score AS seller_credit, u.student_id AS seller_student_id
           FROM products p
           JOIN categories c ON p.category_id = c.category_id
           JOIN users u ON p.seller_id = u.user_id
           WHERE p.product_id = %s""",
        (pid,),
    )
    if not product:
        return {"code": 404, "msg": "商品不存在"}, 404

    # 浏览次数+1
    execute("UPDATE products SET view_count = view_count + 1 WHERE product_id = %s", (pid,))

    # 图片列表
    images = query(
        "SELECT image_url FROM product_images WHERE product_id = %s ORDER BY sort_order",
        (pid,),
    )

    return {"code": 200, "data": {**product, "images": images}}


# ============================================================
#  PUT  /api/products/<id>/status   下架自己的商品
#  body: { status: "已下架" }
# ============================================================
@product_bp.route("/<int:pid>/status", methods=["PUT"])
@login_required
def change_status(pid):
    data = request.get_json()
    new_status = data.get("status")
    if new_status not in ("已下架",):
        return {"code": 400, "msg": "仅支持下架操作"}, 400

    execute(
        "UPDATE products SET status=%s, updated_at=NOW() WHERE product_id=%s AND seller_id=%s",
        (new_status, pid, request.g.current_user["user_id"]),
    )
    return {"code": 200, "msg": "操作成功"}


# ============================================================
#  POST /api/products/<id>/favorite   收藏/取消收藏（toggle）
# ============================================================
@product_bp.route("/<int:pid>/favorite", methods=["POST"])
@login_required
def toggle_favorite(pid):
    uid = request.g.current_user["user_id"]
    exist = query_one(
        "SELECT favorite_id FROM favorites WHERE user_id=%s AND product_id=%s",
        (uid, pid),
    )
    if exist:
        execute("DELETE FROM favorites WHERE user_id=%s AND product_id=%s", (uid, pid))
        return {"code": 200, "data": {"favorited": False}, "msg": "已取消收藏"}
    else:
        execute(
            "INSERT INTO favorites (user_id, product_id) VALUES (%s, %s)",
            (uid, pid),
        )
        return {"code": 200, "data": {"favorited": True}, "msg": "已收藏"}


# ============================================================
#  GET  /api/products/favorites   我的收藏
# ============================================================
@product_bp.route("/favorites", methods=["GET"])
@login_required
def my_favorites():
    rows = query(
        """SELECT p.product_id, p.title, p.price, p.status,
                  u.user_name AS seller_name,
                  (SELECT image_url FROM product_images
                   WHERE product_id = p.product_id AND is_cover = 1 LIMIT 1) AS cover_image
           FROM favorites f
           JOIN products p ON f.product_id = p.product_id
           JOIN users u ON p.seller_id = u.user_id
           WHERE f.user_id = %s
           ORDER BY f.created_at DESC""",
        (request.g.current_user["user_id"],),
    )
    return {"code": 200, "data": rows}


# ============================================================
#  GET  /api/products/search   关键字搜索（已合并到列表接口，此处为独立搜索）
# ============================================================
@product_bp.route("/search", methods=["GET"])
def search():
    keyword = (request.args.get("keyword") or "").strip()
    if not keyword:
        return {"code": 400, "msg": "请输入搜索关键字"}, 400

    rows = query(
        """SELECT p.product_id, p.title, p.price, p.condition, p.status, p.created_at,
                  c.category_name, u.user_name AS seller_name, u.credit_score AS seller_credit,
                  (SELECT image_url FROM product_images WHERE product_id=p.product_id AND is_cover=1 LIMIT 1) AS cover_image
           FROM products p
           JOIN categories c ON p.category_id = c.category_id
           JOIN users u ON p.seller_id = u.user_id
           WHERE p.status = '已上架'
             AND (p.title LIKE %s OR p.description LIKE %s)
           ORDER BY p.created_at DESC LIMIT 50""",
        (f"%{keyword}%", f"%{keyword}%"),
    )
    return {"code": 200, "data": rows}
