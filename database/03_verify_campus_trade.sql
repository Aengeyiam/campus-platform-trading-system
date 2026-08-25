-- ============================================================
-- campus_trade 修复后核验脚本
-- 只查询，不修改任何业务数据
-- ============================================================

-- 1. 当前数据库与用户
SELECT current_database() AS database_name, current_user AS db_user;

-- 2. 15 张基础表
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

SELECT COUNT(*) AS base_table_count
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE';

-- 3. 初始数据
SELECT role_id, role_name, description
FROM public.roles
ORDER BY role_id;

SELECT category_id, category_name, parent_id, sort_order
FROM public.categories
ORDER BY sort_order, category_id;

-- 4. 外键数量
-- 原完整脚本设计中应有 23 个外键约束。
SELECT COUNT(*) AS foreign_key_count
FROM pg_constraint con
JOIN pg_namespace n ON n.oid = con.connamespace
WHERE n.nspname = 'public'
  AND con.contype = 'f';

-- 5. 触发器
-- 物理触发器实例应为 6 个：
-- orders 1 + payments 1 + reviews 1
-- users/products/lost_found 各 1 个 updated_at 触发器
SELECT
    t.tgname AS trigger_name,
    c.relname AS table_name,
    pg_get_triggerdef(t.oid) AS trigger_definition
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE NOT t.tgisinternal
  AND n.nspname = 'public'
ORDER BY c.relname, t.tgname;

-- 6. 4 个触发器函数 + 5 个存储过程
SELECT
    p.proname AS routine_name
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND p.proname IN (
      'fn_order_complete',
      'fn_review_insert',
      'fn_payment_insert',
      'fn_auto_update_timestamp',
      'sp_create_order',
      'sp_confirm_order',
      'sp_audit_claim',
      'sp_audit_product',
      'sp_handle_report'
  )
ORDER BY p.proname;

SELECT COUNT(*) AS routine_count
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND p.proname IN (
      'fn_order_complete',
      'fn_review_insert',
      'fn_payment_insert',
      'fn_auto_update_timestamp',
      'sp_create_order',
      'sp_confirm_order',
      'sp_audit_claim',
      'sp_audit_product',
      'sp_handle_report'
  );

-- 7. 4 个视图
SELECT viewname
FROM pg_views
WHERE schemaname = 'public'
  AND viewname IN (
      'v_product_stats',
      'v_order_stats',
      'v_credit_ranking',
      'v_lost_found_stats'
  )
ORDER BY viewname;

-- 8. 直接查询视图，确认定义可以正常执行
SELECT * FROM public.v_product_stats LIMIT 5;
SELECT * FROM public.v_order_stats LIMIT 5;
SELECT * FROM public.v_credit_ranking LIMIT 5;
SELECT * FROM public.v_lost_found_stats LIMIT 5;

-- ============================================================
-- 期望结果
-- base_table_count      = 15
-- foreign_key_count     = 23
-- 触发器查询            = 6 行
-- routine_count         = 9
-- 视图查询              = 4 行
-- roles                 = 至少含 学生、管理员
-- categories            = 至少含 6 个预置一级分类
-- ============================================================
