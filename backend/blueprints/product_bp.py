"""
商品蓝图：发布 / 列表 / 搜索 / 详情 / 收藏 / 图片
负责人：熊倡
"""
import os
import secrets
import time
from decimal import Decimal, InvalidOperation

from flask import Blueprint, g, request
from config import Config
from db import query, query_one, execute, execute_returning
from auth import login_required, verify_token

product_bp = Blueprint("product", __name__)

# 上传目录：backend/../frontend/uploads
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
UPLOAD_DIR = os.path.join(
    PROJECT_ROOT,
    "frontend", "uploads",
)
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_MIME = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}
MAX_IMAGES = 5           # 单个商品最多图片数
ALLOWED_CONDITIONS = ("全新", "几乎全新", "轻微使用", "正常使用")
MAX_TITLE_LEN = 100
MAX_DESC_LEN = 5000
MAX_KEYWORD_LEN = 100
MAX_FILE_SIZE = Config.MAX_CONTENT_LENGTH


def _token_user():
    """解析请求中的用户身份，未登录或 token 无效时返回 None。"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        token = request.cookies.get("token", "")
    if not token:
        return None
    return verify_token(token)


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

    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size <= 0:
        return {"code": 400, "msg": "不能上传空文件"}, 400
    if size > MAX_FILE_SIZE:
        return {"code": 400, "msg": "单张图片不能超过 16MB"}, 400
    if file.mimetype and file.mimetype not in ALLOWED_MIME:
        return {"code": 400, "msg": "文件类型不合法"}, 400

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # 文件名：p + 时间戳 + 随机串 + 扩展名，避免重名
    fname = f"p{int(time.time())}{secrets.token_hex(6)}{ext}"
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
    uid = g.current_user["user_id"]

    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    condition = (data.get("condition") or "").strip()
    category_id = data.get("category_id")

    # ---- 必填项校验 ----
    if not all([title, description, price := data.get("price"), category_id, condition]):
        return {"code": 400, "msg": "标题、描述、价格、分类、新旧程度不能为空"}, 400
    if len(title) > MAX_TITLE_LEN:
        return {"code": 400, "msg": f"标题不能超过 {MAX_TITLE_LEN} 字"}, 400
    if len(description) > MAX_DESC_LEN:
        return {"code": 400, "msg": f"描述不能超过 {MAX_DESC_LEN} 字"}, 400

    # ---- 价格校验 ----
    try:
        price = Decimal(str(price).strip())
    except (InvalidOperation, ValueError):
        return {"code": 400, "msg": "价格必须是数字"}, 400
    if price <= 0:
        return {"code": 400, "msg": "价格必须大于 0"}, 400
    if price.as_tuple().exponent < -2:
        return {"code": 400, "msg": "价格最多保留 2 位小数"}, 400

    # 原价（可选）
    original_price = data.get("original_price")
    if original_price is not None and original_price != "":
        try:
            original_price = Decimal(str(original_price).strip())
        except (InvalidOperation, ValueError):
            return {"code": 400, "msg": "原价必须是数字"}, 400
        if original_price < 0:
            return {"code": 400, "msg": "原价不能为负数"}, 400
        if original_price.as_tuple().exponent < -2:
            return {"code": 400, "msg": "原价最多保留 2 位小数"}, 400
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
    seen_urls = set()
    for url in images:
        if (
            not isinstance(url, str)
            or len(url) > 255
            or not url.startswith("/uploads/")
            or ".." in url
        ):
            return {"code": 400, "msg": "图片地址不合法"}, 400
        if url in seen_urls:
            return {"code": 400, "msg": "图片不能重复"}, 400
        seen_urls.add(url)

    # ---- 插入商品，返回 product_id ----
    # 注意：必须用 execute_returning（内部提交事务）。
    # 若用 query_one，INSERT 会被 db.query 里的 rollback 回滚，商品不会落库。
    product = execute_returning(
        """INSERT INTO products (seller_id, category_id, title, description,
           price, original_price, condition, status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,'待审核')
           RETURNING product_id""",
        (
            uid,
            category_id,
            title,
            description,
            str(price),
            str(original_price) if original_price is not None else None,
            condition,
        ),
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
    try:
        page = int(request.args.get("page", 1))
        size = int(request.args.get("size", 12))
    except (TypeError, ValueError):
        return {"code": 400, "msg": "分页参数必须是数字"}, 400
    if page < 1 or size < 1 or size > 50:
        return {"code": 400, "msg": "分页参数超出范围"}, 400

    keyword = request.args.get("keyword", "").strip()
    if len(keyword) > MAX_KEYWORD_LEN:
        return {"code": 400, "msg": f"搜索关键词不能超过 {MAX_KEYWORD_LEN} 字"}, 400

    category_id = request.args.get("category_id", "")
    offset = (page - 1) * size

    where = "WHERE p.status = '已上架'"
    params = []

    if category_id:
        try:
            category_id = int(category_id)
        except (TypeError, ValueError):
            return {"code": 400, "msg": "分类参数错误"}, 400
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
        (g.current_user["user_id"],),
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

    current_user = _token_user()
    current_user_id = current_user["user_id"] if current_user else None
    is_admin = bool(current_user and current_user.get("role") == "管理员")
    is_owner = bool(current_user_id and current_user_id == product["seller_id"])

    # 非公开商品仅允许卖家、管理员通过详情页查看
    if product["status"] not in ("已上架", "已售出") and not is_owner and not is_admin:
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
    if current_user_id:
        fav = query_one(
            "SELECT 1 FROM favorites WHERE user_id=%s AND product_id=%s",
            (current_user_id, pid),
        )
        favorited = bool(fav)

    return {
        "code": 200,
        "data": {
            **product,
            "images": images,
            "favorited": favorited,
            "is_owner": is_owner,
        },
    }


# ============================================================
#  PUT  /api/products/<id>/status   下架自己的商品
#  body: { status: "已下架" }
# ============================================================
@product_bp.route("/<int:pid>/status", methods=["PUT"])
@login_required
def change_status(pid):
    data = request.get_json() or {}
    new_status = data.get("status")
    if new_status not in ("已下架",):
        return {"code": 400, "msg": "仅支持下架操作"}, 400

    product = query_one(
        "SELECT seller_id, status FROM products WHERE product_id=%s",
        (pid,),
    )
    if not product:
        return {"code": 404, "msg": "商品不存在"}, 404
    if product["seller_id"] != g.current_user["user_id"]:
        return {"code": 403, "msg": "只能下架自己发布的商品"}, 403
    if product["status"] != "已上架":
        return {"code": 400, "msg": f"当前状态'{product['status']}'不可下架"}, 400

    rowcount = execute(
        "UPDATE products SET status=%s, updated_at=NOW() WHERE product_id=%s AND seller_id=%s",
        (new_status, pid, g.current_user["user_id"]),
    )
    if rowcount == 0:
        return {"code": 500, "msg": "下架失败，请重试"}, 500
    return {"code": 200, "msg": "操作成功"}


# ============================================================
#  POST /api/products/<id>/favorite   收藏/取消收藏（toggle）
# ============================================================
@product_bp.route("/<int:pid>/favorite", methods=["POST"])
@login_required
def toggle_favorite(pid):
    uid = g.current_user["user_id"]
    product = query_one(
        "SELECT 1 FROM products WHERE product_id=%s",
        (pid,),
    )
    if not product:
        return {"code": 404, "msg": "商品不存在"}, 404

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
        """SELECT p.product_id, p.title, p.price, p.condition, p.status,
                  p.created_at,
                  u.user_name AS seller_name, u.credit_score AS seller_credit,
                  (SELECT image_url FROM product_images
                   WHERE product_id = p.product_id AND is_cover = 1 LIMIT 1) AS cover_image
           FROM favorites f
           JOIN products p ON f.product_id = p.product_id
           JOIN users u ON p.seller_id = u.user_id
           WHERE f.user_id = %s
           ORDER BY f.created_at DESC""",
        (g.current_user["user_id"],),
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
    if len(keyword) > MAX_KEYWORD_LEN:
        return {"code": 400, "msg": f"搜索关键词不能超过 {MAX_KEYWORD_LEN} 字"}, 400

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
