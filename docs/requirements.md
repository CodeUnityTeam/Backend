## Зависимости

Проект использует **uv** — быстрый менеджер пакетов Python. [Справка](https://habr.com/ru/articles/875840)

### Установка uv

Если uv не установлен глобально:

```bash
pip install uv
```


### Инициализация проекта с uv

Проект уже содержит `pyproject.toml` с зависимостями. Для начала работы:

1. **Создание виртуального окружения** (если ещё не создано):

```bash
uv venv .venv --python 3.12
```

2. **Активация окружения**:

```bash
source .venv/bin/activate
```

3. **Установка зависимостей**:

```bash
uv pip install -e .
```

Или просто (uv автоматически использует виртуальное окружение):

```bash
uv sync --all-extras
```

### Управление зависимостями

- **Добавить новую зависимость**:

```bash
uv add package-name
```

- **Удалить зависимость**:

```bash
uv remove package-name
```

- **Обновить все зависимости**:

```bash
uv pip compile --upgrade
```

### Миграция с requirements.txt

Если вы ранее использовали `requirements.txt`, зависимости уже перенесены
в `pyproject.toml`. Вы можете продолжать использовать `requirements.txt`
для совместимости, но рекомендуется перейти на `pyproject.toml`.

Для генерации `requirements.txt` из `pyproject.toml`:

```bash
uv pip compile -o requirements.txt pyproject.toml
```

### Полезные команды uv

- `uv python` — запуск Python с активированным окружением
- `uv run` — запуск команды в виртуальном окружении
- `uv pip list` — список установленных пакетов
- `uv pip freeze` — вывод зависимостей в формате requirements
- `uv pip compile` — компиляция зависимостей с разрешением версий



[⬅ Назад на главную](../README.md)