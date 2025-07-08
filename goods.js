/* goods.js
 * 1) пытаемся взять тарифы из KV (ключ "tariffs")
 * 2) иначе используем массив из tariffs.js
 */

import LOCAL_TARIFFS from './tariffs.js';

export async function getGoods(env) {
  // ① KV-хранилище, если настроено
  if (env.GOODS_KV) {
    try {
      const raw = await env.GOODS_KV.get('tariffs');
      if (raw) return JSON.parse(raw);          // KV перекрывает файл
    } catch (e) {
      console.warn('KV read error, fallback to tariffs.js →', e);
    }
  }

  // ② локальный JS-модуль (уже распарсенный массив)
  return LOCAL_TARIFFS;
}
