-- ============================================================
-- 校园二手交易平台 · 数据库完整建库脚本 (openGauss)
-- ============================================================
-- 版本: v1.3
-- 日期: 2026-07-28
-- 数据库: campus_trade
-- 说明: 包含 15 张表、外键、索引、注释、初始数据、4 个触发器、5 个存储过程和 4 个视图
-- 用法: 在 openGauss 中，建好 campus_trade 数据库后执行本文件即可完成全库搭建
-- ============================================================
-- 配套脚本（请按以下顺序执行）：
--   ① 01_init_db.sql（仓库里维护）→ 创建表空间 + 数据库 + 应用用户
--        \i 01_init_db.sql
--   ② 本脚本                       → 在 campus_trade 库内执行所有 DDL/DML
--        \c campus_trade
--        \i 02_create_tables.sql
--   ③ 在 campus_trade 库内补充授权：
--        GRANT ALL ON SCHEMA public TO campus_admin;
-- ============================================================

-- ============================================================
-- 第一部分：前置检查（仅注释，不执行）
-- ============================================================
-- 以下内容由仓库的 01_init_db.sql 负责，本脚本不重复创建：
--   CREATE TABLESPACE campus_ts LOCATION '/opt/opengauss/data/campus';
--   CREATE DATABASE campus_trade TABLESPACE campus_ts ENCODING 'UTF-8';
--   CREATE USER campus_admin WITH PASSWORD 'Campus@2026';
--   GRANT ALL PRIVILEGES ON DATABASE campus_trade TO campus_admin;
--
-- 默认以 omm 超级用户连接数据库后：
--   \c campus_trade
--   GRANT ALL ON SCHEMA public TO campus_admin;
-- ============================================================

-- ============================================================
-- 第二部分：创建表结构
-- ============================================================

-- ----------------------------
-- 1. users（用户表）— 王博华
-- ----------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id      SERIAL          PRIMARY KEY,
    student_id   VARCHAR(20)     NOT NULL UNIQUE,
    user_name    VARCHAR(50)     NOT NULL,
    password     VARCHAR(256)    NOT NULL,
    nickname     VARCHAR(50),
    phone        VARCHAR(20),
    qq           VARCHAR(20),
    credit_score INTEGER         DEFAULT 100  CHECK (credit_score >= 0),
    status       SMALLINT        DEFAULT 0,
    created_at   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  users IS '用户表：存储所有注册用户的基本信息';
COMMENT ON COLUMN users.user_id      IS '用户ID，自增主键';
COMMENT ON COLUMN users.student_id   IS '学号，唯一，不可为空';
COMMENT ON COLUMN users.user_name    IS '真实姓名';
COMMENT ON COLUMN users.password     IS 'SHA-256 加密后的密码';
COMMENT ON COLUMN users.nickname     IS '用户昵称';
COMMENT ON COLUMN users.phone        IS '手机号码';
COMMENT ON COLUMN users.qq           IS 'QQ 号码';
COMMENT ON COLUMN users.credit_score IS '信用分，初始值100，由触发器自动更新';
COMMENT ON COLUMN users.status       IS '0=启用，1=禁用';
COMMENT ON COLUMN users.created_at   IS '注册时间';
COMMENT ON COLUMN users.updated_at   IS '最后更新时间';

