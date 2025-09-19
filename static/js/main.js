// Плавная подсветка счётчика корзины при добавлении
document.addEventListener('DOMContentLoaded', () => {
  const el = document.getElementById('cart-count');
  if (!el) return;
  el.classList.add('pulse');
  setTimeout(() => el.classList.remove('pulse'), 500);
});
