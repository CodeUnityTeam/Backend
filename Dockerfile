FROM python:3.12-alpine

WORKDIR /app

# TODO: Разделить COPY для использования кеша слоёв Docker.
#   Сейчас COPY . . выполняется до pip install — при любом изменении кода
#   переустанавливаются все зависимости. Нужно копировать requirements.txt
#   отдельно, устанавливать зависимости, затем копировать остальной код.
COPY . .

RUN apk add --no-cache --virtual .build-deps \
    && pip install --no-cache-dir --compile -r requirements.txt \
    && apk del .build-deps

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]