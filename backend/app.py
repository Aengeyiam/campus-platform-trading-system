"""
=====================================
 校园二手交易与失物招领系统 - 主入口
=====================================
启动:  python app.py
访问:  http://localhost:5000
=====================================
"""
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from config import Config

# ---- 创建应用 ----
app = Flask(__name__, static_folder="../frontend", static_url_path="")
app.config.from_object(Config)
CORS(app, supports_credentials=True)

# ---- 注册蓝图 ----
from blueprints.auth_bp     import auth_bp
from blueprints.product_bp  import product_bp
from blueprints.order_bp    import order_bp
from blueprints.lostfound_bp import lostfound_bp
from blueprints.admin_bp    import admin_bp
from blueprints.stats_bp    import stats_bp

app.register_blueprint(auth_bp,      url_prefix="/api/auth")
app.register_blueprint(product_bp,   url_prefix="/api/products")
app.register_blueprint(order_bp,     url_prefix="/api/orders")
app.register_blueprint(lostfound_bp, url_prefix="/api/lostfound")
app.register_blueprint(admin_bp,     url_prefix="/api/admin")
app.register_blueprint(stats_bp,     url_prefix="/api/stats")


# ---- 前端静态页面 ----
@app.route("/")
@app.route("/<path:filename>")
def serve_frontend(filename="index.html"):
    """将 frontend/ 目录下的 .html 文件当静态页面提供"""
    path = "../frontend"
    # admin/ 子目录支持
    if filename.endswith(".html") or filename.endswith(".css") or filename.endswith(".js"):
        return send_from_directory(path, filename)
    # 默认返回 index.html
    return send_from_directory(path, "login.html")


# ---- 错误处理 ----
@app.errorhandler(404)
def not_found(e):
    return {"code": 404, "msg": "接口不存在"}, 404


@app.errorhandler(500)
def server_error(e):
    return {"code": 500, "msg": "服务器内部错误"}, 500


# ---- 启动 ----
if __name__ == "__main__":
    print("=" * 50)
    print("  校园二手交易与失物招领系统")
    print("  后端地址: http://localhost:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)
