FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt .

# Виртуальная установка и очистка
RUN apk add --no-cache --virtual .build-deps \
    && pip install --no-cache-dir --compile -r requirements.txt \
    && apk del .build-deps

COPY . .

RUN python manage.py collectstatic --noinput

CMD ["/app/gunicorn.sh"]
