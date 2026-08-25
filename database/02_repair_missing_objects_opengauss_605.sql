-- ============================================================
-- campus_trade 增量修复脚本（openGauss 6.0.x）
-- 用途：数据库 15 张基础表已经存在，只补齐后续对象。
-- 不会 DROP TABLE / CREATE TABLE，不会重建数据库。
--
-- 主要修复：
-- 1) PostgreSQL 风格 EXECUTE FUNCTION -> openGauss EXECUTE PROCEDURE
-- 2) PostgreSQL 风格过程定义 -> openGauss 原生 CREATE PROCEDURE ... AS ... /
-- 3) ON CONFLICT 初始化数据 -> WHERE NOT EXISTS 幂等写法
-- 4) 聚合 FILTER (WHERE ...) -> CASE WHEN 写法
-- 5) DO $$ 动态批量建 updated_at 触发器 -> 显式创建 3 个触发器
-- 6) 同步项目 V1.1 信用规则：
--    交易完成：买家 +2，卖家 +2
--    5星 +3 / 4星 +2 / 3星 0 / 2星 -2 / 1星 -5
-- ============================================================

SET search_path TO public;

-- ============================================================
-- 1. 补初始数据（可重复执行）
-- ============================================================

INSERT INTO public.roles (role_name, description)
SELECT '学生', '普通学生用户，可买卖商品、发布失物招领'
WHERE NOT EXISTS (
    SELECT 1 FROM public.roles WHERE role_name = '学生'
);

INSERT INTO public.roles (role_name, description)
SELECT '管理员', '系统管理员，负责审核商品、认领、举报及用户管理'
WHERE NOT EXISTS (
    SELECT 1 FROM public.roles WHERE role_name = '管理员'
);

INSERT INTO public.categories (category_name, parent_id, sort_order)
SELECT '书籍', NULL, 1
WHERE NOT EXISTS (
    SELECT 1 FROM public.categories WHERE category_name = '书籍'
);

INSERT INTO public.categories (category_name, parent_id, sort_order)
SELECT '电子产品', NULL, 2
WHERE NOT EXISTS (
    SELECT 1 FROM public.categories WHERE category_name = '电子产品'
);

INSERT INTO public.categories (category_name, parent_id, sort_order)
SELECT '生活用品', NULL, 3
WHERE NOT EXISTS (
    SELECT 1 FROM public.categories WHERE category_name = '生活用品'
);

INSERT INTO public.categories (category_name, parent_id, sort_order)
SELECT '服装鞋帽', NULL, 4
WHERE NOT EXISTS (
    SELECT 1 FROM public.categories WHERE category_name = '服装鞋帽'
);

INSERT INTO public.categories (category_name, parent_id, sort_order)
SELECT '运动户外', NULL, 5
WHERE NOT EXISTS (
    SELECT 1 FROM public.categories WHERE category_name = '运动户外'
);

INSERT INTO public.categories (category_name, parent_id, sort_order)
SELECT '其他', NULL, 6
WHERE NOT EXISTS (
    SELECT 1 FROM public.categories WHERE category_name = '其他'
);


-- ============================================================
-- 2. 触发器函数
-- ============================================================

-- 2.1 订单完成：更新商品状态，买卖双方各 +2 信用分
CREATE OR REPLACE FUNCTION public.fn_order_complete()
RETURNS TRIGGER AS
$$
DECLARE
    v_seller_id  INTEGER;
    v_credit_new INTEGER;
