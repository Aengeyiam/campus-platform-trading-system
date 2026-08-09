"""
商品蓝图：发布 / 列表 / 搜索 / 详情 / 收藏 / 图片
负责人：熊倡
"""
import os
import time
import random
from flask import Blueprint, request
from db import query, query_one, execute
from auth import login_required, verify_token

product_bp = Blueprint("product", __name__)

# 上传目录：backend/../frontend/uploads
UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend", "uploads",
)
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_IMAGES = 5           # 单个商品最多图片数
ALLOWED_CONDITIONS = ("全新", "几乎全新", "轻微使用", "正常使用")


# ============================================================
#  POST /api/products/upload   上传商品图片（multipart/form-data, 字段名 file）
#  返回: { url: "/uploads/xxx.jpg" }
# ============================================================
@product_bp.route("/upload", methods=["POST"])
@login_required
def upload_image():
    file = request.files.get("file")
    if not file or not file.filename:
        return {"code": 400, "msg": "未选择文件"}, 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return {"code": 400, "msg": "仅支持 jpg/jpeg/png/gif/webp 格式"}, 400

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # 文件名：p + 时间戳 + 4位随机数 + 扩展名，避免重名
    fname = f"p{int(time.time())}{random.randint(1000, 9999)}{ext}"
    file.save(os.path.join(UPLOAD_DIR, fname))
    return {"code": 200, "data": {"url": f"/uploads/{fname}"}}


# ============================================================
#  GET  /api/products/categories  全部分类
# ============================================================
@product_bp.route("/categories", methods=["GET"])
def categories():
    rows = query("SELECT category_id, category_name, parent_id FROM categories ORDER BY sort_order")
    return {"code": 200, "data": rows}


# ============================================================
#  POST /api/products   发布商品
#  body: { title, description, price, original_price?, category_id, condition, images?: [url] }
# ============================================================
@product_bp.route("", methods=["POST"])
@login_required
def publish():
    data = request.get_json() or {}
    uid = request.g.current_user["user_id"]

    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    condition = (data.get("condition") or "").strip()
    category_id = data.get("category_id")

    # ---- 必填项校验 ----
    if not all([title, description, price := data.get("price"), category_id, condition]):
        return {"code": 400, "msg": "标题、描述、价格、分类、新旧程度不能为空"}, 400

    # ---- 价格校验 ----
    try:
        price = float(price)
    except (TypeError, ValueError):
        return {"code": 400, "msg": "价格必须是数字"}, 400
    if price <= 0:
        return {"code": 400, "msg": "价格必须大于 0"}, 400

    # 原价（可选）
    original_price = data.get("original_price")
    if original_price is not None and original_price != "":
        try:
            original_price = float(original_price)
        except (TypeError, ValueError):
            return {"code": 400, "msg": "原价必须是数字"}, 400
        if original_price < 0:
            return {"code": 400, "msg": "原价不能为负数"}, 400
    else:
        original_price = None

    # ---- 分类校验 ----
    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        return {"code": 400, "msg": "分类参数错误"}, 400
    if not query_one("SELECT category_id FROM categories WHERE category_id=%s", (category_id,)):
        return {"code": 400, "msg": "所选分类不存在"}, 400

    # ---- 新旧程度校验 ----
    if condition not in ALLOWED_CONDITIONS:
        return {"code": 400, "msg": "新旧程度取值不合法"}, 400

    # ---- 图片校验 ----
    images = data.get("images") or []
    if not isinstance(images, list) or len(images) > MAX_IMAGES:
        return {"code": 400, "msg": f"图片最多 {MAX_IMAGES} 张"}, 400
    for url in images:
        if not isinstance(url, str) or not url.startswith("/uploads/"):
            return {"code": 400, "msg": "图片地址不合法"}, 400

    # ---- 插入商品，返回 product_id ----
    product = query_one(
        """INSERT INTO products (seller_id, category_id, title, description,
           price, original_price, condition, status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,'待审核')
           RETURNING product_id""",
        (uid, category_id, title, description, price, original_price, condition),
    )

    # ---- 图片入库：第一张为封面 ----
    for i, url in enumerate(images):
        execute(
            """INSERT INTO product_images (product_id, image_url, is_cover, sort_order)
               VALUES (%s, %s, %s, %s)""",
            (product["product_id"], url, 1 if i == 0 else 0, i),
        )

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

    # 当前用户是否已收藏（带 token 时判断）
    favorited = False
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        token = request.cookies.get("token", "")
    if token:
        payload = verify_token(token)
        if payload:
            fav = query_one(
                "SELECT 1 FROM favorites WHERE user_id=%s AND product_id=%s",
                (payload["user_id"], pid),
            )
            favorited = bool(fav)

    return {"code": 200, "data": {**product, "images": images, "favorited": favorited}}


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
