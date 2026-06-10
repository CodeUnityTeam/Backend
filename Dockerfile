FROM python:3.12-alpine

WORKDIR /app

# Копируем только файл с зависимостями
COPY requirements.txt .

# Устанавливаем системные и Python-зависимости
RUN apk add --no-cache --virtual .build-deps gcc musl-dev linux-headers \
    && pip install --no-cache-dir --compile -r requirements.txt \
    && apk del .build-deps

# Копируем исходный код проекта
COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]