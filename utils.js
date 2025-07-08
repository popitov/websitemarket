// единые стили + мелочь
export const CSS = `
body{font:16px system-ui,sans-serif;margin:0;padding:24px;max-width:720px}
.grid{display:grid;gap:20px}
.card{border:1px solid #eee;border-radius:12px;padding:18px;box-shadow:0 1px 4px #0001}
button,a.btn{background:#24A1DE;color:#fff;border:0;border-radius:8px;padding:8px 18px;cursor:pointer}
button:hover,a.btn:hover{opacity:.9}
a.btn{display:block;margin:12px 0;text-decoration:none;font-weight:600;text-align:center}
pre{white-space:pre-wrap;border:1px dashed #bbb;background:#fafafa;padding:12px;border-radius:8px}
`;

export const escape = s => String(s).replace(/[&<>"]/g,
  c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

export const html = body => new Response(
  "<!doctype html><meta charset=utf-8>"+body,
  {headers:{'content-type':'text/html;charset=utf-8'}}
);
