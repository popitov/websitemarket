import sqlite3
import time
from typing import List, Dict, Any, Optional

import config

def _connect():
    conn = sqlite3.connect(config.SHOP_DB, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        pass
    return conn

def _table_exists(conn, name: str) -> bool:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (name,))
    return cur.fetchone() is not None

def _column_exists(conn, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table});")
    cols = [r['name'] for r in cur.fetchall()]
    return column in cols

# ---------------- Categories ----------------

def get_categories(parent_id: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = _connect()
    if parent_id is None:
        cur = conn.execute("SELECT * FROM categories WHERE parent_id IS NULL ORDER BY name COLLATE NOCASE;")
    else:
        cur = conn.execute("SELECT * FROM categories WHERE parent_id = ? ORDER BY name COLLATE NOCASE;", (parent_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_category(cat_id: int) -> Optional[Dict[str, Any]]:
    conn = _connect()
    cur = conn.execute("SELECT * FROM categories WHERE id = ?;", (cat_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def add_category(name: str, description: str = "", parent_id: Optional[int] = None) -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO categories(name, description, parent_id) VALUES(?,?,?);",
                (name.strip(), description.strip(), parent_id))
    conn.commit()
    nid = cur.lastrowid
    conn.close()
    return nid

def update_category(cat_id: int, name: str, description: str, parent_id: Optional[int] = None) -> None:
    conn = _connect()
    conn.execute("UPDATE categories SET name=?, description=?, parent_id=? WHERE id=?;",
                 (name.strip(), description.strip(), parent_id, cat_id))
    conn.commit()
    conn.close()

def delete_category(cat_id: int) -> None:
    conn = _connect()
    # Товары делаем без категории
    try:
        conn.execute("UPDATE tariffs SET category_id = NULL WHERE category_id = ?;", (cat_id,))
    except Exception:
        pass
    conn.execute("DELETE FROM categories WHERE id = ?;", (cat_id,))
    conn.commit()
    conn.close()

# ---------------- Tariffs ----------------

def get_tariffs(category_id: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = _connect()
    if category_id is None:
        cur = conn.execute(
            "SELECT t.*, COALESCE(c.name,'') AS category_name "
            "FROM tariffs t LEFT JOIN categories c ON c.id = t.category_id "
            "ORDER BY t.name COLLATE NOCASE;"
        )
    else:
        if category_id == 0:
            cur = conn.execute(
                "SELECT t.*, '' AS category_name FROM tariffs t "
                "WHERE t.category_id IS NULL ORDER BY t.name COLLATE NOCASE;"
            )
        else:
            cur = conn.execute(
                "SELECT t.*, COALESCE(c.name,'') AS category_name "
                "FROM tariffs t LEFT JOIN categories c ON c.id = t.category_id "
                "WHERE t.category_id=? ORDER BY t.name COLLATE NOCASE;",
                (category_id,)
            )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_tariff(tariff_id: int) -> Optional[Dict[str, Any]]:
    conn = _connect()
    cur = conn.execute("SELECT * FROM tariffs WHERE id=?;", (tariff_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def add_tariff(name: str, description: str, price: int, t_type: str,
               payload: str = "", category_id: Optional[int] = None,
               status_name: Optional[str] = None) -> int:
    conn = _connect()
    cur = conn.cursor()
    # Опциональные колонки payload/status_name/position могут отсутствовать в некоторых версиях — проверяем
    cols = [c['name'] for c in conn.execute("PRAGMA table_info(tariffs);")]
    fields = ["name", "description", "price", "t_type"]
    values = [name.strip(), description.strip(), price, t_type]
    if "payload" in cols:
        fields.append("payload"); values.append(payload or "")
    if "status_name" in cols:
        fields.append("status_name"); values.append(status_name)
    if "category_id" in cols:
        fields.append("category_id"); values.append(category_id)
    sql = f"INSERT INTO tariffs({', '.join(fields)}) VALUES({', '.join(['?']*len(values))});"
    cur.execute(sql, tuple(values))
    conn.commit()
    nid = cur.lastrowid
    conn.close()
    return nid

def update_tariff(tariff_id: int, name: str, description: str, price: int,
                  category_id: Optional[int], payload: Optional[str] = None,
                  status_name: Optional[str] = None) -> None:
    conn = _connect()
    cols = [c['name'] for c in conn.execute("PRAGMA table_info(tariffs);")]
    sets = ["name=?", "description=?", "price=?", "category_id=?"]
    vals = [name.strip(), description.strip(), price, category_id]
    if payload is not None and "payload" in cols:
        sets.append("payload=?"); vals.append(payload)
    if status_name is not None and "status_name" in cols:
        sets.append("status_name=?"); vals.append(status_name)
    sql = f"UPDATE tariffs SET {', '.join(sets)} WHERE id=?;"
    vals.append(tariff_id)
    conn.execute(sql, tuple(vals))
    conn.commit()
    conn.close()

def delete_tariff(tariff_id: int) -> None:
    conn = _connect()
    conn.execute("DELETE FROM tariffs WHERE id=?;", (tariff_id,))
    try:
        conn.execute("DELETE FROM payments WHERE tariff_id=?;", (tariff_id,))
    except Exception:
        pass
    conn.commit()
    conn.close()

# ------------- Durations --------------

def get_tariff_durations(tariff_id: int) -> List[Dict[str, Any]]:
    conn = _connect()
    if not _table_exists(conn, "tariff_durations"):
        conn.close()
        return []
    cur = conn.execute("SELECT * FROM tariff_durations WHERE tariff_id=? ORDER BY seconds;", (tariff_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def add_tariff_duration(tariff_id: int, seconds: int, name: str, price: int, is_default: bool = False) -> None:
    conn = _connect()
    if not _table_exists(conn, "tariff_durations"):
        conn.close(); return
    cur = conn.cursor()
    if is_default:
        cur.execute("UPDATE tariff_durations SET is_default=0 WHERE tariff_id=?;", (tariff_id,))
    cur.execute("INSERT INTO tariff_durations(tariff_id, name, seconds, price, is_default) VALUES(?,?,?,?,?);",
                (tariff_id, name.strip(), seconds, price, 1 if is_default else 0))
    conn.commit()
    conn.close()

def delete_tariff_duration(duration_id: int) -> None:
    conn = _connect()
    if not _table_exists(conn, "tariff_durations"):
        conn.close(); return
    conn.execute("DELETE FROM tariff_durations WHERE id=?;", (duration_id,))
    conn.commit()
    conn.close()

# ------------- Channels / Bundles --------------

def get_tariff_channels(tariff_id: int) -> List[int]:
    conn = _connect()
    if not _table_exists(conn, "tariff_channels"):
        conn.close(); return []
    cur = conn.execute("SELECT channel_id FROM tariff_channels WHERE tariff_id=?;", (tariff_id,))
    out = [r['channel_id'] for r in cur.fetchall()]
    conn.close()
    return out

def get_channels_map() -> Dict[int, Dict[str, Any]]:
    conn = _connect()
    if not _table_exists(conn, "channels"):
        conn.close(); return {}
    cur = conn.execute("SELECT * FROM channels;")
    out = {int(r['id']): dict(r) for r in cur.fetchall()}
    conn.close()
    return out

def get_bundle_items(bundle_id: int) -> List[int]:
    conn = _connect()
    if not _table_exists(conn, "bundle_items"):
        conn.close(); return []
    cur = conn.execute("SELECT item_tariff_id FROM bundle_items WHERE bundle_id=?;", (bundle_id,))
    out = [r['item_tariff_id'] for r in cur.fetchall()]
    conn.close()
    return out

def set_bundle_items(bundle_id: int, item_ids: List[int]) -> None:
    conn = _connect()
    if not _table_exists(conn, "bundle_items"):
        conn.close(); return
    cur = conn.cursor()
    cur.execute("DELETE FROM bundle_items WHERE bundle_id=?;", (bundle_id,))
    for tid in item_ids:
        if tid == bundle_id: 
            continue
        try:
            cur.execute("INSERT OR IGNORE INTO bundle_items(bundle_id, item_tariff_id) VALUES(?,?);", (bundle_id, tid))
        except Exception:
            pass
    conn.commit()
    conn.close()

# ------------- Users & Purchases & Payments --------------

def ensure_user(tg_id: int, is_admin: bool = False) -> None:
    conn = _connect()
    cols = [c['name'] for c in conn.execute("PRAGMA table_info(users);")]
    # Минимальный набор колонок
    if "tg_id" not in cols:
        conn.close(); return
    # Попытка вставки "мягко" с минимальными полями
    try:
        if "created_at" in cols and "is_admin" in cols:
            conn.execute("INSERT OR IGNORE INTO users(tg_id, is_admin, created_at) VALUES(?, ?, strftime('%s','now'));",
                         (tg_id, 1 if is_admin else 0))
        elif "is_admin" in cols:
            conn.execute("INSERT OR IGNORE INTO users(tg_id, is_admin) VALUES(?, ?);",
                         (tg_id, 1 if is_admin else 0))
        else:
            conn.execute("INSERT OR IGNORE INTO users(tg_id) VALUES(?);", (tg_id,))
        conn.commit()
    except Exception:
        pass
    conn.close()

def get_purchases(tg_id: int) -> List[Dict[str, Any]]:
    conn = _connect()
    if not _table_exists(conn, "purchases"):
        conn.close(); return []
    cur = conn.execute(
        "SELECT p.*, t.name AS tariff_name, t.t_type "
        "FROM purchases p JOIN tariffs t ON t.id = p.tariff_id "
        "WHERE p.user_id=? ORDER BY p.bought_at DESC;",
        (tg_id,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def upsert_purchase(tg_id: int, tariff_id: int, price: int, link: str,
                    duration_seconds: Optional[int], channel_id: Optional[int], payment_id: str) -> int:
    conn = _connect()
    if not _table_exists(conn, "purchases"):
        conn.close(); return 0
    cur = conn.cursor()
    cur.execute("SELECT id, ttl_seconds FROM purchases WHERE user_id=? AND tariff_id=? LIMIT 1;", (tg_id, tariff_id))
    row = cur.fetchone()
    now = int(time.time())
    if row:
        pid = row['id']
        current_ttl = row['ttl_seconds'] if row['ttl_seconds'] is not None else 0
        if duration_seconds is None:
            new_ttl = None
        elif duration_seconds == 0:
            new_ttl = 0
        else:
            new_ttl = (current_ttl or 0) + duration_seconds
        expires_at = (now + new_ttl) if new_ttl and new_ttl > 0 else None
        if channel_id is None:
            cur.execute(
                "UPDATE purchases SET link=?, price=?, payment_id=?, ttl_seconds=?, active=1, last_ttl_update=?, expires_at=? WHERE id=?;",
                (link, price, payment_id, new_ttl, now, expires_at, pid)
            )
        else:
            cur.execute(
                "UPDATE purchases SET link=?, price=?, payment_id=?, ttl_seconds=?, last_channel_id=?, active=1, last_ttl_update=?, expires_at=? WHERE id=?;",
                (link, price, payment_id, new_ttl, channel_id, now, expires_at, pid)
            )
    else:
        ttl = duration_seconds
        expires_at = (now + ttl) if ttl and ttl > 0 else None
        cur.execute(
            "INSERT INTO purchases(user_id, tariff_id, link, price, payment_id, ttl_seconds, last_channel_id, bought_at, last_ttl_update, activated, active, expires_at) "
            "VALUES(?,?,?,?,?,?,?, ?, ?, 0, 1, ?);",
            (tg_id, tariff_id, link, price, payment_id, ttl, channel_id, now, now, expires_at)
        )
        pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid

def mark_payment_processed(guid: str, tg_id: int, total_amount: int) -> None:
    conn = _connect()
    if not _table_exists(conn, "payments"):
        conn.close(); return
    try:
        # tariff_id = 0 для заказа-корзины
        conn.execute("INSERT OR IGNORE INTO payments(guid, user_id, tariff_id, amount) VALUES(?,?,?,?);",
                     (guid, tg_id, 0, total_amount))
        conn.commit()
    except Exception:
        pass
    conn.close()

def is_payment_processed(guid: str) -> bool:
    conn = _connect()
    if not _table_exists(conn, "payments"):
        conn.close(); return False
    cur = conn.execute("SELECT 1 FROM payments WHERE guid=? LIMIT 1;", (guid,))
    ok = cur.fetchone() is not None
    conn.close()
    return ok

# ------------- Promocodes (если есть) --------------

def get_promocode(code: str) -> Optional[Dict[str, Any]]:
    conn = _connect()
    if not _table_exists(conn, "promocodes"):
        conn.close(); return None
    cur = conn.execute("SELECT * FROM promocodes WHERE code=? LIMIT 1;", (code.strip(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def decrement_promo_use(code: str) -> None:
    conn = _connect()
    if not _table_exists(conn, "promocodes"):
        conn.close(); return
    try:
        conn.execute("UPDATE promocodes SET uses_left = uses_left - 1 WHERE code=? AND uses_left IS NOT NULL AND uses_left > 0;", (code.strip(),))
        conn.commit()
    except Exception:
        pass
    conn.close()
