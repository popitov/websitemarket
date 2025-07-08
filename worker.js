// worker.js
//-----------------------------------------------------
//  Импорты вспомогательных модулей
//-----------------------------------------------------
import { html, CSS, escape }      from './utils.js';
import { getGoods }               from './goods.js';
import { createInvoice, isPaid }  from './payments.js';

//-----------------------------------------------------
//  Константы токена и редиректа
//-----------------------------------------------------
const RAW_KEY   = "0123456789abcdef0123456789abcdef";
const LINKS_KEY = "bots-json";

//-----------------------------------------------------
//  b64url + AES-GCM токен (как и раньше)
//-----------------------------------------------------
const b64url = u8 => btoa(String.fromCharCode(...u8))
  .replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");

const KEY_PROMISE = crypto.subtle.importKey(
  "raw", new TextEncoder().encode(RAW_KEY),
  { name:"AES-GCM" }, false, ["encrypt"]
);

async function exportToken(req){
  const ip = (req.headers.get("cf-connecting-ip")||"0.0.0.0")
      .match(/^(\d{1,3}\.){3}\d{1,3}$/) ? RegExp.lastMatch : "0.0.0.0";
  const cc = (req.headers.get("cf-ipcountry")||"--").slice(0,2);
  const ts = Math.floor(Date.now()/1000);

  const p = new Uint8Array(16);
  ip.split(".").forEach((n,i)=>p[i]=+n);
  p[4]=cc.charCodeAt(0)||0; p[5]=cc.charCodeAt(1)||0;
  new DataView(p.buffer).setUint32(6, ts);

  const iv  = crypto.getRandomValues(new Uint8Array(12));
  const key = await KEY_PROMISE;
  const ct  = new Uint8Array(await crypto.subtle.encrypt({name:"AES-GCM",iv},key,p));
  return b64url(new Uint8Array([...iv, ...ct]));
}

//-----------------------------------------------------
//  Основной обработчик
//-----------------------------------------------------
export default {
  async fetch(req, env) {
    const { pathname } = new URL(req.url);

    // 0 — кэшируем тарифы
    const GOODS = await getGoods(env);

    // 1 — Корень: две кнопки
    if (pathname === '/' || pathname === '') {
      const raw   = await env.LINKS_KV.get(LINKS_KEY);
      const links = raw ? JSON.parse(raw) : [];
      if (!links.length) return new Response("No links",{status:503});

      const token  = await exportToken(req);
      const botUrl = links[0] + (links[0].includes('?')?'&':'?') + 'start=' + token;

      return html(`
        <style>${CSS}</style>
        <div style="display:flex;justify-content:center;align-items:center;height:100vh">
          <div class="card" style="text-align:center">
            <h2>ℹ️ Получите доступ</h2>
            <a class="btn primary" href="${botUrl}">🚀 Перейти в бот</a>
            <a class="btn" href="/shop">💳 Приобрести здесь</a>
          </div>
        </div>`);
    }

    // 2 — /shop: список товаров
    if (pathname === '/shop') {
      const items = GOODS.map(g => `
        <div class="card">
          <h3>${escape(g.name)}</h3>
          <p>${escape(g.descr)}</p>
          <b>${g.price}&nbsp;₽</b><br>
          <form action="/buy" method="post">
            <input type="hidden" name="tid" value="${g.id}">
            <button>Купить</button>
          </form>
        </div>`).join('');
      return html(`<h1>Магазин</h1><div class="grid">${items}</div><style>${CSS}</style>`);
    }

    // 3 — /buy: выдаём реквизиты (пока заглушка)
    if (pathname === '/buy' && req.method === 'POST') {
      const fd  = await req.formData();
      const tid = +fd.get('tid');
      const good = GOODS.find(g => g.id === tid);
      if (!good) return new Response('Bad ID', {status:400});

      const invoice = await createInvoice(good);   // пока заглушка
      return html(`
        <h2>Оплата — ${escape(good.name)}</h2>
        <p>Переведите <b>${good.price} ₽</b> на реквизиты:</p>
        ${invoice.html}
        <form action="/check" method="post">
          <input type="hidden" name="tid" value="${tid}">
          <input type="hidden" name="inv" value="${invoice.id}">
          <button>✅ Я оплатил</button>
        </form>
        <form action="/shop" method="get" style="margin-top:8px">
          <button>❌ Отмена</button>
        </form>
        <style>${CSS}</style>
      `);
    }

    // 4 — /check: подтверждение
    if (pathname === '/check' && req.method === 'POST') {
      const fd  = await req.formData();
      const tid = +fd.get('tid'), inv = fd.get('inv');
      const good = GOODS.find(g => g.id === tid);
      if (!good) return new Response('bad', {status:400});

      const paid = await isPaid(inv);              // сейчас всегда true
      if (!paid)
        return html("<p>Платёж ещё не подтверждён.</p><a href=\"/shop\">← Назад</a>");

      return html(`
        <h2>✅ Спасибо за покупку!</h2>
        <pre>${escape(good.payload)}</pre>
        <a href="/shop">← Вернуться</a>
        <style>${CSS}</style>
      `);
    }

    // 404
    return new Response('Not found', {status:404});
  }
};
