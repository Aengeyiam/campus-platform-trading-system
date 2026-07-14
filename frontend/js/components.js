/**
 * campus-trade 公共组件
 * ============================
 * 用法：<script src="/js/components.js"></script>
 *        <campus-navbar></campus-navbar>
 */

/* ========== 导航栏组件 ========== */
class CampusNavbar {
    static init() {
        const nav = document.getElementById("campus-navbar");
        if (!nav) return;
        const user = API.user();
        const role = user ? user.role : null;

        nav.innerHTML = `
        <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
          <div class="container">
            <a class="navbar-brand fw-bold" href="/index.html">校园二手</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
              <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
              <ul class="navbar-nav me-auto">
                <li class="nav-item"><a class="nav-link" href="/index.html">首页</a></li>
                ${user ? `<li class="nav-item"><a class="nav-link" href="/product_publish.html">发布商品</a></li>` : ''}
                ${user ? `<li class="nav-item"><a class="nav-link" href="/my_orders.html">我的订单</a></li>` : ''}
                <li class="nav-item"><a class="nav-link" href="/lost_found.html">失物招领</a></li>
              </ul>
              <ul class="navbar-nav">
                ${user ? `
                  <li class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle" href="#" data-bs-toggle="dropdown">${user.user_name}</a>
                    <ul class="dropdown-menu">
                      <li><a class="dropdown-item" href="/personal.html">个人中心</a></li>
                      ${role === '管理员' ? `<li><a class="dropdown-item" href="/admin/statistics.html">管理后台</a></li>` : ''}
                      <li><hr class="dropdown-divider"></li>
                      <li><a class="dropdown-item" href="#" onclick="CampusNavbar.logout()">退出登录</a></li>
                    </ul>
                  </li>
                ` : `
                  <li class="nav-item"><a class="nav-link" href="/login.html">登录</a></li>
                  <li class="nav-item"><a class="nav-link" href="/register.html">注册</a></li>
                `}
              </ul>
            </div>
          </div>
        </nav>`;
    }

    static logout() {
        localStorage.removeItem("campus_token");
        localStorage.removeItem("campus_user");
        window.location.href = "/login.html";
    }
}

/* ========== 商品卡片 ========== */
function renderProductCard(p) {
    const cover = p.cover_image || "https://placehold.co/400x300/e2e8f0/64748b?text=No+Image";
    return `
    <div class="col">
      <div class="card h-100 shadow-sm product-card" onclick="location.href='/product_detail.html?id=${p.product_id}'" style="cursor:pointer">
        <img src="${cover}" class="card-img-top" style="height:200px;object-fit:cover" alt="${p.title}">
        <div class="card-body">
          <h6 class="card-title text-truncate">${p.title}</h6>
          <p class="card-text">
            <span class="text-danger fw-bold fs-5">¥${Number(p.price).toFixed(2)}</span>
            <small class="text-muted ms-2">${p.condition || ''}</small>
          </p>
        </div>
        <div class="card-footer bg-white d-flex justify-content-between">
          <small class="text-muted">${p.seller_name || ''}</small>
          <small>信用: <span class="text-success">${p.seller_credit || 100}</span></small>
        </div>
      </div>
    </div>`;
}

/* ========== Toast 提示 ========== */
function showToast(msg, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const bg = type === "success" ? "bg-success" : type === "error" ? "bg-danger" : "bg-warning";
    const toast = document.createElement("div");
    toast.className = `toast align-items-center text-white ${bg} border-0`;
    toast.setAttribute("role", "alert");
    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${msg}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>`;
    container.appendChild(toast);
    new bootstrap.Toast(toast).show();
    setTimeout(() => toast.remove(), 3500);
}

/* ========== 页面初始化 ========== */
document.addEventListener("DOMContentLoaded", () => {
    CampusNavbar.init();
});
