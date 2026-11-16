// Класс js ставится здесь, а не в <head>: если скрипт не загрузится, текст останется видимым.
document.documentElement.classList.add('js');

const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));

// Форма макета: заявка никуда не отправляется.
const form = document.querySelector('#lead-form');
const status = form.querySelector('.form-status');
form.addEventListener('submit', (event) => {
  event.preventDefault();
  status.textContent = 'Поля заполнены. Это проверка макета, заявка не отправлена.';
});
form.addEventListener('input', () => { status.textContent = ''; });
form.querySelector('fieldset').disabled = false;

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

// ===== Мини-квиз: шесть вопросов и оценка выгоды. Данные никуда не отправляются. =====
// ВСЕ допущения собраны здесь. Цены и проценты — ориентировочные, их нужно подтвердить у клиента (см. 09).
const QUIZ = {
  // Экономия: до 30% на отелях (спецтарифы; заявляют Аэротон и конкуренты), до 5% на билетах (моя оценка, подтвердить).
  savingHotel: 0.30,
  savingTransport: 0.05,
  lowFactor: 0.5,                                                   // нижняя граница диапазона = половина верхней
  // Цены, ₽. Перелёт: GATE, январь–август 2026, эконом по России ≈ 18,1 тыс. в одну сторону → туда-обратно ≈ 36 тыс.; ж/д дешевле, поэтому в среднем 30 тыс.
  transport: { ru: 30000, cis: 40000, world: 80000, mix: 45000 },   // дорога туда-обратно (СНГ и дальнее зарубежье — оценка)
  // Ночь в отеле: «Ракета», зима 2025–2026 — 8 076 ₽; Bronevik, осень 2026, по России в среднем 6,2 тыс. ₽
  hotelNight: { ru: 7000, cis: 7500, world: 13000, mix: 9000 },
  nights: { short: 1, mid: 3, long: 6 },
  shareByHow: { self: 1, office: 0.8, agency: 0.5, platform: 0.4 },   // какая часть максимума реальна при текущем способе оформления (оценка)
  shareByRules: { none: 1, manual: 0.75, auto: 0.5 },                 // и при текущем контроле расходов (оценка)
  minutesNow: { self: 90, office: 60, agency: 30, platform: 20 },     // минут на оформление одной поездки сейчас (оценка)
  minutesDocs: { manual: 40, part: 20, edo: 5 },                      // минут на документы одной поездки (оценка)
  minutesRules: { none: 0, manual: 15, auto: 0 },                     // минут на ручную проверку лимитов (оценка)
  minutesWith: 15,                                                    // минут с Аэротоном (оценка)
  formValue: { 2: 'q1', 7: 'q2', 20: 'q3', 40: 'q4' },
};
(() => {
  const box = document.querySelector('.quiz-box');
  if (!box) return;
  const steps = [...box.querySelectorAll('.qstep')];
  const total = steps.length;
  const result = box.querySelector('.qresult');
  const back = box.querySelector('.qback');
  const bar = box.querySelector('.quiz-progress i');
  const ans = {};
  let cur = 1;
  const show = (n) => {
    cur = n;
    steps.forEach((s) => { s.hidden = Number(s.dataset.q) !== n; });
    result.hidden = n !== 'done';
    box.dataset.step = String(n);
    bar.style.width = (n === 'done' ? 100 : Math.round((n / total) * 100 - 8)) + '%';
    back.hidden = n === 1 || n === 'done';
  };
  const fmtInt = (n) => Math.round(n).toLocaleString('ru-RU');
  const money = (n) => {
    const r = Math.round(n / 10000) * 10000;
    return r >= 1000000 ? (r / 1000000).toFixed(1).replace('.', ',') + ' млн' : fmtInt(r / 1000) + ' тыс.';
  };
  const countTo = (el, to) => {
    if (reduced) { el.textContent = fmtInt(to); return; }
    const t0 = performance.now();
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / 900);
      el.textContent = fmtInt(to * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  const finish = () => {
    const trips = Number(ans[1]);
    const tripsYear = trips * 12;
    const transportYear = tripsYear * QUIZ.transport[ans[2]];
    const hotelYear = tripsYear * QUIZ.hotelNight[ans[2]] * QUIZ.nights[ans[3]];
    const spendYear = transportYear + hotelYear;
    const share = QUIZ.shareByHow[ans[4]] * QUIZ.shareByRules[ans[6]];
    const high = (hotelYear * QUIZ.savingHotel + transportYear * QUIZ.savingTransport) * share;
    const low = high * QUIZ.lowFactor;
    const nowMin = QUIZ.minutesNow[ans[4]] + QUIZ.minutesDocs[ans[5]] + QUIZ.minutesRules[ans[6]];
    const hours = Math.round((trips * 12 * Math.max(0, nowMin - QUIZ.minutesWith)) / 60);
    show('done');
    result.querySelector('.qr-ctx').textContent = 'Ваши поездки — примерно ' + fmtInt(trips * 12) + ' в год на ' + money(spendYear) + ' ₽ по средним рыночным ценам.';
    result.querySelector('[data-out="money"]').textContent = 'от ' + money(low) + ' до ' + money(high);
    countTo(result.querySelector('[data-out="hours"]'), hours);
    const v = result.querySelector('.qr-verdict');
    if (trips <= 3 && (ans[4] === 'agency' || ans[4] === 'platform') && ans[5] === 'edo' && ans[6] === 'auto') {
      v.textContent = 'У вас всё уже налажено, и поездок немного — возможно, вам удобнее продолжить как сейчас. Платформа бесплатная, поэтому можно подключить её «про запас».';
    } else if (ans[5] !== 'edo') {
      v.textContent = 'Больше всего времени уходит на бумаги. Документы по ЭДО, сводные счета и персональный бухгалтер уберут эту рутину.';
    } else if (ans[6] === 'none') {
      v.textContent = 'Без правил расходы трудно контролировать. Лимиты в платформе не дадут сотруднику забронировать лишнее.';
    } else {
      v.textContent = 'Платформа бесплатная и подойдёт вам: все поездки в одном окне, свои правила и лимиты, поддержка 24/7.';
    }
    document.querySelector('#lead-form [name="trips"]').value = QUIZ.formValue[trips] || '';
  };
  box.addEventListener('click', (e) => {
    const b = e.target.closest('.opts button');
    if (b) {
      ans[cur] = b.dataset.v;
      if (cur < total) show(cur + 1); else finish();
      return;
    }
    if (e.target.closest('.qback')) show(cur - 1);
    if (e.target.closest('[data-qreset]')) show(1);
  });
  show(1);
})();
