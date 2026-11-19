(() => {
  const config = window.AEROTONE_LEADS || {};
  document.querySelectorAll('[data-lead-form]').forEach((form) => {
    const fieldset = form.querySelector('fieldset');
    const status = form.querySelector('.form-status');
    const endpoint = config.endpoint;
    const connected = Boolean(endpoint && (endpoint.startsWith('/') && !endpoint.startsWith('//') || endpoint.startsWith('https://')));
    const phone = form.querySelector('[name="phone"]');
    const email = form.querySelector('[name="email"]');
    function validateContacts() {
      const rawPhone = phone.value.trim();
      let digits = rawPhone.replace(/\D/g, '');
      if (digits.length === 10 && digits.startsWith('9')) digits = '7' + digits;
      if (digits.length === 11 && digits.startsWith('8') && !rawPhone.startsWith('+')) digits = '7' + digits.slice(1);
      const russian = digits.startsWith('7');
      const phoneValid = /^[+]?[0-9 ()-]+$/.test(rawPhone) &&
        (russian ? digits.length === 11 : rawPhone.startsWith('+') && /^[1-9][0-9]{7,14}$/.test(digits)) &&
        !/^([0-9])\1+$/.test(digits.slice(1)) && !['1234567890', '12345678901', '9876543210'].includes(digits);
      phone.setCustomValidity(rawPhone && !phoneValid
        ? 'Проверьте номер. Для России — 11 цифр с 7 или 8, для других стран — номер с + и кодом страны.' : '');
      const address = email.value.trim();
      const parts = address.split('@');
      const local = parts[0] || '';
      const domain = parts[1] || '';
      const labels = domain.split('.');
      const emailValid = parts.length === 2 && local.length <= 64 && address.length <= 254 &&
        /^[a-z0-9!#$%&'*+/=?^_\x60{|}~.-]+$/i.test(local) && !local.startsWith('.') && !local.endsWith('.') && !local.includes('..') &&
        labels.length >= 2 && labels.every((label) => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i.test(label)) &&
        /^(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})$/i.test(labels.at(-1)) &&
        !['invalid', 'test', 'localhost'].includes(labels.at(-1).toLowerCase());
      email.setCustomValidity(address && !emailValid ? 'Введите почту в формате name@company.ru. Проверьте имя и домен.' : '');
      return '+' + digits;
    }
    phone.addEventListener('blur', () => {
      const normalized = validateContacts();
      if (phone.value && phone.validity.valid) phone.value = normalized;
    });
    email.addEventListener('blur', () => { email.value = email.value.trim(); validateContacts(); });
    let attempt = null;
    let busy = false;
    const reported = new Set();
    form.addEventListener('input', () => { status.textContent = ''; validateContacts(); });
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      validateContacts();
      if (busy || !form.reportValidity()) return;
      if (!connected) {
        status.textContent = 'Онлайн-отправка пока недоступна. Заявка не передана. Позвоните +7 (495) 445-00-77 или напишите info@aerotone.ru.';
        return;
      }
      phone.value = validateContacts();
      const values = Object.fromEntries(new FormData(form));
      const payload = {
        form_type: form.dataset.leadForm,
        name: (values.name || '').trim(), company: (values.company || '').trim(), email: values.email.trim(),
        phone: values.phone.trim(), consent: values.consent === 'on',
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
        attempt = null;
      } catch (_) {
        status.textContent = 'Не удалось подтвердить отправку. Повторите с теми же данными или позвоните +7 (495) 445-00-77.';
      } finally {
        clearTimeout(timer);
        busy = false;
        fieldset.disabled = false;
      }
    });
    // Enable entry only after the submit handler is installed.
    fieldset.disabled = false;
  });
})();
