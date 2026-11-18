(() => {
  const form = document.querySelector('#lead-form');
  if (!form) return;
  const config = window.AEROTONE_LEADS || {};
  const fieldset = form.querySelector('fieldset');
  const status = form.querySelector('.form-status');
  const notice = document.querySelector('#lead-availability');
  const endpoint = config.endpoint;
  // Default is closed until the client supplies a receiving endpoint.
  if (!endpoint || (!endpoint.startsWith('/') && !endpoint.startsWith('https://'))) return;
  fieldset.disabled = false;
  notice.textContent = 'Заявка поступит в отдел продаж Аэротона.';
  let attempt = null;
  let busy = false;
  const reported = new Set();
  form.addEventListener('input', () => { status.textContent = ''; });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (busy || !form.reportValidity()) return;
    const values = Object.fromEntries(new FormData(form));
    const payload = {
      name: values.name.trim(), company: values.company.trim(), email: values.email.trim(),
      phone: values.phone.trim(), trips: values.trips, consent: values.consent === 'on',
      consent_version: config.consentVersion, website: values.website,
      page: location.origin + location.pathname,
      quiz: JSON.parse(form.dataset.quiz || '{}'),
      attribution: {},
    };
    // Read allowed attribution only for the submission, without browser storage.
    const query = new URLSearchParams(location.search);
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'yclid'].forEach((key) => {
      if (query.has(key)) payload.attribution[key] = query.get(key).slice(0, 300);
    });
    const snapshot = JSON.stringify(payload);
    if (!attempt || attempt.snapshot !== snapshot) {
      attempt = { snapshot, id: crypto.randomUUID() };
    }
    payload.request_id = attempt.id;
    busy = true;
    fieldset.disabled = true;
    status.textContent = 'Отправляем заявку…';
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(endpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload), signal: controller.signal, credentials: 'omit',
      });
      const result = await response.json();
      if (!response.ok || result.status !== 'created' || result.request_id !== attempt.id) {
        status.textContent = result.status === 'pending'
          ? 'Проверяем получение заявки. Повторите отправку с теми же данными или свяжитесь с нами по телефону.'
          : 'Отправка не подтверждена. Попробуйте ещё раз или свяжитесь с нами по телефону.';
        return;
      }
      status.textContent = 'Спасибо! Заявка поступила в отдел продаж. Мы свяжемся с вами.';
      // The analytics owner enables this callback only after valid analytics consent.
      if (!reported.has(attempt.id) && typeof window.aerotoneLeadConfirmed === 'function') {
        reported.add(attempt.id);
        try { window.aerotoneLeadConfirmed({ goal: 'lead_submit_success' }); } catch (_) { /* The lead remains accepted. */ }
      }
      form.reset();
      delete form.dataset.quiz;
      attempt = null;
    } catch (_) {
      status.textContent = 'Не удалось подтвердить отправку. Повторите с теми же данными или позвоните +7 (495) 445-00-77.';
    } finally {
      clearTimeout(timer);
      busy = false;
      fieldset.disabled = false;
    }
  });
})();
