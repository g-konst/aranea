[![python_version](https://img.shields.io/badge/python-3.12+-brightgreen.svg?logo=Python&logoColor=white)](https://www.python.org/)

# Aranea

**Aranea** — это распределённый фреймворк для парсинга веб-страниц с управляемыми браузерами-воркерами. Он позволяет запускать, управлять и масштабировать парсинг через API или дашборд.

## Возможности

- Управляемые браузеры-воркеры через gRPC.
- REST API для парсинга страниц, запуска и остановки воркеров.
- Встроенный дашборд для мониторинга состояния.
- Гибкое взаимодействие с воркерами — создание, удаление, балансировка.
- Поддержка прокси, кук, кастомных заголовков, действий и блокировки ресурсов.

---

## Установка и запуск

1. Клонируй репозиторий:

```bash
git clone https://github.com/g-konst/aranea.git
cd aranea
```

2. Установи зависимости:

```bash
pip install -r requirements.txt
```

3. Запусти сервер:

```bash
make server
```

## Примеры запросов

- Запуск воркера

```
POST /spawn

{
  "message": "Worker worker-0 spawned on port 50051"
}

```

- Парсинг страницы

```
POST /parse
Content-Type: application/json

{
  "url": "https://example.com",
  "proxy": "http://proxy:3128",
  "timeout": 10000,
  "headers": { "User-Agent": "Custom" },
  "load": "networkidle",
  "actions": [
    { "func": "click", "args": [{ "name": "selector", "string_value": "#login" }] }
  ]
}

{
  "status": 200,
  "content": "<html>...</html>",
  "cookies": [...],
  "headers": {...},
  "error": ""
}
```

- Просмотр состояния воркеров

```
GET /workers

{
  "workers": [
    {
      "id": "worker-0",
      "host": "localhost",
      "port": 50051,
      "status": 0,
      "last_report": "2025-01-01T00:00:01.000000",
      "active_pages": 0,
      "cpu_usage": 6.9,
      "memory_usage": 4.5
    }
  ]
}
```

- Удаление воркера

```
DELETE /worker/worker-0

{
  "worker_id": "worker-0", "status": "terminated"
}

```

## Поддержка проекта

Если тебе нравится этот проект, ты можешь:

- ⭐ Поставить звезду на GitHub.
- 🤝 Присоединиться к разработке.
- 💸 Поддержать материально:

### Быстрая оплата

[![SberPay](https://img.shields.io/badge/SberPay-через_Сбербанк-green?style=for-the-badge&logo=sberbank)](https://bit.ly/4d7t8PY)

### Криптовалюты

| Валюта | Адрес |
|--------|-------|
| ![BTC](https://img.shields.io/badge/BTC-Bitcoin-orange?style=for-the-badge&logo=bitcoin&logoColor=white) | `bc1q2jzh8uxy7x7fnztmuepne4vth7ntargh39x4n3` |
| ![ETH](https://img.shields.io/badge/ETH-Ethereum-5c6bc0?style=for-the-badge&logo=ethereum&logoColor=white) | `0xeA1b4C1d72Be6B5e828e6d58950b2A00Aaa97faD` |
| ![TON](https://img.shields.io/badge/TON-Toncoin-0098ea?style=for-the-badge&logo=telegram&logoColor=white) | `UQAQm_merCLgE0-JvJAmX6nLIeNSVf5EyIWpCadWjnXJGzLl` |
| ![USDT](https://img.shields.io/badge/USDT-TRC20-26a17b?style=for-the-badge&logo=tether&logoColor=white) | `TYswHByP7yFUqJ7WMcEk2thihN4AMNhWDH` |


## Лицензия

Проект лицензирован под [GNU AGPLv3](./LICENSE).

```
Copyright (C) 2025 Konstantin Grudnitskiy
<k.grudnitskiy@yandex.ru>
```

## Связь

По всем вопросам, багам и предложениям — открывай `issue` или пиши на [почту](mailto:k.grudnitskiy@yandex.ru)

## TODO

- [ ] Документация по gRPC API
- [ ] Авторизация для доступа к API
- [ ] Перезапуск упавших воркеров
- [ ] Dockerfile
- [ ] CI/CD пайплайн