BEGIN
    IF NEW.status = '已完成'
       AND (OLD.status IS NULL OR OLD.status <> '已完成') THEN

        UPDATE public.products
           SET status = '已售出',
               updated_at = CURRENT_TIMESTAMP
         WHERE product_id = NEW.product_id;

        UPDATE public.users
           SET credit_score = credit_score + 2,
               updated_at = CURRENT_TIMESTAMP
         WHERE user_id = NEW.buyer_id;

        SELECT credit_score
          INTO v_credit_new
          FROM public.users
         WHERE user_id = NEW.buyer_id;

        INSERT INTO public.credit_records
            (user_id, change_type, change_value, score_after, related_id, remark)
        VALUES
            (NEW.buyer_id, '交易完成', 2, v_credit_new, NEW.order_id,
             '买家完成订单，信用分+2');

        SELECT seller_id
          INTO v_seller_id
          FROM public.products
         WHERE product_id = NEW.product_id;

        UPDATE public.users
           SET credit_score = credit_score + 2,
               updated_at = CURRENT_TIMESTAMP
         WHERE user_id = v_seller_id;

        SELECT credit_score
          INTO v_credit_new
          FROM public.users
         WHERE user_id = v_seller_id;

        INSERT INTO public.credit_records
            (user_id, change_type, change_value, score_after, related_id, remark)
        VALUES
            (v_seller_id, '交易完成', 2, v_credit_new, NEW.order_id,
             '卖家完成交易，信用分+2');

        NEW.completed_at = CURRENT_TIMESTAMP;
    END IF;

    RETURN NEW;
END
$$ LANGUAGE PLPGSQL;


-- 2.2 评价后自动调整被评价人信用分（V1.1）
CREATE OR REPLACE FUNCTION public.fn_review_insert()
RETURNS TRIGGER AS
$$
DECLARE
    v_change_value INTEGER;
    v_old_score    INTEGER;
    v_score_after  INTEGER;
    v_change_type  VARCHAR(30);
BEGIN
    v_change_value := CASE NEW.rating
        WHEN 5 THEN 3
        WHEN 4 THEN 2
        WHEN 3 THEN 0
        WHEN 2 THEN -2
        WHEN 1 THEN -5
        ELSE 0
    END;

    IF v_change_value > 0 THEN
        v_change_type := '收到好评';
    ELSIF v_change_value < 0 THEN
        v_change_type := '收到差评';
    ELSE
        v_change_type := '收到评价';
    END IF;

    SELECT credit_score
      INTO v_old_score
      FROM public.users
     WHERE user_id = NEW.reviewee_id;

    UPDATE public.users
       SET credit_score = GREATEST(credit_score + v_change_value, 0),
           updated_at = CURRENT_TIMESTAMP
     WHERE user_id = NEW.reviewee_id;

    SELECT credit_score
      INTO v_score_after
      FROM public.users
     WHERE user_id = NEW.reviewee_id;

    INSERT INTO public.credit_records
        (user_id, change_type, change_value, score_after, related_id, remark)
    VALUES
        (NEW.reviewee_id,
         v_change_type,
         v_score_after - v_old_score,
         v_score_after,
         NEW.review_id,
         '收到评价，评分' || NEW.rating || '分');

    RETURN NEW;
END
$$ LANGUAGE PLPGSQL;


-- 2.3 插入支付记录后，自动把订单改为“已支付”
CREATE OR REPLACE FUNCTION public.fn_payment_insert()
RETURNS TRIGGER AS
$$
BEGIN
    UPDATE public.orders
       SET status = '已支付',
           paid_at = CURRENT_TIMESTAMP
     WHERE order_id = NEW.order_id;

    RETURN NEW;
END
$$ LANGUAGE PLPGSQL;


-- 2.4 通用 updated_at 自动更新时间
CREATE OR REPLACE FUNCTION public.fn_auto_update_timestamp()
RETURNS TRIGGER AS
$$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END
$$ LANGUAGE PLPGSQL;


-- ============================================================
-- 3. 绑定触发器
-- openGauss 使用 EXECUTE PROCEDURE
-- ============================================================

DROP TRIGGER IF EXISTS trg_order_complete ON public.orders;
CREATE TRIGGER trg_order_complete
    BEFORE UPDATE ON public.orders
    FOR EACH ROW
    EXECUTE PROCEDURE public.fn_order_complete();

