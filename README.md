# CodeUnity  ![](/docs/logo-BGBMxMPc.svg)

Проект для связи разработчиков и авторов проектов.

Здесь разработчики смогут найти для себя проекты, соответствующие их навыкам, участие в которых поможет получить 
необходимый опыт, а авторы проектов смогут собрать себе команду для реализации своих идей. Также на этом проекте есть 
раздел Q&A, где каждый сможет задать вопрос по интересующим его навыкам и темам и получить ответы и комментарии от коллег. 
Подробнее о возможностях сервиса можно узнать по ссылкам разделов ниже.

Backend проекта реализован как RESTful API на Django/DRF, использованы библиотеки и инструменты:
  * df-rest-auth - авторизация, включая авторизацию по протоколу OAuth2
  * psycopg - для работы с PostgreSQL
  * django-redis и celery - для кеширования и настройки фоновых задач
  * django-storages - для хранения файлов в хранилище MinIO
  * drf-spectacular - для документирования API
  * Docker - для контейниризации бэкенда и инфраструктуры
  * GitHub Action - для настройки CI/CD
  * Другие вспомогательные Django библиотеки


### Команда backend
<table>
  <thead>
    <tr>
      <th>Имя</th>
      <th>GitHub</th>
      <th>Telegram</th>
    </tr>
  </thead>
  <tbody>
    <!-- Секция TeamLead -->
    <tr>
      <td colspan="3" style="font-weight: bold; text-align: center;">TeamLead</td>
    </tr>
    <tr>
      <td>Станислав Баринов</td>
      <td><a href="https://github.com/hixwizard">https://github.com/hixwizard</a></td>
      <td>@hixhello</td>
    </tr>
    <!-- Секция Developers -->
    <tr>
      <td colspan="3" style="font-weight: bold; text-align: center;">Developers</td>
    </tr>
    <tr>
      <td>Олег Мисхожев</td>
      <td><a href="https://github.com/OlegMiskhozhev">https://github.com/OlegMiskhozhev</a></td>
      <td>@miskhozhev</td>
    </tr>
    <tr>
      <td>Кристина Невская</td>
      <td><a href="https://github.com/Enigmatica33">https://github.com/Enigmatica33</a></td>
      <td>@enigmatica33</td>
    </tr>
    <tr>
      <td>Вячеслав Шипов</td>
      <td><a href="https://github.com/clsvood">https://github.com/clsvood</a></td>
      <td>@clsvood</td>
    </tr>
    <tr>
      <td>Максим Числавский</td>
      <td><a href="https://github.com/MaksimChislavskiy">https://github.com/MaksimChislavskiy</a></td>
      <td>@M_75_x</td>
    </tr>
    <tr>
      <td>Евгений Цыганков</td>
      <td><a href="https://github.com/EvgeniyTsygankov">https://github.com/EvgeniyTsygankov</a></td>
      <td>@tsygankov_eg</td>
    </tr>
    <tr>
      <td>Наташа Хуснутдинова</td>
      <td><a href="https://github.com/natixdev">https://github.com/natixdev</a></td>
      <td>@natix_dev</td>
    </tr>
    <tr>
      <td>Надежда Малюхина</td>
      <td><a href="https://github.com/nadyamalyuhina">https://github.com/nadyamalyuhina</a></td>
      <td>@hope_build</td>
    </tr>
    <tr>
      <td>Александр Быстров</td>
      <td><a href="https://github.com/Aleksandr-Bystrov">https://github.com/Aleksandr-Bystrov</a></td>
      <td>@km00_1</td>
    </tr>
  </tbody>
</table>

### Backend

* [Зависимости](docs/requirements.md)
* [Запуск проекта](docs/start.md)
* [Разработка](docs/development.md)
* [Авторизация](docs/auth.md)
* [Наполнение БД](docs/add_tags.md)
* [Docker](docs/docker.md)
* [Admin-панель](docs/admin.md)
* [Nginx](docs/nginx.md)

### Разделы
* [👤 Пользователи и профили](docs/users.md)
* [📁 Проекты](docs/projects.md)
* [❓ Вопросы и ответы (Q&A)](docs/qna.md)
* [☁️ Хранилище S3 Minio](docs/s3_minio.md)
* [⚡ Кэширование](docs/caching.md)
* [📄 Документы](docs/documents.md)
* [🛡️ Блокировка стоп-слов](docs/bad_words.md)

### Дополнительные ресурсы

- [Документация uv](https://docs.astral.sh/uv/)
- [Документация Django](https://docs.djangoproject.com/)
- [Документация Django REST Framework](https://www.django-rest-framework.org/)
