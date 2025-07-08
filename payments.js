export async function createInvoice(good) {
    // TODO: подключить реальный провайдер
    const invoiceId = crypto.randomUUID();
    const html = `
      <ul><li>🏦 Тинькофф</li><li>📞 +7 999 123-45-67</li></ul>`;
    return { id: invoiceId, html };
  }
  
  export async function isPaid(invoiceId) {
    // TODO: проверять статус
    return true;
  }
  