DROP TRIGGER IF EXISTS trg_review_insert ON public.reviews;
CREATE TRIGGER trg_review_insert
    AFTER INSERT ON public.reviews
    FOR EACH ROW
    EXECUTE PROCEDURE public.fn_review_insert();

DROP TRIGGER IF EXISTS trg_payment_insert ON public.payments;
CREATE TRIGGER trg_payment_insert
    AFTER INSERT ON public.payments
    FOR EACH ROW
    EXECUTE PROCEDURE public.fn_payment_insert();

-- 原 SQL 用 DO $$ 动态扫描 updated_at 字段。
-- 你的当前表结构中有 updated_at 的基础表是 users / products / lost_found，
-- 这里直接显式绑定，避免动态 SQL 兼容性问题。
DROP TRIGGER IF EXISTS trg_auto_updated_at ON public.users;
CREATE TRIGGER trg_auto_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW
    EXECUTE PROCEDURE public.fn_auto_update_timestamp();

DROP TRIGGER IF EXISTS trg_auto_updated_at ON public.products;
CREATE TRIGGER trg_auto_updated_at
    BEFORE UPDATE ON public.products
    FOR EACH ROW
    EXECUTE PROCEDURE public.fn_auto_update_timestamp();

DROP TRIGGER IF EXISTS trg_auto_updated_at ON public.lost_found;
CREATE TRIGGER trg_auto_updated_at
    BEFORE UPDATE ON public.lost_found
    FOR EACH ROW
    EXECUTE PROCEDURE public.fn_auto_update_timestamp();


-- ============================================================
-- 4. 存储过程
-- openGauss 原生过程语法：CREATE OR REPLACE PROCEDURE ... AS ... /
-- ============================================================

-- 4.1 创建订单并锁定商品
CREATE OR REPLACE PROCEDURE public.sp_create_order(
    p_buyer_id   IN  INTEGER,
    p_product_id IN  INTEGER,
    p_order_id   OUT INTEGER,
    p_order_no   OUT VARCHAR(32),
    p_error_msg  OUT VARCHAR(255)
)
AS
DECLARE
    v_price      DECIMAL(10,2);
    v_status     VARCHAR(20);
    v_seller_id  INTEGER;
    v_count      INTEGER;
BEGIN
    p_order_id := NULL;
    p_order_no := NULL;
    p_error_msg := NULL;

    SELECT COUNT(*)
      INTO v_count
      FROM public.products
     WHERE product_id = p_product_id;

    IF v_count = 0 THEN
        p_error_msg := '商品不存在';
        RETURN;
    END IF;

    SELECT price, status, seller_id
      INTO v_price, v_status, v_seller_id
      FROM public.products
     WHERE product_id = p_product_id
     FOR UPDATE;

    IF v_status <> '已上架' THEN
        p_error_msg := '商品当前状态不可购买：' || COALESCE(v_status, '未知');
        RETURN;
    END IF;

    IF v_seller_id = p_buyer_id THEN
        p_error_msg := '不能购买自己发布的商品';
        RETURN;
    END IF;

    p_order_no :=
        'ORD' ||
        TO_CHAR(CURRENT_TIMESTAMP, 'YYYYMMDDHH24MISS') ||
        LPAD(CAST(CAST(FLOOR(RANDOM() * 10000) AS INTEGER) AS VARCHAR), 4, '0');

    INSERT INTO public.orders
        (order_no, buyer_id, product_id, amount, status)
    VALUES
        (p_order_no, p_buyer_id, p_product_id, v_price, '待付款')
    RETURNING order_id INTO p_order_id;

    UPDATE public.products
       SET status = '已锁定',
           updated_at = CURRENT_TIMESTAMP
     WHERE product_id = p_product_id;
END;
/

