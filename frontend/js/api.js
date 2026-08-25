/**
 * campus-trade 前端 API 封装
 * ============================
 * 所有 fetch 请求的统一入口
 * 用法：
 *   API.get("/api/products").then(res => { ... })
 *   API.post("/api/auth/login", { student_id, password })
 */

const BASE = "";  // Flask 同源，无需前缀

const API = {
    /**
     * 获取 token
     */
    token() {
        return localStorage.getItem("campus_token") || "";
    },

    /**
     * 获取当前用户
     */
    user() {
        const u = localStorage.getItem("campus_user");
        return u ? JSON.parse(u) : null;
    },

    /**
     * 通用请求
     */
    async request(method, url, data = null) {
        const headers = { "Content-Type": "application/json" };
        const token = this.token();
        if (token) headers["Authorization"] = "Bearer " + token;

        const opts = { method, headers };
        if (data && method !== "GET") {
            opts.body = JSON.stringify(data);
        }

        let queryUrl = url;
        if (data && method === "GET") {
            const params = new URLSearchParams(data).toString();
            if (params) queryUrl += "?" + params;
        }

        const resp = await fetch(queryUrl, opts);
        const json = await resp.json();

        if (json.code === 401) {
            localStorage.removeItem("campus_token");
            localStorage.removeItem("campus_user");
            window.location.href = "/login.html";
        }
        return json;
    },

    get(url, params = null)    { return this.request("GET", url, params); },
    post(url, data = {})       { return this.request("POST", url, data); },
    put(url, data = {})        { return this.request("PUT", url, data); },
    delete(url, data = {})     { return this.request("DELETE", url, data); },
};
