import { escape } from './utils.js';

export async function createInvoice(good, env) {
  const invoiceId = crypto.randomUUID();

  let guid = '';
  let note = '';
  let url = '';

  try {
    const body = JSON.stringify({
      merchant_order_id: invoiceId,
      user_id: env?.PAYMENTS_USER_ID || 0,
      amount: good.price,
      method: env?.PAYMENTS_METHOD || 'card',
      email: env?.PAYMENTS_EMAIL || 'user@example.com'
    });

    const headers = { 'Content-Type': 'application/json' };
    if (env?.PAYMENTS_API_KEY) {
      headers['Authorization'] = `Bearer ${env.PAYMENTS_API_KEY}`;
    }

    const res = await fetch('https://1plat.cash/api/merchant/order/create/by-api', {
      method: 'POST',
      headers,
      body
    });

    const data = await res.json();
    guid = data.guid || '';
    note = data.payment?.note || '';
    url = data.url || '';
  } catch (e) {
    console.warn('createInvoice error →', e);
  }

  if (guid && env?.PAYMENTS_KV) {
    try { await env.PAYMENTS_KV.put(invoiceId, guid); } catch (e) {
      console.warn('KV put failed →', e);
    }
  }

  let html = '';
  if (note) {
    html = `<pre>${escape(note)}</pre>`;
  } else if (url) {
    html = `<a class="btn" href="${escape(url)}">Оплатить</a>`;
  }

  return { id: invoiceId, html };
}

export async function isPaid(invoiceId, env) {
  let guid = '';
  if (env?.PAYMENTS_KV) {
    try { guid = await env.PAYMENTS_KV.get(invoiceId) || ''; } catch (e) {
      console.warn('KV get failed →', e);
    }
  }

  if (!guid) return false;

  try {
    const headers = {};
    if (env?.PAYMENTS_API_KEY) {
      headers['Authorization'] = `Bearer ${env.PAYMENTS_API_KEY}`;
    }
    const res = await fetch(`https://1plat.cash/api/merchant/order/info/${guid}/by-api`, { headers });
    const data = await res.json();
    return data.status === 1;
  } catch (e) {
    console.warn('isPaid error →', e);
    return false;
  }}  