-- 4.2 确认收货
CREATE OR REPLACE PROCEDURE public.sp_confirm_order(
    p_order_id  IN  INTEGER,
    p_buyer_id  IN  INTEGER,
    p_error_msg OUT VARCHAR(255)
)
AS
DECLARE
    v_status    VARCHAR(20);
    v_buyer_id  INTEGER;
    v_count     INTEGER;
BEGIN
    p_error_msg := NULL;

    SELECT COUNT(*)
      INTO v_count
      FROM public.orders
     WHERE order_id = p_order_id;

    IF v_count = 0 THEN
        p_error_msg := '订单不存在';
        RETURN;
    END IF;

    SELECT status, buyer_id
      INTO v_status, v_buyer_id
      FROM public.orders
     WHERE order_id = p_order_id;

    IF v_buyer_id <> p_buyer_id THEN
        p_error_msg := '无权操作此订单';
        RETURN;
    END IF;

    IF v_status <> '已支付' THEN
        p_error_msg :=
            '订单状态不正确，当前状态：' ||
            COALESCE(v_status, '未知') ||
            '，需要状态：已支付';
        RETURN;
    END IF;

    UPDATE public.orders
       SET status = '已完成',
           completed_at = CURRENT_TIMESTAMP
     WHERE order_id = p_order_id;
END;
/

-- 4.3 审核认领申请
CREATE OR REPLACE PROCEDURE public.sp_audit_claim(
    p_claim_id   IN  INTEGER,
    p_auditor_id IN  INTEGER,
    p_result     IN  VARCHAR(20),
    p_remark     IN  VARCHAR(255),
    p_error_msg  OUT VARCHAR(255)
)
AS
DECLARE
    v_status VARCHAR(20);
    v_lf_id  INTEGER;
    v_count  INTEGER;
BEGIN
    p_error_msg := NULL;

    IF p_result NOT IN ('已通过', '已拒绝') THEN
        p_error_msg := '审核结果只能是"已通过"或"已拒绝"';
        RETURN;
    END IF;

    SELECT COUNT(*)
      INTO v_count
      FROM public.claim_requests
     WHERE claim_id = p_claim_id;

    IF v_count = 0 THEN
        p_error_msg := '认领申请不存在';
        RETURN;
    END IF;

    SELECT status, lf_id
      INTO v_status, v_lf_id
      FROM public.claim_requests
     WHERE claim_id = p_claim_id;

    IF v_status <> '待审核' THEN
        p_error_msg := '该申请已被处理，当前状态：' || COALESCE(v_status, '未知');
        RETURN;
    END IF;

    UPDATE public.claim_requests
       SET status = p_result,
           auditor_id = p_auditor_id,
           audit_time = CURRENT_TIMESTAMP,
           audit_remark = p_remark
     WHERE claim_id = p_claim_id;

    IF p_result = '已通过' THEN
        UPDATE public.lost_found
           SET status = '已认领',
               updated_at = CURRENT_TIMESTAMP
         WHERE lf_id = v_lf_id;
    END IF;

    INSERT INTO public.audit_logs
        (auditor_id, audit_type, target_id, result, remark)
    VALUES
        (p_auditor_id, '认领审核', p_claim_id, p_result, p_remark);
END;
/

-- 4.4 管理员审核商品
CREATE OR REPLACE PROCEDURE public.sp_audit_product(
    p_product_id IN  INTEGER,
    p_auditor_id IN  INTEGER,
    p_result     IN  VARCHAR(20),
    p_remark     IN  VARCHAR(255),
    p_error_msg  OUT VARCHAR(255)
)
AS
DECLARE
    v_status VARCHAR(20);
    v_count  INTEGER;
