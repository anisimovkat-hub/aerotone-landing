# Лендинг Аэротон

Код и история правок остаются в этом репозитории. Демонстрационный адрес — https://anisimovkat-hub.github.io/aerotone-landing/ . Целевой адрес клиента — https://b2b.aerotone.ru/ после подтверждения администратора. Новый домен покупать не нужно.

## Передача клиенту

Репозиторий публичный: для чтения, клонирования и **Code → Download ZIP** приглашение не требуется. Владельцем остаётся Катерина; пароль её GitHub передавать не нужно. Для совместных правок нужен GitHub-логин разработчика и отдельное приглашение после согласования прав.

**В web-root загружать только содержимое public/ собранного пакета.** Backend, .env, базы и внутренние файлы размещаются отдельно. [Полная инструкция](deployment/HANDOFF.md).

## Сборка без зависимостей

Python 3.9+, из корня клонированного репозитория:

```sh
python3 tools/build_release.py --site-url https://b2b.aerotone.ru --output dist/client-handoff
```

Получатся ZIP, SHA-256 и манифест версии. Endpoint по умолчанию пустой: ввод доступен, отправка честно сообщает, что заявка не передана.

Только после приёмки CRM и юридических текстов:

```sh
python3 tools/build_release.py --site-url https://b2b.aerotone.ru --endpoint /api/leads --forms-approved --output dist/client-handoff-connected
```

Папка вывода должна быть новой; сборщик не перезаписывает релизы. Для другого согласованного адреса заменить --site-url. Файл CNAME в GitHub Pages для этой схемы не нужен.

## Индексация

**Постоянно сохранять noindex, nofollow** в index.html и privacy.html. Robots.txt разрешает обход, чтобы поисковик прочитал noindex. Для Apache сборка включает .htaccess с X-Robots-Tag; для Nginx есть отдельный пример. Фактический заголовок проверяет администратор. Не включать лендинг в sitemap и не снимать запрет при запуске.

Noindex — указание поисковику, а не пароль. Публичный код GitHub остаётся доступен. Уже известные поиску URL удаляются после обработки запрета; при необходимости клиент использует инструменты удаления точных URL в Search Console и Вебмастере.

Первоисточники: [Google](https://developers.google.com/search/docs/crawling-indexing/block-indexing), [Яндекс](https://yandex.ru/support/webmaster/ru/controlling-robot/robots-txt).

## Правки и обновления

Редактировать исходники и фиксировать коммиты в GitHub. Workflow **Client handoff** проверяет и собирает пакет после изменений main и вручную. Actions → успешный запуск → Artifacts → client-handoff. Артефакт содержит готовый ZIP и SHA-256; он хранится 30 дней, а код остаётся в GitHub.

**Изменение GitHub не обновляет клиентский хостинг автоматически.** Администратор устанавливает новый пакет и сохраняет согласованную конфигурацию формы. Для автодоставки нужны данные хостинга, разрешённый способ подключения и отдельное согласование. Сейчас она не подключена.

```sh
python3 -m unittest discover -s integration -p 'test_*.py' -v
python3 -m unittest discover -s tools -p 'test_*.py' -v
```

Проверки подменяют amoCRM, реальных лидов не создают. Финальная приёмка — по [HANDOFF](deployment/HANDOFF.md) и [ТЗ интеграции](integration/README.md).
