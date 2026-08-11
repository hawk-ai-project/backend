-- 쿼리는 name 기준으로 구분
-- name: menu.get_active_menus
SELECT id, name, path, icon
FROM menu
WHERE is_use = 1
ORDER BY sort_order ASC;

-- name: get_menu_by_id
SELECT id, name, path, icon
FROM menu
WHERE id = :menu_id;

-- name: insert_menu
INSERT INTO menu (name, path, icon, is_use, sort_order)
VALUES (:name, :path, :icon, :is_use, :sort_order);

-- NAME : UPDATE_MENU_TEST
UPDATE MENU
SET NAME =:NAME
WHERE ID = 1