-- ----------------------------
-- 2. roles（角色表）— 王博华
-- ----------------------------
CREATE TABLE IF NOT EXISTS roles (
    role_id     SERIAL          PRIMARY KEY,
    role_name   VARCHAR(30)     NOT NULL UNIQUE,
    description VARCHAR(100),
    created_at  TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  roles IS '角色表：系统角色定义（学生、管理员）';
COMMENT ON COLUMN roles.role_id     IS '角色ID，自增主键';
COMMENT ON COLUMN roles.role_name   IS '角色名称，唯一';
COMMENT ON COLUMN roles.description IS '角色描述';
COMMENT ON COLUMN roles.created_at  IS '创建时间';

-- ----------------------------
-- 3. user_roles（用户角色关联表）— 王博华
-- ----------------------------
CREATE TABLE IF NOT EXISTS user_roles (
    id          SERIAL      PRIMARY KEY,
    user_id     INTEGER     NOT NULL,
    role_id     INTEGER     NOT NULL,
    assigned_at TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_role UNIQUE (user_id, role_id)
);

COMMENT ON TABLE  user_roles IS '用户角色关联表：多对多关联用户与角色';
COMMENT ON COLUMN user_roles.id          IS '自增主键';
COMMENT ON COLUMN user_roles.user_id     IS '用户ID';
COMMENT ON COLUMN user_roles.role_id     IS '角色ID';
COMMENT ON COLUMN user_roles.assigned_at IS '角色分配时间';

-- ----------------------------
-- 4. categories（商品分类表）— 熊倡
-- ----------------------------
CREATE TABLE IF NOT EXISTS categories (
    category_id   SERIAL          PRIMARY KEY,
    category_name VARCHAR(50)     NOT NULL UNIQUE,
    parent_id     INTEGER,
    sort_order    INTEGER         DEFAULT 0,
    created_at    TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  categories IS '商品分类表：支持二级分类（自引用 parent_id）';
COMMENT ON COLUMN categories.category_id   IS '分类ID，自增主键';
COMMENT ON COLUMN categories.category_name IS '分类名称，唯一';
COMMENT ON COLUMN categories.parent_id     IS '上级分类ID，支持二级分类';
COMMENT ON COLUMN categories.sort_order    IS '排序序号';
COMMENT ON COLUMN categories.created_at    IS '创建时间';

-- ----------------------------
-- 5. products（二手商品表）— 熊倡
-- ----------------------------
CREATE TABLE IF NOT EXISTS products (
    product_id     SERIAL          PRIMARY KEY,
    seller_id      INTEGER         NOT NULL,
    category_id    INTEGER         NOT NULL,
    title          VARCHAR(100)    NOT NULL,
    description    TEXT            NOT NULL,
    price          DECIMAL(10,2)   NOT NULL,
    original_price DECIMAL(10,2),
    condition      VARCHAR(20)     NOT NULL,
    status         VARCHAR(20)     DEFAULT '待审核',
    view_count     INTEGER         DEFAULT 0,
    created_at     TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  products IS '商品表：存储用户发布的二手商品信息';
COMMENT ON COLUMN products.product_id     IS '商品ID，自增主键';
COMMENT ON COLUMN products.seller_id      IS '卖家用户ID';
COMMENT ON COLUMN products.category_id    IS '商品分类ID';
COMMENT ON COLUMN products.title          IS '商品标题';
COMMENT ON COLUMN products.description    IS '商品详细描述';
COMMENT ON COLUMN products.price          IS '售价（元）';
COMMENT ON COLUMN products.original_price IS '原价（元）';
COMMENT ON COLUMN products.condition      IS '新旧程度描述';
COMMENT ON COLUMN products.status         IS '状态：待审核/已上架/已锁定/已售出/已下架/审核驳回';
COMMENT ON COLUMN products.view_count     IS '浏览次数';
COMMENT ON COLUMN products.created_at     IS '发布时间';
COMMENT ON COLUMN products.updated_at     IS '最后更新时间';

-- ----------------------------
-- 6. product_images（商品图片表）— 熊倡
-- ----------------------------
CREATE TABLE IF NOT EXISTS product_images (
    image_id    SERIAL          PRIMARY KEY,
    product_id  INTEGER         NOT NULL,
    image_url   VARCHAR(255)    NOT NULL,
    is_cover    SMALLINT        DEFAULT 0,
    sort_order  INTEGER         DEFAULT 0,
    created_at  TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  product_images IS '商品图片表：存储商品的多张图片';
COMMENT ON COLUMN product_images.image_id   IS '图片ID，自增主键';
COMMENT ON COLUMN product_images.product_id IS '所属商品ID，级联删除';
COMMENT ON COLUMN product_images.image_url  IS '图片存储路径';
COMMENT ON COLUMN product_images.is_cover   IS '是否为封面图（0=否，1=是）';
COMMENT ON COLUMN product_images.sort_order IS '展示排序';
COMMENT ON COLUMN product_images.created_at IS '上传时间';

-- ----------------------------
-- 7. favorites（收藏表）— 熊倡
-- ----------------------------
CREATE TABLE IF NOT EXISTS favorites (
    favorite_id SERIAL      PRIMARY KEY,
    user_id     INTEGER     NOT NULL,
    product_id  INTEGER     NOT NULL,
    created_at  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_product UNIQUE (user_id, product_id)
);

COMMENT ON TABLE  favorites IS '收藏表：记录用户收藏的商品';
COMMENT ON COLUMN favorites.favorite_id IS '收藏ID，自增主键';
COMMENT ON COLUMN favorites.user_id     IS '用户ID';
COMMENT ON COLUMN favorites.product_id  IS '商品ID';
COMMENT ON COLUMN favorites.created_at  IS '收藏时间';

-- ----------------------------
-- 8. orders（交易订单表）— 吴裕勇
-- ----------------------------
CREATE TABLE IF NOT EXISTS orders (
    order_id      SERIAL          PRIMARY KEY,
    order_no      VARCHAR(32)     NOT NULL UNIQUE,
    buyer_id      INTEGER         NOT NULL,
    product_id    INTEGER         NOT NULL,
    amount        DECIMAL(10,2)   NOT NULL,
    status        VARCHAR(20)     DEFAULT '待付款',
    created_at    TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    paid_at       TIMESTAMP,
    completed_at  TIMESTAMP,
    cancelled_at  TIMESTAMP,
    cancel_reason VARCHAR(255)
);

COMMENT ON TABLE  orders IS '订单表：存储每笔交易订单信息';
COMMENT ON COLUMN orders.order_id      IS '订单ID，自增主键';
COMMENT ON COLUMN orders.order_no      IS '订单编号，系统自动生成，唯一';
COMMENT ON COLUMN orders.buyer_id      IS '买家用户ID';
COMMENT ON COLUMN orders.product_id    IS '商品ID';
COMMENT ON COLUMN orders.amount        IS '交易金额（元）';
COMMENT ON COLUMN orders.status        IS '订单状态：待付款/已支付/已完成/已取消';
COMMENT ON COLUMN orders.created_at    IS '下单时间';
COMMENT ON COLUMN orders.paid_at       IS '付款时间';
COMMENT ON COLUMN orders.completed_at  IS '完成时间';
COMMENT ON COLUMN orders.cancelled_at  IS '取消时间';
COMMENT ON COLUMN orders.cancel_reason IS '取消原因';

-- ----------------------------
-- 9. payments（支付记录表）— 吴裕勇
-- ----------------------------
CREATE TABLE IF NOT EXISTS payments (
    payment_id  SERIAL          PRIMARY KEY,
    order_id    INTEGER         NOT NULL UNIQUE,
    payer_id    INTEGER         NOT NULL,
    pay_amount  DECIMAL(10,2)   NOT NULL,
    pay_method  VARCHAR(20)     DEFAULT '模拟支付',
    paid_at     TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  payments IS '支付记录表：记录每笔支付明细';
COMMENT ON COLUMN payments.payment_id IS '支付记录ID，自增主键';
COMMENT ON COLUMN payments.order_id   IS '关联订单ID，一对一';
COMMENT ON COLUMN payments.payer_id   IS '付款用户ID';
COMMENT ON COLUMN payments.pay_amount IS '支付金额（元）';
COMMENT ON COLUMN payments.pay_method IS '支付方式';
COMMENT ON COLUMN payments.paid_at    IS '付款时间';

-- ----------------------------
-- 10. reviews（评价表）— 吴裕勇
-- ----------------------------
CREATE TABLE IF NOT EXISTS reviews (
    review_id    SERIAL          PRIMARY KEY,
    order_id     INTEGER         NOT NULL,
    reviewer_id  INTEGER         NOT NULL,
    reviewee_id  INTEGER         NOT NULL,
    rating       SMALLINT        NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment      VARCHAR(500),
    created_at   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  reviews IS '评价表：订单完成后的双方互评';
COMMENT ON COLUMN reviews.review_id   IS '评价ID，自增主键';
COMMENT ON COLUMN reviews.order_id    IS '关联订单ID';
COMMENT ON COLUMN reviews.reviewer_id IS '评价人用户ID';
COMMENT ON COLUMN reviews.reviewee_id IS '被评价人用户ID';
COMMENT ON COLUMN reviews.rating      IS '评分，1-5分（CHECK约束）';
COMMENT ON COLUMN reviews.comment     IS '评语内容';
COMMENT ON COLUMN reviews.created_at  IS '评价时间';

-- ----------------------------
-- 11. credit_records（信用记录表）— 吴裕勇
-- ----------------------------
CREATE TABLE IF NOT EXISTS credit_records (
    record_id    SERIAL          PRIMARY KEY,
    user_id      INTEGER         NOT NULL,
    change_type  VARCHAR(30)     NOT NULL,
    change_value INTEGER         NOT NULL,
    score_after  INTEGER         NOT NULL,
    related_id   INTEGER,
    remark       VARCHAR(255),
    created_at   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  credit_records IS '信用记录表：记录所有信用分变动明细（由触发器/系统自动写入）';
COMMENT ON COLUMN credit_records.record_id    IS '记录ID，自增主键';
COMMENT ON COLUMN credit_records.user_id      IS '用户ID';
COMMENT ON COLUMN credit_records.change_type  IS '变动类型：交易完成/收到评价/举报扣分';
COMMENT ON COLUMN credit_records.change_value IS '变动分值（正为加分，负为扣分）';
COMMENT ON COLUMN credit_records.score_after  IS '变动后的信用分';
COMMENT ON COLUMN credit_records.related_id   IS '关联ID（订单ID/评价ID/举报ID）';
COMMENT ON COLUMN credit_records.remark       IS '备注说明';
COMMENT ON COLUMN credit_records.created_at   IS '记录时间';

-- ----------------------------
-- 12. lost_found（失物招领表）— 王旭坤
-- ----------------------------
CREATE TABLE IF NOT EXISTS lost_found (
    lf_id        SERIAL          PRIMARY KEY,
    publisher_id INTEGER         NOT NULL,
    type         VARCHAR(10)     NOT NULL,
    title        VARCHAR(100)    NOT NULL,
    description  TEXT            NOT NULL,
    location     VARCHAR(100)    NOT NULL,
    lf_date      DATE            NOT NULL,
    contact      VARCHAR(100)    NOT NULL,
    status       VARCHAR(20)     DEFAULT '寻找中',
    created_at   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  lost_found IS '失物招领表：存储失物/拾物信息';
COMMENT ON COLUMN lost_found.lf_id        IS '记录ID，自增主键';
COMMENT ON COLUMN lost_found.publisher_id IS '发布人用户ID';
COMMENT ON COLUMN lost_found.type         IS '类型：失物 或 拾物';
COMMENT ON COLUMN lost_found.title        IS '物品标题';
COMMENT ON COLUMN lost_found.description  IS '物品详细描述';
COMMENT ON COLUMN lost_found.location     IS '丢失/拾获地点';
COMMENT ON COLUMN lost_found.lf_date      IS '丢失/拾获日期';
COMMENT ON COLUMN lost_found.contact      IS '联系方式';
COMMENT ON COLUMN lost_found.status       IS '状态：寻找中/已认领/已关闭';
COMMENT ON COLUMN lost_found.created_at   IS '发布时间';
COMMENT ON COLUMN lost_found.updated_at   IS '更新时间';

-- ----------------------------
-- 13. claim_requests（认领申请表）— 王旭坤
-- ----------------------------
CREATE TABLE IF NOT EXISTS claim_requests (
    claim_id     SERIAL          PRIMARY KEY,
    lf_id        INTEGER         NOT NULL,
    claimant_id  INTEGER         NOT NULL,
    description  TEXT            NOT NULL,
    status       VARCHAR(20)     DEFAULT '待审核',
    auditor_id   INTEGER,
    audit_time   TIMESTAMP,
    audit_remark VARCHAR(255),
    created_at   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  claim_requests IS '认领申请表：用户对失物招领的认领申请';
COMMENT ON COLUMN claim_requests.claim_id    IS '申请ID，自增主键';
COMMENT ON COLUMN claim_requests.lf_id       IS '失物记录ID';
COMMENT ON COLUMN claim_requests.claimant_id IS '申请人用户ID';
COMMENT ON COLUMN claim_requests.description IS '认领说明（物品特征等证明信息）';
COMMENT ON COLUMN claim_requests.status      IS '状态：待审核/已通过/已拒绝';
COMMENT ON COLUMN claim_requests.auditor_id  IS '审核人ID（管理员）';
COMMENT ON COLUMN claim_requests.audit_time  IS '审核时间';
COMMENT ON COLUMN claim_requests.audit_remark IS '审核备注';
COMMENT ON COLUMN claim_requests.created_at  IS '申请时间';

-- ----------------------------
-- 14. reports（举报记录表）— 刘子懿
-- ----------------------------
CREATE TABLE IF NOT EXISTS reports (
    report_id     SERIAL          PRIMARY KEY,
    reporter_id   INTEGER         NOT NULL,
    reported_type VARCHAR(30)     NOT NULL,
    reported_id   INTEGER         NOT NULL,
    reason        TEXT            NOT NULL,
    status        VARCHAR(20)     DEFAULT '待处理',
    handler_id    INTEGER,
    handle_result VARCHAR(255),
    handle_time   TIMESTAMP,
    created_at    TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  reports IS '举报记录表：存储用户举报信息';
COMMENT ON COLUMN reports.report_id     IS '举报ID，自增主键';
COMMENT ON COLUMN reports.reporter_id   IS '举报人用户ID';
COMMENT ON COLUMN reports.reported_type IS '举报对象类型：商品/用户';
COMMENT ON COLUMN reports.reported_id   IS '被举报对象ID（商品ID或用户ID）';
COMMENT ON COLUMN reports.reason        IS '举报原因';
COMMENT ON COLUMN reports.status        IS '处理状态：待处理/已处理/已驳回';
COMMENT ON COLUMN reports.handler_id    IS '处理人ID（管理员）';
COMMENT ON COLUMN reports.handle_result IS '处理结果';
COMMENT ON COLUMN reports.handle_time   IS '处理时间';
COMMENT ON COLUMN reports.created_at    IS '举报时间';

-- ----------------------------
-- 15. audit_logs（审核日志表）— 刘子懿
-- ----------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id      SERIAL          PRIMARY KEY,
    auditor_id  INTEGER         NOT NULL,
    audit_type  VARCHAR(30)     NOT NULL,
    target_id   INTEGER         NOT NULL,
    result      VARCHAR(20)     NOT NULL,
    remark      VARCHAR(255),
    created_at  TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  audit_logs IS '审核日志表：记录所有管理员审核操作的日志';
COMMENT ON COLUMN audit_logs.log_id     IS '日志ID，自增主键';
COMMENT ON COLUMN audit_logs.auditor_id IS '审核人（管理员）用户ID';
COMMENT ON COLUMN audit_logs.audit_type IS '审核类型：商品审核/认领审核/举报处理/用户管理';
COMMENT ON COLUMN audit_logs.target_id  IS '审核对象ID';
COMMENT ON COLUMN audit_logs.result     IS '审核结果：通过/驳回/拒绝/禁用/启用';
COMMENT ON COLUMN audit_logs.remark     IS '审核备注';
COMMENT ON COLUMN audit_logs.created_at IS '审核时间';


-- ============================================================
-- 第三部分：添加外键约束
-- ============================================================

-- user_roles 外键
ALTER TABLE user_roles
    ADD CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    ADD CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) REFERENCES roles(role_id);

-- categories 自引用外键
ALTER TABLE categories
    ADD CONSTRAINT fk_categories_parent FOREIGN KEY (parent_id) REFERENCES categories(category_id);

-- products 外键
ALTER TABLE products
    ADD CONSTRAINT fk_products_seller   FOREIGN KEY (seller_id)   REFERENCES users(user_id),
    ADD CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(category_id);

-- product_images 外键（级联删除）
ALTER TABLE product_images
    ADD CONSTRAINT fk_product_images_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE;

-- favorites 外键
ALTER TABLE favorites
    ADD CONSTRAINT fk_favorites_user    FOREIGN KEY (user_id)    REFERENCES users(user_id),
    ADD CONSTRAINT fk_favorites_product FOREIGN KEY (product_id) REFERENCES products(product_id);

-- orders 外键
ALTER TABLE orders
    ADD CONSTRAINT fk_orders_buyer   FOREIGN KEY (buyer_id)   REFERENCES users(user_id),
    ADD CONSTRAINT fk_orders_product FOREIGN KEY (product_id) REFERENCES products(product_id);

-- payments 外键
ALTER TABLE payments
    ADD CONSTRAINT fk_payments_order FOREIGN KEY (order_id) REFERENCES orders(order_id),
    ADD CONSTRAINT fk_payments_payer FOREIGN KEY (payer_id) REFERENCES users(user_id);

-- reviews 外键
ALTER TABLE reviews
    ADD CONSTRAINT fk_reviews_order     FOREIGN KEY (order_id)     REFERENCES orders(order_id),
    ADD CONSTRAINT fk_reviews_reviewer  FOREIGN KEY (reviewer_id)  REFERENCES users(user_id),
    ADD CONSTRAINT fk_reviews_reviewee  FOREIGN KEY (reviewee_id)  REFERENCES users(user_id);

-- credit_records 外键
ALTER TABLE credit_records
    ADD CONSTRAINT fk_credit_records_user FOREIGN KEY (user_id) REFERENCES users(user_id);

-- lost_found 外键
ALTER TABLE lost_found
    ADD CONSTRAINT fk_lost_found_publisher FOREIGN KEY (publisher_id) REFERENCES users(user_id);

-- claim_requests 外键
ALTER TABLE claim_requests
    ADD CONSTRAINT fk_claim_requests_lf        FOREIGN KEY (lf_id)       REFERENCES lost_found(lf_id),
    ADD CONSTRAINT fk_claim_requests_claimant  FOREIGN KEY (claimant_id) REFERENCES users(user_id),
    ADD CONSTRAINT fk_claim_requests_auditor   FOREIGN KEY (auditor_id)  REFERENCES users(user_id);

-- reports 外键
ALTER TABLE reports
    ADD CONSTRAINT fk_reports_reporter FOREIGN KEY (reporter_id) REFERENCES users(user_id),
    ADD CONSTRAINT fk_reports_handler  FOREIGN KEY (handler_id)  REFERENCES users(user_id);

-- audit_logs 外键
ALTER TABLE audit_logs
    ADD CONSTRAINT fk_audit_logs_auditor FOREIGN KEY (auditor_id) REFERENCES users(user_id);


-- ============================================================
-- 第四部分：创建索引（提升查询性能）
-- ============================================================

-- users 表索引
CREATE INDEX IF NOT EXISTS idx_users_student_id   ON users(student_id);
CREATE INDEX IF NOT EXISTS idx_users_status       ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_credit_score ON users(credit_score);

-- user_roles 表索引（唯一约束已自动创建索引，此处加速 user_id 单独查询）
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);

-- products 表索引
CREATE INDEX IF NOT EXISTS idx_products_seller_id   ON products(seller_id);
CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_status      ON products(status);
CREATE INDEX IF NOT EXISTS idx_products_created_at  ON products(created_at DESC);

-- product_images 表索引
CREATE INDEX IF NOT EXISTS idx_product_images_product_id ON product_images(product_id);

-- favorites 表索引（唯一约束已覆盖 user_id + product_id）
CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);

-- orders 表索引
CREATE INDEX IF NOT EXISTS idx_orders_buyer_id   ON orders(buyer_id);
CREATE INDEX IF NOT EXISTS idx_orders_product_id ON orders(product_id);
CREATE INDEX IF NOT EXISTS idx_orders_status     ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);

-- payments 表索引（order_id UNIQUE 已自动创建索引）
CREATE INDEX IF NOT EXISTS idx_payments_payer_id ON payments(payer_id);

-- reviews 表索引
CREATE INDEX IF NOT EXISTS idx_reviews_order_id    ON reviews(order_id);
CREATE INDEX IF NOT EXISTS idx_reviews_reviewer_id ON reviews(reviewer_id);
CREATE INDEX IF NOT EXISTS idx_reviews_reviewee_id ON reviews(reviewee_id);

-- credit_records 表索引
CREATE INDEX IF NOT EXISTS idx_credit_records_user_id  ON credit_records(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_records_created  ON credit_records(created_at DESC);

-- lost_found 表索引
CREATE INDEX IF NOT EXISTS idx_lost_found_publisher_id ON lost_found(publisher_id);
CREATE INDEX IF NOT EXISTS idx_lost_found_status       ON lost_found(status);
CREATE INDEX IF NOT EXISTS idx_lost_found_type         ON lost_found(type);

-- claim_requests 表索引
CREATE INDEX IF NOT EXISTS idx_claim_requests_lf_id      ON claim_requests(lf_id);
CREATE INDEX IF NOT EXISTS idx_claim_requests_claimant_id ON claim_requests(claimant_id);
CREATE INDEX IF NOT EXISTS idx_claim_requests_status     ON claim_requests(status);

-- reports 表索引
CREATE INDEX IF NOT EXISTS idx_reports_reporter_id ON reports(reporter_id);
CREATE INDEX IF NOT EXISTS idx_reports_status      ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_handler_id  ON reports(handler_id);

-- audit_logs 表索引
CREATE INDEX IF NOT EXISTS idx_audit_logs_auditor_id ON audit_logs(auditor_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_type       ON audit_logs(audit_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);


-- ============================================================
-- 第五部分：插入初始数据
-- ============================================================

-- 角色初始数据（预置：学生、管理员）
INSERT INTO roles (role_name, description) VALUES
    ('学生',   '普通学生用户，可买卖商品、发布失物招领'),
    ('管理员', '系统管理员，负责审核商品、认领、举报及用户管理')
ON CONFLICT (role_name) DO NOTHING;

-- 商品分类初始数据（预置 6 个一级分类）
INSERT INTO categories (category_name, parent_id, sort_order) VALUES
    ('书籍',       NULL, 1),
    ('电子产品',   NULL, 2),
    ('生活用品',   NULL, 3),
    ('服装鞋帽',   NULL, 4),
    ('运动户外',   NULL, 5),
    ('其他',       NULL, 6)
ON CONFLICT (category_name) DO NOTHING;


-- ============================================================
-- 第六部分：触发器函数与触发器
-- ============================================================

-- ----------------------------
-- 触发器1: trg_order_complete（订单完成时自动更新信用分和商品状态）
-- ----------------------------
CREATE OR REPLACE FUNCTION fn_order_complete()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_seller_id   INTEGER;
    v_credit_new  INTEGER;
BEGIN
    -- 仅当订单状态从非"已完成"变为"已完成"时触发
    IF NEW.status = '已完成' AND (OLD.status IS NULL OR OLD.status <> '已完成') THEN

        -- 1. 将对应商品状态改为"已售出"
        UPDATE products
           SET status     = '已售出',
               updated_at = CURRENT_TIMESTAMP
         WHERE product_id = NEW.product_id;

        -- 2. 买家信用分 +2（完成交易奖励）
        UPDATE users
           SET credit_score = credit_score + 2,
               updated_at   = CURRENT_TIMESTAMP
         WHERE user_id = NEW.buyer_id
         RETURNING credit_score INTO v_credit_new;

        -- 记录买家信用变动
        INSERT INTO credit_records (user_id, change_type, change_value, score_after, related_id, remark)
        VALUES (NEW.buyer_id, '交易完成', 2, v_credit_new, NEW.order_id, '买家完成订单，信用分+2');

        -- 3. 卖家信用分 +2（成功售出奖励，V1.1 与 02 修复脚本一致）
        SELECT seller_id INTO v_seller_id FROM products WHERE product_id = NEW.product_id;

        UPDATE users
           SET credit_score = credit_score + 2,
               updated_at   = CURRENT_TIMESTAMP
         WHERE user_id = v_seller_id
         RETURNING credit_score INTO v_credit_new;

        INSERT INTO credit_records (user_id, change_type, change_value, score_after, related_id, remark)
        VALUES (v_seller_id, '交易完成', 2, v_credit_new, NEW.order_id, '卖家商品售出，信用分+2');

        -- 4. 记录订单完成时间
        NEW.completed_at = CURRENT_TIMESTAMP;

    END IF;

    RETURN NEW;
END;
$$;

-- 绑定触发器
DROP TRIGGER IF EXISTS trg_order_complete ON orders;
CREATE TRIGGER trg_order_complete
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION fn_order_complete();


-- ----------------------------
-- 触发器2: trg_review_insert（收到评价时根据评分更新信用分）
-- ----------------------------
CREATE OR REPLACE FUNCTION fn_review_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_change_value INTEGER;
    v_score_after  INTEGER;
    v_change_type  VARCHAR(30);
BEGIN
    -- 根据评分计算信用分变动值（V1.1 与 02 修复脚本一致）
    -- 5分 → +3, 4分 → +2, 3分 → 0, 2分 → -2, 1分 → -5
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

    -- 更新被评价人的信用分
    UPDATE users
       SET credit_score = credit_score + v_change_value,
           updated_at   = CURRENT_TIMESTAMP
     WHERE user_id = NEW.reviewee_id
     RETURNING credit_score INTO v_score_after;

    -- 写入信用记录
    INSERT INTO credit_records (user_id, change_type, change_value, score_after, related_id, remark)
    VALUES (NEW.reviewee_id, v_change_type, v_change_value, v_score_after, NEW.review_id,
            '收到评价，评分' || NEW.rating || '分，信用分' || CASE WHEN v_change_value >= 0 THEN '+' ELSE '' END || v_change_value);

    RETURN NEW;
END;
$$;

-- 绑定触发器
DROP TRIGGER IF EXISTS trg_review_insert ON reviews;
CREATE TRIGGER trg_review_insert
    AFTER INSERT ON reviews
    FOR EACH ROW
    EXECUTE FUNCTION fn_review_insert();


-- ----------------------------
-- 触发器3: trg_payment_insert（支付后自动更新订单状态）
-- ----------------------------
CREATE OR REPLACE FUNCTION fn_payment_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- 支付后自动将订单状态改为"已支付"
    UPDATE orders
       SET status  = '已支付',
           paid_at = CURRENT_TIMESTAMP
     WHERE order_id = NEW.order_id;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_payment_insert ON payments;
CREATE TRIGGER trg_payment_insert
    AFTER INSERT ON payments
    FOR EACH ROW
    EXECUTE FUNCTION fn_payment_insert();


-- ============================================================
-- 第七部分：存储过程
-- ============================================================

-- ----------------------------
-- 存储过程1: sp_create_order（创建订单并锁定商品）
-- ----------------------------
CREATE OR REPLACE PROCEDURE sp_create_order(
    IN  p_buyer_id   INTEGER,
    IN  p_product_id INTEGER,
    OUT p_order_id   INTEGER,
    OUT p_order_no   VARCHAR(32),
    OUT p_error_msg  VARCHAR(255)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_price      DECIMAL(10,2);
    v_status     VARCHAR(20);
    v_seller_id  INTEGER;
BEGIN
    p_error_msg := NULL;

    -- 检查商品是否存在且可购买（FOR UPDATE 防止并发抢购）
    SELECT price, status, seller_id
      INTO v_price, v_status, v_seller_id
      FROM products
     WHERE product_id = p_product_id
       FOR UPDATE;

    IF NOT FOUND THEN
        p_error_msg := '商品不存在';
        RETURN;
    END IF;

    IF v_status <> '已上架' THEN
        p_error_msg := '商品当前状态不可购买：' || COALESCE(v_status, '未知');
        RETURN;
    END IF;

    IF v_seller_id = p_buyer_id THEN
        p_error_msg := '不能购买自己发布的商品';
        RETURN;
    END IF;

    -- 生成订单编号：格式 ORD + 年月日时分秒 + 4位随机数
    p_order_no := 'ORD' || TO_CHAR(CURRENT_TIMESTAMP, 'YYYYMMDDHH24MISS') ||
                  LPAD(FLOOR(RANDOM() * 10000)::TEXT, 4, '0');

    -- 插入订单
    INSERT INTO orders (order_no, buyer_id, product_id, amount, status)
    VALUES (p_order_no, p_buyer_id, p_product_id, v_price, '待付款')
    RETURNING order_id INTO p_order_id;

    -- 锁定商品（防止重复下单）
    UPDATE products
       SET status     = '已锁定',
           updated_at = CURRENT_TIMESTAMP
     WHERE product_id = p_product_id;

END;
$$;

COMMENT ON PROCEDURE sp_create_order IS '创建订单：验证商品可购买 → 生成订单编号 → 插入订单 → 锁定商品';


-- ----------------------------
-- 存储过程2: sp_confirm_order（确认收货）
-- ----------------------------
CREATE OR REPLACE PROCEDURE sp_confirm_order(
    IN  p_order_id  INTEGER,
    IN  p_buyer_id  INTEGER,
    OUT p_error_msg VARCHAR(255)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_status    VARCHAR(20);
    v_buyer_id  INTEGER;
BEGIN
    p_error_msg := NULL;

    SELECT status, buyer_id
      INTO v_status, v_buyer_id
      FROM orders
     WHERE order_id = p_order_id;

    IF NOT FOUND THEN
        p_error_msg := '订单不存在';
        RETURN;
    END IF;

    IF v_buyer_id <> p_buyer_id THEN
        p_error_msg := '无权操作此订单';
        RETURN;
    END IF;

    IF v_status <> '已支付' THEN
        p_error_msg := '订单状态不正确，当前状态：' || COALESCE(v_status, '未知') || '，需要状态：已支付';
        RETURN;
    END IF;

    -- 更新订单状态为"已完成"（触发器 trg_order_complete 会自动处理后续逻辑）
    UPDATE orders
       SET status       = '已完成',
           completed_at = CURRENT_TIMESTAMP
     WHERE order_id = p_order_id;

END;
$$;

COMMENT ON PROCEDURE sp_confirm_order IS '确认收货：验证权限 → 将订单状态改为已完成（触发器自动处理信用分和商品状态）';


-- ----------------------------
-- 存储过程3: sp_audit_claim（审核认领申请）
-- ----------------------------
CREATE OR REPLACE PROCEDURE sp_audit_claim(
    IN  p_claim_id    INTEGER,
    IN  p_auditor_id  INTEGER,
    IN  p_result      VARCHAR(20),
    IN  p_remark      VARCHAR(255),
    OUT p_error_msg   VARCHAR(255)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_status VARCHAR(20);
    v_lf_id  INTEGER;
BEGIN
    p_error_msg := NULL;

    -- 验证参数
    IF p_result NOT IN ('已通过', '已拒绝') THEN
        p_error_msg := '审核结果只能是"已通过"或"已拒绝"';
        RETURN;
    END IF;

    SELECT status, lf_id
      INTO v_status, v_lf_id
      FROM claim_requests
     WHERE claim_id = p_claim_id;

    IF NOT FOUND THEN
        p_error_msg := '认领申请不存在';
        RETURN;
    END IF;

    IF v_status <> '待审核' THEN
        p_error_msg := '该申请已被处理，当前状态：' || COALESCE(v_status, '未知');
        RETURN;
    END IF;

    -- 更新认领申请
    UPDATE claim_requests
       SET status       = p_result,
           auditor_id   = p_auditor_id,
           audit_time   = CURRENT_TIMESTAMP,
           audit_remark = p_remark
     WHERE claim_id = p_claim_id;

    -- 如果审核通过，更新失物招领状态为"已认领"
    IF p_result = '已通过' THEN
        UPDATE lost_found
           SET status     = '已认领',
               updated_at = CURRENT_TIMESTAMP
         WHERE lf_id = v_lf_id;
    END IF;

    -- 写入审核日志
    INSERT INTO audit_logs (auditor_id, audit_type, target_id, result, remark)
    VALUES (p_auditor_id, '认领审核', p_claim_id, p_result, p_remark);

END;
$$;

COMMENT ON PROCEDURE sp_audit_claim IS '审核认领申请：验证状态 → 更新申请结果 → 若通过则更新失物状态 → 写入审核日志';


-- ----------------------------
-- 存储过程4: sp_audit_product（管理员审核商品）
-- ----------------------------
CREATE OR REPLACE PROCEDURE sp_audit_product(
    IN  p_product_id  INTEGER,
    IN  p_auditor_id  INTEGER,
    IN  p_result      VARCHAR(20),
    IN  p_remark      VARCHAR(255),
    OUT p_error_msg   VARCHAR(255)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_status VARCHAR(20);
BEGIN
    p_error_msg := NULL;

    -- 验证参数
    IF p_result NOT IN ('通过', '驳回') THEN
        p_error_msg := '审核结果只能是"通过"或"驳回"';
        RETURN;
    END IF;

    SELECT status INTO v_status
      FROM products
     WHERE product_id = p_product_id;

    IF NOT FOUND THEN
        p_error_msg := '商品不存在';
        RETURN;
    END IF;

    IF v_status <> '待审核' THEN
        p_error_msg := '该商品已被审核，当前状态：' || COALESCE(v_status, '未知');
        RETURN;
    END IF;

    -- 更新商品状态
    IF p_result = '通过' THEN
        UPDATE products
           SET status     = '已上架',
               updated_at = CURRENT_TIMESTAMP
         WHERE product_id = p_product_id;
    ELSE
        UPDATE products
           SET status     = '审核驳回',
               updated_at = CURRENT_TIMESTAMP
         WHERE product_id = p_product_id;
    END IF;

    -- 写入审核日志
    INSERT INTO audit_logs (auditor_id, audit_type, target_id, result, remark)
    VALUES (p_auditor_id, '商品审核', p_product_id, p_result, p_remark);

END;
$$;

COMMENT ON PROCEDURE sp_audit_product IS '商品审核：验证商品状态 → 通过改为已上架/驳回改为审核驳回 → 写入审核日志';


-- ----------------------------
-- 存储过程5: sp_handle_report（管理员处理举报）
-- ----------------------------
CREATE OR REPLACE PROCEDURE sp_handle_report(
    IN  p_report_id   INTEGER,
    IN  p_handler_id  INTEGER,
    IN  p_result      VARCHAR(20),
    IN  p_remark      VARCHAR(255),
    OUT p_error_msg   VARCHAR(255)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_status        VARCHAR(20);
    v_reported_type VARCHAR(30);
    v_reported_id   INTEGER;
    v_score_after   INTEGER;
    v_old_score     INTEGER;
BEGIN
    p_error_msg := NULL;

    -- 验证参数
    IF p_result NOT IN ('通过', '驳回') THEN
        p_error_msg := '处理结果只能是"通过"或"驳回"';
        RETURN;
    END IF;

    SELECT status, reported_type, reported_id
      INTO v_status, v_reported_type, v_reported_id
      FROM reports
     WHERE report_id = p_report_id;

    IF NOT FOUND THEN
        p_error_msg := '举报不存在';
        RETURN;
    END IF;

    IF v_status <> '待处理' THEN
        p_error_msg := '该举报已被处理，当前状态：' || COALESCE(v_status, '未知');
        RETURN;
    END IF;

    -- 更新举报记录
    IF p_result = '通过' THEN
        UPDATE reports
           SET status        = '已处理',
               handler_id    = p_handler_id,
               handle_result = p_remark,
               handle_time   = CURRENT_TIMESTAMP
         WHERE report_id = p_report_id;

        -- 处理通过：若举报对象是用户，扣减信用分 -10（不低于 0）
        IF v_reported_type = '用户' THEN
            -- 先读取当前信用分
            SELECT credit_score INTO v_old_score
              FROM users
             WHERE user_id = v_reported_id;

            -- 扣减（GREATEST 保证不低于 0）
            UPDATE users
               SET credit_score = GREATEST(credit_score - 10, 0),
                   updated_at   = CURRENT_TIMESTAMP
             WHERE user_id = v_reported_id
             RETURNING credit_score INTO v_score_after;

            -- 记录实际扣除的分值
            INSERT INTO credit_records (user_id, change_type, change_value, score_after, related_id, remark)
            VALUES (v_reported_id, '举报扣分', v_score_after - v_old_score, v_score_after, p_report_id,
                    '举报处理通过，信用分-10：' || COALESCE(p_remark, ''));
        END IF;

        -- 写入审核日志
        INSERT INTO audit_logs (auditor_id, audit_type, target_id, result, remark)
        VALUES (p_handler_id, '举报处理', p_report_id, p_result, p_remark);

    ELSE
        -- 驳回举报
        UPDATE reports
           SET status        = '已驳回',
               handler_id    = p_handler_id,
               handle_result = p_remark,
               handle_time   = CURRENT_TIMESTAMP
         WHERE report_id = p_report_id;

        -- 写入审核日志
        INSERT INTO audit_logs (auditor_id, audit_type, target_id, result, remark)
        VALUES (p_handler_id, '举报处理', p_report_id, p_result, p_remark);
    END IF;

END;
$$;

COMMENT ON PROCEDURE sp_handle_report IS '举报处理：验证举报状态 → 通过则扣被举报用户信用分-10+写信用记录 → 写入审核日志';


-- ============================================================
-- 第八部分：视图（聚合统计）
-- ============================================================

-- ----------------------------
-- 视图1: v_product_stats（商品统计）
-- ----------------------------
CREATE OR REPLACE VIEW v_product_stats AS
SELECT
    c.category_id,
    c.category_name,
    COUNT(p.product_id)                                          AS total_products,
    COUNT(p.product_id) FILTER (WHERE p.status = '已售出')       AS sold_count,
    COUNT(p.product_id) FILTER (WHERE p.status = '已上架')       AS active_count,
    COALESCE(AVG(p.price) FILTER (WHERE p.status = '已上架'), 0) AS avg_price,
    COALESCE(SUM(p.view_count), 0)                               AS total_views
FROM categories c
LEFT JOIN products p ON c.category_id = p.category_id
GROUP BY c.category_id, c.category_name
ORDER BY total_products DESC;

COMMENT ON VIEW v_product_stats IS '商品统计视图：按分类统计商品数量、售出数、在售数、均价和总浏览量';


-- ----------------------------
-- 视图2: v_order_stats（订单统计）
-- ----------------------------
CREATE OR REPLACE VIEW v_order_stats AS
SELECT
    DATE(created_at)                         AS order_date,
    COUNT(*)                                 AS total_orders,
    COUNT(*) FILTER (WHERE status = '已完成') AS completed_orders,
    COUNT(*) FILTER (WHERE status = '已取消') AS cancelled_orders,
    COALESCE(SUM(amount) FILTER (WHERE status = '已完成'), 0) AS total_amount,
    COALESCE(AVG(amount) FILTER (WHERE status = '已完成'), 0) AS avg_amount
FROM orders
GROUP BY DATE(created_at)
ORDER BY order_date DESC;

COMMENT ON VIEW v_order_stats IS '订单统计视图：按日期统计订单数、完成数、取消数、总金额和均价';


-- ----------------------------
-- 视图3: v_credit_ranking（信用分排行）
-- ----------------------------
CREATE OR REPLACE VIEW v_credit_ranking AS
SELECT
    RANK() OVER (ORDER BY credit_score DESC) AS rank,
    user_id,
    student_id,
    user_name,
    nickname,
    credit_score,
    (SELECT COUNT(*) FROM credit_records cr WHERE cr.user_id = u.user_id) AS record_count
FROM users u
WHERE status = 0
ORDER BY credit_score DESC;

COMMENT ON VIEW v_credit_ranking IS '信用分排行视图：按信用分降序排列，含排名和信用记录数';


-- ----------------------------
-- 视图4: v_lost_found_stats（失物招领统计）
-- ----------------------------
CREATE OR REPLACE VIEW v_lost_found_stats AS
SELECT
    type,
    status,
    COUNT(*)                                                 AS total_count,
    COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE)  AS today_count
FROM lost_found
GROUP BY type, status
ORDER BY type, status;

COMMENT ON VIEW v_lost_found_stats IS '失物招领统计视图：按类型和状态统计失物招领数量';


-- ============================================================
-- 第九部分：自动更新 updated_at 的触发器函数（可选）
-- ============================================================

-- 通用函数：自动更新 updated_at 字段
CREATE OR REPLACE FUNCTION fn_auto_update_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

-- 为有 updated_at 字段的表绑定自动更新触发器
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN
        SELECT table_name
          FROM information_schema.columns
         WHERE column_name = 'updated_at'
           AND table_schema = 'public'
         GROUP BY table_name
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_auto_updated_at ON %I;
             CREATE TRIGGER trg_auto_updated_at
                 BEFORE UPDATE ON %I
                 FOR EACH ROW
                 EXECUTE FUNCTION fn_auto_update_timestamp();',
            tbl, tbl
        );
    END LOOP;
END;
$$;


-- ============================================================
-- 脚本执行完毕
-- ============================================================
-- 执行后请验证：
--   1. 表数量：SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';
--      （预期：15 张表）
--   2. 角色数据：SELECT * FROM roles;
--      （预期：2 行，学生 + 管理员）
--   3. 分类数据：SELECT * FROM categories;
--      （预期：6 行）
--   4. 触发器数量：SELECT COUNT(*) FROM pg_trigger WHERE tgname LIKE 'trg_%';
--      （预期：≥ 7 个触发器）
--   5. 存储过程：\df (查看函数/过程列表)
--      （预期：5 个存储过程 + 4 个触发器函数）
--   6. 视图：SELECT * FROM information_schema.views WHERE table_schema='public';
--      （预期：4 个视图）
-- ============================================================
