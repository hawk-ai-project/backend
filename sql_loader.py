# sql_loader.py
from pathlib import Path
from sqlalchemy import text

BASE_DIR = Path(__file__).resolve().parent


def load_all_sqls(sql_dir_path: str = "sql") -> dict:
    """
    sql_dir_path 폴더 내의 모든 .sql 파일을 스캔하여
    {"파일명.쿼리명": text("SQL문")} 형태의 통합 딕셔너리로 반환합니다.
    """
    target_dir = BASE_DIR / sql_dir_path
    sql_map = {}

    if not target_dir.exists():
        return sql_map

    # sql 폴더 안의 모든 .sql 파일 탐색
    for sql_file in target_dir.glob("**/*.sql"):
        file_namespace = sql_file.stem  # 파일명 (예: menu)

        current_name = None
        current_sql_lines = []

        with open(sql_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("-- name:"):
                    if current_name and current_sql_lines:
                        # 네임스페이스 적용 (예: menu.get_active_menus)
                        full_key = f"{file_namespace}.{current_name}"
                        sql_map[full_key] = text("".join(current_sql_lines).strip())
                        current_sql_lines = []

                    current_name = line.strip().replace("-- name:", "").strip()
                else:
                    if current_name:
                        current_sql_lines.append(line)

            if current_name and current_sql_lines:
                full_key = f"{file_namespace}.{current_name}"
                sql_map[full_key] = text("".join(current_sql_lines).strip())

    return sql_map