BEGIN
    p_error_msg := NULL;

    IF p_result NOT IN ('通过', '驳回') THEN
        p_error_msg := '审核结果只能是"通过"或"驳回"';
        RETURN;
    END IF;

    SELECT COUNT(*)
      INTO v_count
      FROM public.products
     WHERE product_id = p_product_id;

    IF v_count = 0 THEN
        p_error_msg := '商品不存在';
        RETURN;
    END IF;

    SELECT status
      INTO v_status
      FROM public.products
     WHERE product_id = p_product_id;

    IF v_status <> '待审核' THEN
        p_error_msg := '该商品已被审核，当前状态：' || COALESCE(v_status, '未知');
        RETURN;
    END IF;

    IF p_result = '通过' THEN
        UPDATE public.products
           SET status = '已上架',
               updated_at = CURRENT_TIMESTAMP
         WHERE product_id = p_product_id;
    ELSE
        UPDATE public.products
           SET status = '审核驳回',
               updated_at = CURRENT_TIMESTAMP
         WHERE product_id = p_product_id;
    END IF;

    INSERT INTO public.audit_logs
        (auditor_id, audit_type, target_id, result, remark)
    VALUES
        (p_auditor_id, '商品审核', p_product_id, p_result, p_remark);
END;
/

-- 4.5 管理员处理举报
CREATE OR REPLACE PROCEDURE public.sp_handle_report(
    p_report_id  IN  INTEGER,
    p_handler_id IN  INTEGER,
    p_result     IN  VARCHAR(20),
    p_remark     IN  VARCHAR(255),
    p_error_msg  OUT VARCHAR(255)
)
AS
DECLARE
    v_status        VARCHAR(20);
    v_reported_type VARCHAR(30);
    v_reported_id   INTEGER;
    v_score_after   INTEGER;
    v_old_score     INTEGER;
    v_count         INTEGER;
BEGIN
    p_error_msg := NULL;

    IF p_result NOT IN ('通过', '驳回') THEN
        p_error_msg := '处理结果只能是"通过"或"驳回"';
        RETURN;
    END IF;

    SELECT COUNT(*)
      INTO v_count
      FROM public.reports
     WHERE report_id = p_report_id;

    IF v_count = 0 THEN
        p_error_msg := '举报不存在';
        RETURN;
    END IF;

    SELECT status, reported_type, reported_id
      INTO v_status, v_reported_type, v_reported_id
      FROM public.reports
     WHERE report_id = p_report_id;

    IF v_status <> '待处理' THEN
        p_error_msg := '该举报已被处理，当前状态：' || COALESCE(v_status, '未知');
        RETURN;
    END IF;

    IF p_result = '通过' THEN
        UPDATE public.reports
           SET status = '已处理',
               handler_id = p_handler_id,
               handle_result = p_remark,
               handle_time = CURRENT_TIMESTAMP
         WHERE report_id = p_report_id;

        IF v_reported_type = '用户' THEN
            SELECT COUNT(*)
              INTO v_count
              FROM public.users
             WHERE user_id = v_reported_id;

            IF v_count > 0 THEN
                SELECT credit_score
                  INTO v_old_score
                  FROM public.users
                 WHERE user_id = v_reported_id;

                UPDATE public.users
                   SET credit_score = GREATEST(credit_score - 10, 0),
                       updated_at = CURRENT_TIMESTAMP
                 WHERE user_id = v_reported_id;

                SELECT credit_score
                  INTO v_score_after
                  FROM public.users
                 WHERE user_id = v_reported_id;

                INSERT INTO public.credit_records
                    (user_id, change_type, change_value, score_after, related_id, remark)
                VALUES
                    (v_reported_id,
                     '举报扣分',
                     v_score_after - v_old_score,
                     v_score_after,
                     p_report_id,
                     '举报处理通过，信用分扣减：' || COALESCE(p_remark, ''));
            END IF;
        END IF;

        INSERT INTO public.audit_logs
            (auditor_id, audit_type, target_id, result, remark)
        VALUES
            (p_handler_id, '举报处理', p_report_id, p_result, p_remark);
    ELSE
        UPDATE public.reports
           SET status = '已驳回',
               handler_id = p_handler_id,
               handle_result = p_remark,
               handle_time = CURRENT_TIMESTAMP
         WHERE report_id = p_report_id;

        INSERT INTO public.audit_logs
            (auditor_id, audit_type, target_id, result, remark)
        VALUES
            (p_handler_id, '举报处理', p_report_id, p_result, p_remark);
    END IF;
