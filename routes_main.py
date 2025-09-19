from __future__ import annotations
import uuid
import time
import hmac
import hashlib
from typing import List, Dict, Any, Optional

import requests
import redis
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, jsonify

import config
import db

main_bp = Blueprint('main', __name__)

# Память для ожидающих заказов (payment_id -> данные заказа)
PENDING_ORDERS: Dict[str, Dict[str, Any]] = {}

# -------------------- Вспомогательные --------------------

def _session_cart() -> List[Dict[str, Any]]:
    cart = session.get('cart')
    if not isinstance(cart, list):
        cart = []
        session['cart'] = cart
    return cart

def _cart_enriched(cart: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Вернуть структуру: items (расчётные позиции с именами/ценой/итогами), total (сумма)."""
    items = []
    total = 0
    for it in cart:
        tid = int(it['tariff_id'])
        qty = int(it.get('quantity', 1))
        dur = int(it.get('duration_seconds') or 0)
        t = db.get_tariff(tid)
        if not t:
            continue
        # цена по умолчанию
        price = int(t['price'])
        duration_name = None
        if dur > 0:
            # искать цену длительности
            for d in db.get_tariff_durations(tid):
                if int(d['seconds']) == dur:
                    price = int(d['price'])
                    duration_name = d['name']
                    break
        subtotal = price * qty
        total += subtotal
        items.append({
            "tariff_id": tid,
            "name": t['name'],
            "t_type": t['t_type'],
            "price": price,
            "quantity": qty,
            "subtotal": subtotal,
            "duration_seconds": dur,
            "duration_name": duration_name,
        })
    return {"items": items, "total": total}

def _require_tg_if_channel(cart_items: List[Dict[str, Any]]) -> bool:
    """Если в корзине есть доступ в канал — нужен Telegram login (tg_id > 0)."""
    if session.get('user_id') and int(session['user_id']) > 0:
        return True
    for it in cart_items:
        if it['t_type'] == 'channel' or it['t_type'] == 'bundle':
            # bundle может содержать channel — ради простоты требуем логин
            return False
    # только текст/статус — можно без логина
    return True

def _verify_telegram_login(data: Dict[str, str]) -> bool:
    tg_hash = data.get('hash')
    if not tg_hash or not config.TELEGRAM_LOGIN_TOKEN:
        return False
    # готовим data_check_string
    pairs = sorted([(k, v) for k, v in data.items() if k != 'hash'])
    data_check = '\n'.join([f"{k}={v}" for k, v in pairs])
    secret = hashlib.sha256(config.TELEGRAM_LOGIN_TOKEN.encode()).digest()
    calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, tg_hash)

def _set_auto_approve(channel_id: int, tg_id: int, ttl_seconds: Optional[int]) -> None:
    try:
        r = redis.from_url(config.REDIS_URL)
        key = f"auto:{channel_id}:{tg_id}"
        if ttl_seconds is None:
            r.set(key, "1")
        elif ttl_seconds > 0:
            r.setex(key, ttl_seconds, "1")
        r.close()
    except Exception as e:
        current_app.logger.warning(f"Redis auto-approve error: {e}")

# -------------------- Маршруты сайта --------------------

@main_bp.route('/')
def index():
    categories = db.get_categories(parent_id=None)
    # покажем на главной незакатегоризованные товары как подборку
    products = db.get_tariffs(category_id=0)
    return render_template('index.html', categories=categories, products=products)

@main_bp.route('/category/<int:cat_id>')
def category(cat_id: int):
    if cat_id == 0:
        category = {"id": 0, "name": "Uncategorized", "description": ""}
        products = db.get_tariffs(category_id=0)
        subs = []
    else:
        category = db.get_category(cat_id)
        if not category:
            flash("Категория не найдена", "error")
            return redirect(url_for('main.index'))
        products = db.get_tariffs(category_id=cat_id)
        subs = db.get_categories(parent_id=cat_id)
    return render_template('category.html', category=category, products=products, subcategories=subs)

@main_bp.route('/product/<int:tariff_id>')
def product_detail(tariff_id: int):
    product = db.get_tariff(tariff_id)
    if not product:
        flash("Товар не найден", "error")
        return redirect(url_for('main.index'))
    durations = db.get_tariff_durations(tariff_id)
    return render_template('product_detail.html', product=product, durations=durations)

@main_bp.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    tid = int(request.form.get('tariff_id'))
    dur = request.form.get('duration')
    dur = int(dur) if dur and str(dur).isdigit() else 0
    qty = 1
    cart = _session_cart()
    # проверка на дубликат — по товару и длительности
    for it in cart:
        if it['tariff_id'] == tid and int(it.get('duration_seconds') or 0) == dur:
            flash("Товар уже в корзине", "warning")
            return redirect(request.referrer or url_for('main.index'))
    cart.append({"tariff_id": tid, "duration_seconds": dur, "quantity": qty})
    session['cart'] = cart
    flash("Товар добавлен в корзину", "success")
    return redirect(request.referrer or url_for('main.index'))

@main_bp.route('/remove_from_cart/<int:tariff_id>')
def remove_from_cart(tariff_id: int):
    cart = _session_cart()
    cart = [it for it in cart if int(it['tariff_id']) != int(tariff_id)]
    session['cart'] = cart
    flash("Товар удалён из корзины", "info")
    return redirect(url_for('main.view_cart'))

@main_bp.route('/cart')
def view_cart():
    data = _cart_enriched(_session_cart())
    promo_code = session.get('promo_code')
    promo = None
    discount = 0
    if promo_code:
        promo = db.get_promocode(promo_code)
        if promo:
            applicable = True
            # ограничение на конкретный товар
            bt = promo.get('bound_tariff_id')
            if bt:
                applicable = any(it['tariff_id'] == bt for it in data['items'])
            # только новые
            if applicable and session.get('user_id') and int(session['user_id']) > 0:
                past = db.get_purchases(int(session['user_id']))
                if any(p.get('active') == 1 for p in past):
                    applicable = False
            if applicable:
                if promo.get('discount_type') == 'percent':
                    discount = data['total'] * int(promo.get('discount_value', 0)) // 100
                    if promo.get('max_discount') and discount > int(promo['max_discount']):
                        discount = int(promo['max_discount'])
                else:
                    discount = int(promo.get('discount_value') or 0)
                    if promo.get('max_discount') and discount > int(promo['max_discount']):
                        discount = int(promo['max_discount'])
            else:
                promo = None
                session.pop('promo_code', None)
                flash("Промокод не применим", "warning")
        else:
            session.pop('promo_code', None)
            flash("Промокод не найден", "warning")
    total_after = max(0, data['total'] - discount)
    return render_template('cart.html', items=data['items'], total=data['total'], 
                           promo=promo, discount=discount, total_after=total_after)

@main_bp.route('/apply_promo', methods=['POST'])
def apply_promo():
    code = (request.form.get('promo_code') or '').strip()
    if code:
        session['promo_code'] = code
        flash("Промокод применён (будет проверен при оплате)", "success")
    else:
        session.pop('promo_code', None)
    return redirect(url_for('main.view_cart'))

@main_bp.route('/checkout', methods=['POST'])
def checkout():
    cart = _session_cart()
    if not cart:
        flash("Корзина пуста", "error")
        return redirect(url_for('main.view_cart'))
    enriched = _cart_enriched(cart)
    # требуем Telegram-логин для каналов/бандлов
    if not _require_tg_if_channel(enriched['items']):
        flash("Для покупки доступа в каналы нужно войти через Telegram", "warning")
        return redirect(url_for('main.view_cart'))
    # итоговая сумма + промо
    total = enriched['total']
    promo_code = session.get('promo_code')
    if promo_code:
        promo = db.get_promocode(promo_code)
        if promo:
            applicable = True
            bt = promo.get('bound_tariff_id')
            if bt:
                applicable = any(it['tariff_id'] == bt for it in enriched['items'])
            if applicable:
                if promo.get('discount_type') == 'percent':
                    disc = total * int(promo.get('discount_value', 0)) // 100
                    if promo.get('max_discount') and disc > int(promo['max_discount']):
                        disc = int(promo['max_discount'])
                else:
                    disc = int(promo.get('discount_value') or 0)
                    if promo.get('max_discount') and disc > int(promo['max_discount']):
                        disc = int(promo['max_discount'])
                total = max(0, total - disc)
    payment_id = str(uuid.uuid4())
    payload = {
        "paymentMethod": 2,   # SBP
        "id": payment_id,
        "paymentDetails": {"amount": total, "currency": "RUB"},
        "description": "Оплата заказа в витрине",
        "return": f"{config.SITE_URL}/payment/{payment_id}",
        "failedUrl": f"{config.SITE_URL}/payment/{payment_id}?failed=1",
        "payload": "ORDER_PAYLOAD"
    }
    headers = {
        "Content-Type": "application/json",
        "X-MerchantId": config.PLATEGA_MERCHANT_ID,
        "X-Secret": config.PLATEGA_API_KEY
    }
    try:
        resp = requests.post(config.PLATEGA_CREATE_URL, json=payload, headers=headers, timeout=30)
        data = resp.json()
        redirect_url = data.get('redirect')
        if not redirect_url:
            raise RuntimeError('No redirect URL from Platega')
    except Exception as e:
        current_app.logger.exception(e)
        flash("Ошибка инициализации платежа", "error")
        return redirect(url_for('main.view_cart'))
    # сохраняем заказ в памяти
    PENDING_ORDERS[payment_id] = {
        "user_id": int(session.get('user_id') or -1),
        "items": enriched['items'],
        "total": total,
        "redirect_url": redirect_url,
        "delivered": False,
        "created_at": int(time.time())
    }
    # переходим на нашу страницу оплаты (покажем QR и будем опрашивать статус)
    return redirect(url_for('main.payment', payment_id=payment_id))

@main_bp.route('/payment/<payment_id>')
def payment(payment_id: str):
    order = PENDING_ORDERS.get(payment_id)
    if not order:
        # Возможно возврат с Platega returnUrl — покажем заглушку
        return render_template('payment.html', payment_id=payment_id, amount=0, redirect_url=None)
    return render_template('payment.html', payment_id=payment_id, amount=order['total'], redirect_url=order['redirect_url'])

@main_bp.route('/api/platega_qr/<payment_id>')
def api_platega_qr(payment_id: str):
    order = PENDING_ORDERS.get(payment_id)
    if not order:
        return jsonify({"ok": False, "error": "order not found"}), 404
    url = order['redirect_url']
    # Пробуем через Playwright достать qr.nspk.ru
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return jsonify({"ok": False, "need_open": True, "redirect_url": url})
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60000)
            # На странице Platega обычно кнопка «Оплатить» — попробуем кликнуть
            try:
                page.get_by_role("button", name="Оплатить").click(timeout=30000)
            except Exception:
                pass
            # Ожидаем переход на qr.nspk.ru
            for _ in range(30):
                time.sleep(1)
                cur_url = page.url
                if "qr.nspk.ru" in cur_url:
                    qr_url = cur_url
                    browser.close()
                    return jsonify({"ok": True, "qr_url": qr_url})
            browser.close()
        # не удалось — предложим открыть вручную
        return jsonify({"ok": False, "need_open": True, "redirect_url": url})
    except Exception as e:
        current_app.logger.warning(f"QR parse failed: {e}")
        return jsonify({"ok": False, "need_open": True, "redirect_url": url})

@main_bp.route('/api/payment_status/<payment_id>')
def api_payment_status(payment_id: str):
    order = PENDING_ORDERS.get(payment_id)
    status_url = config.PLATEGA_STATUS_URL.format(payment_id=payment_id)
    headers = {"X-MerchantId": config.PLATEGA_MERCHANT_ID, "X-Secret": config.PLATEGA_API_KEY}
    try:
        resp = requests.get(status_url, headers=headers, timeout=20)
        data = resp.json()
        status = (data.get('status') or '').lower()
    except Exception as e:
        return jsonify({"ok": False, "status": "error", "message": "status check failed"}), 200
    success_states = {"successful", "success", "completed", "paid", "confirmed"}
    if status in success_states:
        if order and not order.get('delivered') and not db.is_payment_processed(payment_id):
            _deliver_order(payment_id, order)
        return jsonify({"ok": True, "status": "confirmed"})
    elif status in {"pending", "processing", "created"}:
        return jsonify({"ok": True, "status": "pending"})
    else:
        return jsonify({"ok": True, "status": status})

@main_bp.route('/account')
def account():
    tg_id = int(session.get('user_id') or -1)
    purchases = []
    guest_purchases = session.get('guest_purchases') or []
    if tg_id > 0:
        purchases = db.get_purchases(tg_id)
        # человеко-читаемые даты
        for p in purchases:
            if p.get('expires_at'):
                p['expires_at_h'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(p['expires_at'])))
            else:
                p['expires_at_h'] = None
    return render_template('account.html', purchases=purchases, guest_purchases=guest_purchases)

@main_bp.route('/refresh_access/<int:purchase_id>')
def refresh_access(purchase_id: int):
    tg_id = int(session.get('user_id') or -1)
    if tg_id <= 0:
        flash("Войдите через Telegram", "warning")
        return redirect(url_for('main.account'))
    # найдём покупку пользователя
    for p in db.get_purchases(tg_id):
        if int(p['id']) == int(purchase_id) and p['t_type'] == 'channel':
            # попробуем выдать ту же ссылку (или другую из списка каналов)
            chans = db.get_tariff_channels(int(p['tariff_id']))
            cmap = db.get_channels_map()
            link = None; cid = None
            for c in chans:
                row = cmap.get(int(c))
                if row and row.get('invite_link'):
                    link = row['invite_link']; cid = int(c); break
            if not link:
                flash("Нет доступных ссылок канала", "warning")
                return redirect(url_for('main.account'))
            db.upsert_purchase(tg_id, int(p['tariff_id']), price=int(p.get('price') or 0),
                               link=link, duration_seconds=0, channel_id=cid, payment_id=p.get('payment_id') or "")
            _set_auto_approve(cid, tg_id, p.get('ttl_seconds'))
            flash("Ссылка обновлена", "success")
            return redirect(url_for('main.account'))
    flash("Покупка не найдена", "error")
    return redirect(url_for('main.account'))

# -------------------- Авторизация Telegram --------------------

@main_bp.route('/tg_login')
def tg_login():
    args = request.args.to_dict()
    if not _verify_telegram_login(args):
        flash("Не удалось подтвердить вход через Telegram", "error")
        return redirect(url_for('main.index'))
    tg_id = int(args.get('id'))
    session['user_id'] = tg_id
    session['tg_first_name'] = args.get('first_name')
    session['tg_username'] = args.get('username')
    db.ensure_user(tg_id, is_admin=(tg_id in config.ADMINS))
    flash("Вход через Telegram выполнен", "success")
    return redirect(url_for('main.index'))

@main_bp.route('/logout')
def logout():
    session.clear()
    flash("Вы вышли из аккаунта", "info")
    return redirect(url_for('main.index'))

# -------------------- Внутренняя выдача заказа --------------------

def _deliver_order(payment_id: str, order: Dict[str, Any]) -> None:
    tg_id = int(order.get('user_id') or -1)
    items = order['items']
    # Для гостей (tg_id <= 0) — выдаём только текстовые товары в сессию (account -> guest_purchases)
    guest_accum = session.get('guest_purchases') or []
    channels_map = db.get_channels_map()
    for it in items:
        t = db.get_tariff(int(it['tariff_id']))
        if not t:
            continue
        price = int(it['price']) * int(it['quantity'])
        dur = int(it.get('duration_seconds') or 0)
        if t['t_type'] == 'bundle':
            # выдаём бандл как набор его товаров
            for child_id in db.get_bundle_items(int(t['id'])):
                _deliver_single(tg_id, db.get_tariff(child_id), price=0, duration=dur,
                                payment_id=payment_id, channels_map=channels_map, guest_accum=guest_accum)
        else:
            _deliver_single(tg_id, t, price=price, duration=dur,
                            payment_id=payment_id, channels_map=channels_map, guest_accum=guest_accum)
    # Пометим платёж
    if tg_id > 0:
        db.mark_payment_processed(payment_id, tg_id, int(order['total']))
    order['delivered'] = True
    # Сохраним гостевые покупки обратно в сессию
    session['guest_purchases'] = guest_accum
    # Корзину очищаем
    session['cart'] = []

def _deliver_single(tg_id: int, tariff: Dict[str, Any], price: int, duration: int,
                    payment_id: str, channels_map: Dict[int, Dict[str, Any]], guest_accum: List[Dict[str, Any]]):
    ttype = tariff['t_type']
    if ttype == 'text':
        content = tariff.get('payload') or ''
        if tg_id > 0:
            db.upsert_purchase(tg_id, int(tariff['id']), price=price, link=content,
                               duration_seconds=0, channel_id=None, payment_id=payment_id)
        else:
            guest_accum.append({
                "name": tariff['name'],
                "type": "text",
                "content": content
            })
    elif ttype == 'status':
        code = str(uuid.uuid4())[:8]
        link = (f"{config.STATUS_BOT_LINK}?start={code}") if config.STATUS_BOT_LINK else code
        if tg_id > 0:
            db.upsert_purchase(tg_id, int(tariff['id']), price=price, link=link,
                               duration_seconds=0, channel_id=None, payment_id=payment_id)
        else:
            guest_accum.append({
                "name": tariff['name'],
                "type": "status",
                "link": link
            })
    else:
        # Канал / прочее: нужна ссылка приглашения
        chans = db.get_tariff_channels(int(tariff['id']))
        invite_link = None; chosen_cid = None
        for cid in chans:
            row = channels_map.get(int(cid))
            if row and row.get('invite_link'):
                invite_link = row['invite_link']; chosen_cid = int(cid); break
        if invite_link and tg_id > 0:
            db.upsert_purchase(tg_id, int(tariff['id']), price=price, link=invite_link,
                               duration_seconds=duration if duration > 0 else None,
                               channel_id=chosen_cid, payment_id=payment_id)
            ttl = duration if duration > 0 else None
            if chosen_cid is not None:
                _set_auto_approve(chosen_cid, tg_id, ttl)

