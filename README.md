###### Backend
```bash
# Установка зависимостей через uv
> [Справка] (https://habr.com/ru/articles/875840)
```
```bash
pip install uv
uv pip install -r requirements.txt
# Или если uv уже установлен:
# uv pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

###### Запуск только базы данных для разработки

Если вы хотите работать с локальным Django-приложением, но использовать контейнеризованную базу данных:

1. Запустите только базу данных:
```bash
docker-compose -f docker-compose.db.yaml up -d
```

3. Проверьте статус контейнера:
```bash
docker-compose -f docker-compose.db.yaml ps
```

4. Настройте Django для подключения к базе данных:
   - Убедитесь, что в `config/settings.py` используются переменные окружения из `.env`
   - Выполните миграции:
```bash
python manage.py migrate
```

5. Остановка базы данных:
```bash
cd ../infra
docker-compose -f docker-compose.db.yaml down
```

> Примечание: Для работы с базой данных убедитесь, что порт 5432 свободен.

Здесь создано базовое приложение config для запуска.
Создать новое приложение можно команой django startapp <app_name>
 - Можно пойти через создание приложения api/ и писать там весь функционал бекенда.
 - Можно создавать отдельные приложения и работать в них.

Общая структура Django приложения (для пользоователей или вопросов или проектов):
```
<app_name>/
    __init__.py
    admin.py
    apps.py
    models.py
    serializers.py
    views.py
    selectors.py
    services.py
```

Основная идея в том, что мы выносим запросы отдельным файлом и добавляем во views.py
Бизнес-логику выносим в отдельный файл, например, services.py
Здесь происходит создание, валидация данных, отправка почты.
Ниже примеры:

selectors.py - отдельно для построения запросов, пример (здесь обработка запроса):
```
def collect_detail(id):
    """Получение детальной информации о сборе."""
    cache_data = cache_collect_detail(id)
    if cache_data is not None:
        return cache_data
    try:
        data = Collect.objects.select_related('author').prefetch_related(
            'payments__user').annotate(
            current_price=Coalesce(Sum('payments__amount'), 0),
            donators_count=Count('payments__user', distinct=True),
        ).get(id=id)
        cache_collect_detail(id, data)
        return data
    except Collect.DoesNotExist:
        raise Http404('Сбор не найден')
```

services.py - отдельно для логики приложения, пример (здесь сервис кеширует данные и отправляет почту):
```
@transaction.atomic
def collect_create(collect_data) -> Collect:
    """Создание нового сбора."""
    collect = Collect(**collect_data)
    collect.full_clean()
    collect.save()
    send_collect_created_email(collect)
    invalidate_collect_list_cache()
    return collect


@transaction.atomic
def payment_create(payment_data) -> Payment:
    """Создание нового пожертвования."""
    payment = Payment(**payment_data)
    payment.full_clean()
    payment.save()
    send_payment_created_email(payment)
    invalidate_collect_detail_cache(payment.collect.id)
    invalidate_collect_list_cache()
    return payment
```

views.py:
```
class CollectViewSet(ModelViewSet):
    """Создание сбора, список сборов, детальная информация."""

    http_method_names = ('post', 'get')

    def get_queryset(self):
        """Запрос к связным данным с вычислениями."""
        if self.action == 'retrieve':
            return collect_detail()  # используем selectors.py
        return collect_list()

    def get_serializer_class(self):
        """Выбор сериализатора."""
        if self.action == 'create':
            return CollectCreateSerializer
        if self.action == 'retrieve':
            return CollectDetailSerializer
        return CollectListSerializer

    def get_object(self):
        """Получение объекта."""
        return collect_detail(self.kwargs.get('pk'))

    def perform_create(self, serializer) -> None:
        """Создание сбора."""
        collect_data = serializer.validated_data
        collect_data['author'] = self.request.user
        collect_create(collect_data)  # используем services.py
        return collect_data
```
посмотреть можно тут:
https://github.com/HackSoftware/Django-Styleguide
