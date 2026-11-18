// Класс js ставится здесь, а не в <head>: если скрипт не загрузится, текст останется видимым.
document.documentElement.classList.add('js');

const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));

// Появление блоков при прокрутке.
const revealEls = document.querySelectorAll('[data-r]');
if ('IntersectionObserver' in window && !reduced) {
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
  revealEls.forEach((el) => io.observe(el));
} else {
  revealEls.forEach((el) => el.classList.add('in'));
}

// Сцена «всё в одной платформе»: самолёт, поезд, отель и такси одновременно слетаются в кабинет.
const merge = document.querySelector('.merge');
if (merge) {
  const flies = [...merge.querySelectorAll('.fly')];
  const tiles = [...merge.querySelectorAll('.tile')];
  const render = () => {
    let p = 1;
    if (!reduced) {
      const r = merge.getBoundingClientRect();
      const total = merge.offsetHeight - innerHeight;
      p = clamp(-r.top / Math.max(total, 1));
    }
    merge.style.setProperty('--lp', clamp(p / 0.15).toFixed(3));
    const q = clamp((p - 0.12) / 0.43);
    flies.forEach((f, i) => f.style.setProperty('--q', clamp(q * (1 + i * 0.04)).toFixed(3)));
    tiles.forEach((t) => t.classList.toggle('on', q >= 0.98));
    merge.classList.toggle('is-complete', p > 0.62);
  };
  addEventListener('scroll', render, { passive: true });
  addEventListener('resize', render);
  render();
}

// Фото и иконки: если файла ещё нет, показываем заглушку (место под фото или эмодзи).
document.querySelectorAll('.slot').forEach((slot) => {
  const img = slot.querySelector('img');
  const miss = () => slot.classList.add('missing');
  if (img.complete && img.naturalWidth === 0) miss();
  img.addEventListener('error', miss);
});

// Липкая кнопка на телефоне: после первого экрана, прячется у формы.
const sticky = document.querySelector('.sticky-cta');
const hero = document.querySelector('.hl-hero');
const request = document.querySelector('#request');
if (sticky && hero && request && 'IntersectionObserver' in window) {
  sticky.hidden = false;
  let heroGone = false;
  let formVisible = false;
  const upd = () => sticky.classList.toggle('on', heroGone && !formVisible);
  new IntersectionObserver(([e]) => { heroGone = !e.isIntersecting; upd(); }).observe(hero);
  new IntersectionObserver(([e]) => { formVisible = e.isIntersecting; upd(); }, { threshold: 0.15 }).observe(request);
}

// Cookie: выбор хранится только в браузере посетителя. Аналитику подключать лишь при выборе «Принять».
const cookie = document.querySelector('.cookie');
if (cookie) {
  let saved = null;
  try { saved = localStorage.getItem('aerotone-cookie'); } catch (e) { saved = null; }
  if (!saved) cookie.hidden = false;
  cookie.querySelectorAll('[data-cookie]').forEach((b) => b.addEventListener('click', () => {
    try { localStorage.setItem('aerotone-cookie', b.dataset.cookie); } catch (e) { /* без хранилища просто закрываем */ }
    cookie.hidden = true;
    // Здесь подключается счётчик аналитики после согласования текста с юристом.
  }));
}

// ===== Мессенджеры: заполнить, когда клиент подтвердит контакты. Пустое значение = кнопка скрыта. =====
const CONTACTS = {
  telegram: '', // например 'https://t.me/aerotone_support'
  whatsapp: '', // например 'https://wa.me/79991234567'
};
(() => {
  const box = document.querySelector('.msgr');
  if (!box) return;
  let any = false;
  box.querySelectorAll('[data-ch]').forEach((a) => {
    const url = CONTACTS[a.dataset.ch];
    if (url) { a.href = url; a.target = '_blank'; a.rel = 'noopener'; a.hidden = false; any = true; }
  });
  box.hidden = !any;
})();

// Подбор тем для демо по ответам компании. Финансовый прогноз не рассчитывается.
(() => {
  const box = document.querySelector('.quiz-box');
  if (!box) return;
  const steps = [...box.querySelectorAll('.qstep')];
  const result = box.querySelector('.qresult');
  const back = box.querySelector('.qback');
  const bar = box.querySelector('.quiz-progress i');
  const answers = {};
  let current = 1;
  function show(step) {
    current = step;
    steps.forEach((item) => { item.hidden = Number(item.dataset.q) !== step; });
    result.hidden = step !== 'done';
    box.dataset.step = String(step);
    bar.style.width = (step === 'done' ? 100 : Math.round(step / steps.length * 100)) + '%';
    back.hidden = step === 1 || step === 'done';
  }
  function finish() {
    show('done');
    const themes = ['Онлайн-бронирование и работа через менеджера'];
    if (answers[5] !== 'edo') themes.push('ЭДО и интеграция с 1С');
    if (answers[6] !== 'auto') themes.push('Лимиты и согласование поездок');
    if (answers[2] !== 'ru') themes.push('Зарубежные поездки и визовое сопровождение');
    result.querySelector('.qr-ctx').textContent = themes.join(' · ');
    result.querySelector('.qr-verdict').textContent = 'Покажем подходящие сценарии и обсудим условия обслуживания. Отдельной платы за использование платформы нет, сервисные сборы согласуем индивидуально.';
    const trips = {2: 'q1', 7: 'q2', 20: 'q3', 40: 'q4'};
    document.querySelector('#lead-form [name="trips"]').value = trips[answers[1]] || '';
    document.querySelector('#lead-form').dataset.quiz = JSON.stringify(answers);
  }
  box.addEventListener('click', (event) => {
    const button = event.target.closest('.opts button');
    if (button) {
      answers[current] = button.dataset.v;
      if (current < steps.length) show(current + 1); else finish();
    }
    if (event.target.closest('.qback')) show(current - 1);
    if (event.target.closest('[data-qreset]')) {
      Object.keys(answers).forEach((key) => delete answers[key]);
      delete document.querySelector('#lead-form').dataset.quiz;
      document.querySelector('#lead-form [name="trips"]').value = '';
      show(1);
    }
  });
  show(1);
})();
