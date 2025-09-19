import time
from flask import Flask, g, session

import config
from routes_main import main_bp
from routes_admin import admin_bp

app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = config.SECRET_KEY

# Регистрация блюпринтов
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)

# Фильтр Jinja для форматирования timestamp
@app.template_filter('dt')
def _fmt_dt(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ts))) if ts else ""

# Контекст-процессор: прокидываем некоторые переменные во все шаблоны
@app.context_processor
def inject_globals():
    cart = session.get('cart') or []
    return {
        'cfg': config,
        'cart_count': sum(int(it.get('quantity', 1)) for it in cart)
    }

if __name__ == '__main__':
    app.run(debug=True)