END;
/


-- ============================================================
-- 5. 统计视图
-- 用 CASE WHEN 替代 FILTER (WHERE ...)
-- ============================================================

CREATE OR REPLACE VIEW public.v_product_stats AS
SELECT
    c.category_id,
    c.category_name,
    COUNT(p.product_id) AS total_products,
    COUNT(CASE WHEN p.status = '已售出' THEN 1 END) AS sold_count,
    COUNT(CASE WHEN p.status = '已上架' THEN 1 END) AS active_count,
    COALESCE(AVG(CASE WHEN p.status = '已上架' THEN p.price END), 0) AS avg_price,
    COALESCE(SUM(p.view_count), 0) AS total_views
FROM public.categories c
LEFT JOIN public.products p
       ON c.category_id = p.category_id
GROUP BY c.category_id, c.category_name
ORDER BY total_products DESC;

CREATE OR REPLACE VIEW public.v_order_stats AS
SELECT
    DATE(created_at) AS order_date,
    COUNT(*) AS total_orders,
    COUNT(CASE WHEN status = '已完成' THEN 1 END) AS completed_orders,
    COUNT(CASE WHEN status = '已取消' THEN 1 END) AS cancelled_orders,
    COALESCE(SUM(CASE WHEN status = '已完成' THEN amount ELSE 0 END), 0) AS total_amount,
    COALESCE(AVG(CASE WHEN status = '已完成' THEN amount END), 0) AS avg_amount
FROM public.orders
GROUP BY DATE(created_at)
ORDER BY order_date DESC;

CREATE OR REPLACE VIEW public.v_credit_ranking AS
SELECT
    RANK() OVER (ORDER BY u.credit_score DESC) AS rank,
    u.user_id,
    u.student_id,
    u.user_name,
    u.nickname,
    u.credit_score,
    (
        SELECT COUNT(*)
          FROM public.credit_records cr
         WHERE cr.user_id = u.user_id
    ) AS record_count
FROM public.users u
WHERE u.status = 0
ORDER BY u.credit_score DESC;

CREATE OR REPLACE VIEW public.v_lost_found_stats AS
SELECT
    type,
    status,
    COUNT(*) AS total_count,
    COUNT(CASE WHEN DATE(created_at) = CURRENT_DATE THEN 1 END) AS today_count
FROM public.lost_found
GROUP BY type, status
ORDER BY type, status;


-- ============================================================
-- 6. 完成提示（这些 SELECT 只做检查，不修改数据）
-- ============================================================

SELECT current_database() AS database_name, current_user AS db_user;

SELECT COUNT(*) AS role_count
FROM public.roles
WHERE role_name IN ('学生', '管理员');

SELECT COUNT(*) AS category_count
FROM public.categories
WHERE category_name IN ('书籍', '电子产品', '生活用品', '服装鞋帽', '运动户外', '其他');

SELECT COUNT(*) AS repaired_trigger_count
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE NOT t.tgisinternal
  AND n.nspname = 'public'
  AND t.tgname IN ('trg_order_complete', 'trg_review_insert', 'trg_payment_insert', 'trg_auto_updated_at');

SELECT COUNT(*) AS repaired_view_count
FROM pg_views
WHERE schemaname = 'public'
  AND viewname IN ('v_product_stats', 'v_order_stats', 'v_credit_ranking', 'v_lost_found_stats');

-- 正常情况下：
-- role_count = 2
-- category_count = 6
-- repaired_trigger_count = 6
-- repaired_view_count = 4
-- 过程/函数请执行配套的 03_verify_campus_trade.sql 继续核验。
