from __future__ import annotations
from typing import List, Dict, Any, Optional

from flask import Blueprint, render_template, request, redirect, url_for, session, flash

import db
import config

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def _is_admin() -> bool:
    uid = session.get('user_id')
    try:
        return int(uid) in config.ADMINS
    except Exception:
        return False

@admin_bp.before_request
def _check_admin():
    # Разрешаем доступ к /admin без логина только на страницу-инструкцию логина
    if request.endpoint == 'admin.login_info':
        return
    if not _is_admin():
        return redirect(url_for('admin.login_info'))

@admin_bp.route('/login_info')
def login_info():
    return render_template('admin_base.html')

@admin_bp.route('/')
def index():
    return render_template('admin_base.html')

# -------- Categories --------

@admin_bp.route('/categories')
def categories():
    cats = db.get_categories(None)
    # добавим подкатегории/счётчики для удобства
    for c in cats:
        c['subcategories'] = db.get_categories(c['id'])
    uncategorized_count = len(db.get_tariffs(0))
    return render_template('admin_categories.html', categories=cats, uncategorized_count=uncategorized_count)

@admin_bp.route('/categories/new', methods=['GET', 'POST'])
def new_category():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        description = (request.form.get('description') or '').strip()
        parent = request.form.get('parent_id')
        parent_id = int(parent) if parent and parent.isdigit() else None
        if not name:
            flash('Введите название', 'error'); return redirect(url_for('admin.new_category'))
        db.add_category(name, description, parent_id)
        flash('Категория создана', 'success')
        return redirect(url_for('admin.categories'))
    all_top = db.get_categories(None)
    return render_template('admin_category_edit.html', category=None, all_categories=all_top)

@admin_bp.route('/categories/<int:cat_id>/edit', methods=['GET', 'POST'])
def edit_category(cat_id: int):
    cat = db.get_category(cat_id)
    if not cat:
        flash('Категория не найдена', 'error'); return redirect(url_for('admin.categories'))
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        description = (request.form.get('description') or '').strip()
        parent = request.form.get('parent_id')
        parent_id = int(parent) if parent and parent.isdigit() else None
        db.update_category(cat_id, name, description, parent_id)
        flash('Сохранено', 'success')
        return redirect(url_for('admin.categories'))
    all_top = db.get_categories(None)
    return render_template('admin_category_edit.html', category=cat, all_categories=all_top)

@admin_bp.route('/categories/<int:cat_id>/delete', methods=['POST'])
def delete_category(cat_id: int):
    db.delete_category(cat_id)
    flash('Удалено', 'success')
    return redirect(url_for('admin.categories'))

# -------- Tariffs --------

@admin_bp.route('/tariffs')
def tariffs():
    tariffs = db.get_tariffs(None)
    return render_template('admin_tariffs.html', tariffs=tariffs)

@admin_bp.route('/tariffs/new', methods=['GET', 'POST'])
def new_tariff():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        description = (request.form.get('description') or '').strip()
        price = int(request.form.get('price') or 0)
        t_type = request.form.get('t_type') or 'channel'
        category = request.form.get('category_id')
        category_id = int(category) if category and category.isdigit() else None

        payload = ''
        status_name = None
        if t_type == 'text':
            payload = request.form.get('text_content') or ''
        elif t_type == 'status':
            status_name = request.form.get('status_name') or ''
        elif t_type == 'channel':
            payload = request.form.get('source_link') or ''
        # bundle — payload не нужен

        new_id = db.add_tariff(name, description, price, t_type, payload, category_id, status_name)
        flash('Товар создан', 'success')
        if t_type == 'bundle':
            return redirect(url_for('admin.edit_tariff', tariff_id=new_id))
        return redirect(url_for('admin.tariffs'))
    categories = db.get_categories(None)
    return render_template('admin_tariff_edit.html', tariff=None, categories=categories, durations=[], bundle_items=[], all_tariffs=[])

@admin_bp.route('/tariffs/<int:tariff_id>/edit', methods=['GET', 'POST'])
def edit_tariff(tariff_id: int):
    t = db.get_tariff(tariff_id)
    if not t:
        flash('Товар не найден', 'error'); return redirect(url_for('admin.tariffs'))
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        description = (request.form.get('description') or '').strip()
        price = int(request.form.get('price') or 0)
        category = request.form.get('category_id')
        category_id = int(category) if category and category.isdigit() else None
        payload = None; status_name = None
        if t['t_type'] == 'text':
            payload = request.form.get('text_content') or ''
        elif t['t_type'] == 'status':
            status_name = request.form.get('status_name') or ''
        elif t['t_type'] == 'channel':
            payload = request.form.get('source_link') or ''
        db.update_tariff(tariff_id, name, description, price, category_id, payload, status_name)

        # Длительности — добавление новой (если поля заполнены)
        if t['t_type'] in ('channel', 'text', 'status'):
            nd_name = (request.form.get('new_duration_name') or '').strip()
            nd_sec = request.form.get('new_duration_seconds')
            nd_price = request.form.get('new_duration_price')
            nd_def = request.form.get('new_duration_default') == 'on'
            if nd_name and nd_sec and nd_sec.isdigit() and nd_price and nd_price.isdigit():
                db.add_tariff_duration(tariff_id, int(nd_sec), nd_name, int(nd_price), nd_def)

        # Для бандла — обновляем состав
        if t['t_type'] == 'bundle':
            items = request.form.getlist('bundle_items')
            try:
                item_ids = [int(x) for x in items]
            except Exception:
                item_ids = []
            db.set_bundle_items(tariff_id, item_ids)

        flash('Сохранено', 'success')
        return redirect(url_for('admin.tariffs'))
    categories = db.get_categories(None)
    durations = db.get_tariff_durations(tariff_id)
    bundle_items = []; all_tariffs = []
    if t['t_type'] == 'bundle':
        bundle_items = db.get_bundle_items(tariff_id)
        all_tariffs = [x for x in db.get_tariffs(None) if x['t_type'] != 'bundle' and x['id'] != tariff_id]
    return render_template('admin_tariff_edit.html', tariff=t, categories=categories, durations=durations,
                           bundle_items=bundle_items, all_tariffs=all_tariffs)

@admin_bp.route('/tariffs/<int:tariff_id>/delete', methods=['POST'])
def delete_tariff(tariff_id: int):
    db.delete_tariff(tariff_id)
    flash('Удалено', 'success')
    return redirect(url_for('admin.tariffs'))

@admin_bp.route('/tariffs/<int:tariff_id>/durations/<int:duration_id>/delete', methods=['POST'])
def delete_duration(tariff_id: int, duration_id: int):
    db.delete_tariff_duration(duration_id)
    flash('Длительность удалена', 'success')
    return redirect(url_for('admin.edit_tariff', tariff_id=tariff_id))
