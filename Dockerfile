FROM python:3.12-alpine

WORKDIR /app

COPY . .

RUN apk add --no-cache --virtual .build-deps \
    && pip install --no-cache-dir --compile -r requirements.txt \
    && apk del .build-deps

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]