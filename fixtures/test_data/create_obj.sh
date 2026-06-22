#!/bin/bash

# =============================================================================
# Скрипт для создания тестовых данных:
#   1. Логин и получение JWT-токена (Stanislav)
#   2. Обновление профиля данными из user_path.json
#   3. Загрузка аватара
#   4. Создание всех проектов из projects.json
#   5. Создание вопросов из questions.json
#   6. Создание ответов на вопросы (2 пользователями)
#   7. Логин остальных пользователей (Kristina, Evgeniy, Natalya)
#   8. Отклики на проекты
#   9. Приглашения от Stanislav
#  10. Лайки проектов
#  11. Лайки вопросов
#
# Запускать из корня проекта:
#   bash fixtures/test_data/create_obj_local.sh
# =============================================================================

# Конфигурация
BASE_URL="${BASE_URL:-http://127.0.0.1:8000/api/v1}"
PASSWORD="user887089"
EMAIL="stanislav_b@example.com"
EMAIL2="oleg_m@example.com"
EMAIL3="kristina@example.com"
EMAIL4="evgeniy@example.com"
EMAIL5="natalya@example.com"

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Путь к папке с JSON-файлами (относительно корня проекта)
DATA_DIR="fixtures/test_data"

# Временный файл
TEMP_JSON="$DATA_DIR/temp_project_data.json"

echo "=============================================="
echo " Создание тестовых данных"
echo "=============================================="
echo ""

# =============================================================================
# Функция: подтверждение email через API
# =============================================================================
confirm_email() {
  local email=$1

  # Подтверждаем email напрямую через manage.py shell
  # (allauth 65+ использует HMAC-ключи, которые не хранятся в БД)
  local result
  result=$(uv run python manage.py shell -c "
from allauth.account.models import EmailAddress
try:
    ea = EmailAddress.objects.get(email='$email')
    ea.verified = True
    ea.save()
    print('OK')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1)

  if [ "$result" = "OK" ]; then
    echo -e "${GREEN}  ✓ Email подтверждён ($email)${NC}"
    return 0
  else
    echo -e "${RED}  ✗ Ошибка подтверждения email: $result${NC}"
    return 1
  fi
}

# =============================================================================
# Функция: логин и получение токена
# =============================================================================
login() {
  local email=$1
  local password=$2

  login_data=$(cat <<EOF
{
  "email": "$email",
  "password": "$password"
}
EOF
)

  login_response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/user/auth/login/" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d "$login_data")

  login_code=$(echo "$login_response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
  login_body=$(echo "$login_response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")

  if [ "$login_code" -eq 200 ]; then
    echo "$login_body" | python -c "import sys,json; print(json.load(sys.stdin)['access'])"
    return 0
  else
    echo ""
    return 1
  fi
}

# =============================================================================
# Функция: POST-запрос с JSON-телом
# =============================================================================
api_post_json() {
  local url=$1
  local token=$2
  local json_body=$3

  response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$url" \
    -H "Content-Type: application/json; charset=utf-8" \
    -H "Authorization: Bearer $token" \
    -d "$json_body")

  code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
  body=$(echo "$response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")

  echo "$code|$body"
}

# =============================================================================
# Функция: POST-запрос без тела (для эндпоинтов, где data={})
# =============================================================================
api_post_empty() {
  local url=$1
  local token=$2

  response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$url" \
    -H "Authorization: Bearer $token")

  code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
  body=$(echo "$response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")

  echo "$code|$body"
}

# =============================================================================
# Шаг 1: Логин и получение JWT-токена (Stanislav)
# =============================================================================
echo -e "${YELLOW}[1/11] Логин и получение JWT-токена...${NC}"

# Подтверждаем email перед логином
echo "  Подтверждение email для Stanislav..."
confirm_email "$EMAIL"

access_token=$(login "$EMAIL" "$PASSWORD")
if [ -n "$access_token" ]; then
  echo -e "${GREEN}  ✓ Логин успешен (Stanislav)${NC}"
else
  echo -e "${RED}  ✗ Ошибка логина${NC}"
  exit 1
fi

echo ""

# =============================================================================
# Шаг 2: Обновление профиля данными из user_path.json
# =============================================================================
echo -e "${YELLOW}[2/11] Обновление профиля пользователя...${NC}"

profile_response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X PATCH "$BASE_URL/user/profile/me/" \
  -H "Content-Type: application/json; charset=utf-8" \
  -H "Authorization: Bearer $access_token" \
  --data-binary "@$DATA_DIR/user_path.json")

profile_code=$(echo "$profile_response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
profile_body=$(echo "$profile_response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")

if [ "$profile_code" -eq 200 ]; then
  echo -e "${GREEN}  ✓ Профиль обновлён${NC}"
else
  echo -e "${RED}  ✗ Ошибка обновления профиля (HTTP $profile_code): $profile_body${NC}"
  exit 1
fi

echo ""

# =============================================================================
# Шаг 2.1: Загрузка аватара
# =============================================================================
echo -e "${YELLOW}[2.1/10] Загрузка аватара...${NC}"

AVATAR_FILE="$DATA_DIR/test_avatar.jpg"

if [ -f "$AVATAR_FILE" ]; then
  avatar_response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/user/profile/me/avatar/" \
    -H "Authorization: Bearer $access_token" \
    -F "file=@$AVATAR_FILE")

  avatar_code=$(echo "$avatar_response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
  avatar_body=$(echo "$avatar_response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")

  if [ "$avatar_code" -eq 201 ]; then
    avatar_url=$(echo "$avatar_body" | python -c "import sys,json; print(json.load(sys.stdin).get('avatar_url', 'unknown'))")
    echo -e "${GREEN}  ✓ Аватар загружен: $avatar_url${NC}"
  else
    echo -e "${RED}  ✗ Ошибка загрузки аватара (HTTP $avatar_code): $avatar_body${NC}"
  fi
else
  echo -e "${YELLOW}  ⚠ Файл аватара не найден: $AVATAR_FILE${NC}"
fi

echo ""

# =============================================================================
# Шаг 4: Создание проектов из projects.json
# =============================================================================
echo -e "${YELLOW}[4/11] Создание проектов...${NC}"

projects_count=$(python -c "
import json, os
data_dir = 'fixtures/test_data'
projects_file = os.path.join(data_dir, 'projects.json')
with open(projects_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
print(len(data))
")

echo "  Всего проектов для создания: $projects_count"
echo ""

# Массив для хранения ID созданных проектов
project_ids=()

for i in $(seq 0 $((projects_count - 1))); do
  python -c "
import json, os
data_dir = 'fixtures/test_data'
projects_file = os.path.join(data_dir, 'projects.json')
with open(projects_file, 'r', encoding='utf-8') as f:
    projects = json.load(f)
project = projects[$i]
with open(os.path.join(data_dir, 'temp_project_data.json'), 'w', encoding='utf-8') as f:
    json.dump(project, f, ensure_ascii=False)
"

  project_title=$(python -c "
import json, os, sys
data_dir = 'fixtures/test_data'
with open(os.path.join(data_dir, 'temp_project_data.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)
title = data.get('title', 'Без названия')
sys.stdout.buffer.write(title.encode('utf-8'))
")

  echo "  Создание проекта $((i + 1)): $project_title"

  project_response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/projects/" \
    -H "Content-Type: application/json; charset=utf-8" \
    -H "Authorization: Bearer $access_token" \
    --data-binary "@$TEMP_JSON")

  project_code=$(echo "$project_response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
  project_body=$(echo "$project_response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")

  if [ "$project_code" -eq 201 ]; then
    project_id=$(echo "$project_body" | python -c "import sys,json; print(json.load(sys.stdin).get('project_id', 'unknown'))")
    project_ids+=("$project_id")
    echo -e "${GREEN}    ✓ Создан project_id: $project_id${NC}"
  else
    echo -e "${RED}    ✗ Ошибка (HTTP $project_code): $project_body${NC}"
  fi

  echo ""
  sleep 1
done

# =============================================================================
# Шаг 5: Создание вопросов из questions.json
# =============================================================================
echo -e "${YELLOW}[5/11] Создание вопросов Q&A...${NC}"

questions_count=$(python -c "
import json, os
data_dir = 'fixtures/test_data'
questions_file = os.path.join(data_dir, 'questions.json')
with open(questions_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
print(len(data))
")

echo "  Всего вопросов для создания: $questions_count"
echo ""

# Массив для хранения ID созданных вопросов
question_ids=()

for i in $(seq 0 $((questions_count - 1))); do
  python -c "
import json, os
data_dir = 'fixtures/test_data'
questions_file = os.path.join(data_dir, 'questions.json')
with open(questions_file, 'r', encoding='utf-8') as f:
    questions = json.load(f)
question = questions[$i]
with open(os.path.join(data_dir, 'temp_project_data.json'), 'w', encoding='utf-8') as f:
    json.dump(question, f, ensure_ascii=False)
"

  question_title=$(python -c "
import json, os, sys
data_dir = 'fixtures/test_data'
with open(os.path.join(data_dir, 'temp_project_data.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)
title = data.get('title', 'Без названия')
sys.stdout.buffer.write(title.encode('utf-8'))
")

  echo "  Создание вопроса $((i + 1)): $question_title"

  question_response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/qna/questions/" \
    -H "Content-Type: application/json; charset=utf-8" \
    -H "Authorization: Bearer $access_token" \
    --data-binary "@$TEMP_JSON")

  question_code=$(echo "$question_response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
  question_body=$(echo "$question_response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")

  if [ "$question_code" -eq 201 ]; then
    qid=$(echo "$question_body" | python -c "import sys,json; print(json.load(sys.stdin).get('question_id', 'unknown'))")
    question_ids+=("$qid")
    echo -e "${GREEN}    ✓ Создан question_id: $qid${NC}"
  else
    echo -e "${RED}    ✗ Ошибка (HTTP $question_code): $question_body${NC}"
  fi

  echo ""
  sleep 1
done

# =============================================================================
# Шаг 5: Создание ответов на вопросы (двумя пользователями)
# =============================================================================
echo -e "${YELLOW}[6/11] Создание ответов на вопросы...${NC}"

# Логинимся как второй пользователь (Oleg)
echo "  Логин второго пользователя (Oleg)..."
echo "  Подтверждение email для Oleg..."
confirm_email "$EMAIL2"
access_token2=$(login "$EMAIL2" "$PASSWORD")
if [ -n "$access_token2" ]; then
  echo -e "${GREEN}  ✓ Логин успешен (Oleg)${NC}"
else
  echo -e "${RED}  ✗ Ошибка логина Oleg${NC}"
  exit 1
fi

echo ""

# Читаем ответы из JSON
answers_count=$(python -c "
import json, os
data_dir = 'fixtures/test_data'
answers_file = os.path.join(data_dir, 'answers.json')
with open(answers_file, 'r', encoding='utf-8') as f:
    data = json.load(f)
print(len(data))
")

echo "  Всего ответов для создания: $answers_count"
echo ""

# Массив для хранения ID созданных ответов
answer_ids=()

# Создаём ответы: первые 3 от Stanislav, последние 2 от Oleg
for i in $(seq 0 $((answers_count - 1))); do
  # Определяем, какой токен использовать
  if [ "$i" -lt 3 ]; then
    current_token=$access_token
    author="Stanislav"
  else
    current_token=$access_token2
    author="Oleg"
  fi

  # Берём вопрос по циклу (если вопросов меньше, чем ответов)
  q_index=$((i % ${#question_ids[@]}))
  qid="${question_ids[$q_index]}"

  # Извлекаем данные ответа
  python -c "
import json, os
data_dir = 'fixtures/test_data'
answers_file = os.path.join(data_dir, 'answers.json')
with open(answers_file, 'r', encoding='utf-8') as f:
    answers = json.load(f)
answer = answers[$i]
with open(os.path.join(data_dir, 'temp_project_data.json'), 'w', encoding='utf-8') as f:
    json.dump(answer, f, ensure_ascii=False)
"

  answer_content=$(python -c "
import json, os, sys
data_dir = 'fixtures/test_data'
with open(os.path.join(data_dir, 'temp_project_data.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)
content = data.get('content', '')
sys.stdout.buffer.write(content.encode('utf-8'))
")

  echo "  Создание ответа $((i + 1)) (от $author): ${answer_content:0:50}..."

  answer_response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/qna/questions/$qid/answers/" \
    -H "Content-Type: application/json; charset=utf-8" \
    -H "Authorization: Bearer $current_token" \
    --data-binary "@$TEMP_JSON")

  answer_code=$(echo "$answer_response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
  answer_body=$(echo "$answer_response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")

  if [ "$answer_code" -eq 201 ]; then
    answer_id=$(echo "$answer_body" | python -c "import sys,json; print(json.load(sys.stdin).get('answer_id', 'unknown'))")
    answer_ids+=("$answer_id")
    echo -e "${GREEN}    ✓ Создан answer_id: $answer_id${NC}"
  else
    echo -e "${RED}    ✗ Ошибка (HTTP $answer_code): $answer_body${NC}"
  fi

  echo ""
  sleep 1
done

# =============================================================================
# Шаг 7: Логин остальных пользователей (Kristina, Evgeniy, Natalya)
# =============================================================================
echo -e "${YELLOW}[7/11] Логин остальных пользователей...${NC}"

echo "  Подтверждение email для Kristina..."
confirm_email "$EMAIL3"
access_token3=$(login "$EMAIL3" "$PASSWORD")
if [ -n "$access_token3" ]; then
  echo -e "${GREEN}  ✓ Логин успешен (Kristina)${NC}"
else
  echo -e "${RED}  ✗ Ошибка логина Kristina${NC}"
  exit 1
fi

echo "  Подтверждение email для Evgeniy..."
confirm_email "$EMAIL4"
access_token4=$(login "$EMAIL4" "$PASSWORD")
if [ -n "$access_token4" ]; then
  echo -e "${GREEN}  ✓ Логин успешен (Evgeniy)${NC}"
else
  echo -e "${RED}  ✗ Ошибка логина Evgeniy${NC}"
  exit 1
fi

echo "  Подтверждение email для Natalya..."
confirm_email "$EMAIL5"
access_token5=$(login "$EMAIL5" "$PASSWORD")
if [ -n "$access_token5" ]; then
  echo -e "${GREEN}  ✓ Логин успешен (Natalya)${NC}"
else
  echo -e "${RED}  ✗ Ошибка логина Natalya${NC}"
  exit 1
fi

echo ""

# =============================================================================
# Шаг 8: Отклики на проекты
#   - Kristina откликается на проект #2 (Kristina фитнесс приложение) — published
#   - Evgeniy откликается на проект #4 (Хитрый Евгений) — published
#   - Natalya откликается на проект #5 (Сервис книг от Натальи) — published
#   - Oleg откликается на проект #7 (DevOps Infrastructure Automation) — published
#
# Эндпоинт: POST /api/v1/projects/{project_id}/responses/
# В сериализаторе data={}, поэтому тело не нужно
# =============================================================================
echo -e "${YELLOW}[8/11] Отклики на проекты...${NC}"

# project_ids: [0]=OlegCo, [1]=Kristina, [2]=Маркетплейс, [3]=Хитрый Евгений,
#               [4]=Сервис книг, [5]=E-Commerce, [6]=DevOps

echo "  Отклик от Kristina на проект ${project_ids[1]}..."
result=$(api_post_empty "$BASE_URL/projects/${project_ids[1]}/responses/" "$access_token3")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 201 ]; then
  echo -e "${GREEN}    ✓ Отклик создан${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

echo "  Отклик от Evgeniy на проект ${project_ids[3]}..."
result=$(api_post_empty "$BASE_URL/projects/${project_ids[3]}/responses/" "$access_token4")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 201 ]; then
  echo -e "${GREEN}    ✓ Отклик создан${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

echo "  Отклик от Natalya на проект ${project_ids[4]}..."
result=$(api_post_empty "$BASE_URL/projects/${project_ids[4]}/responses/" "$access_token5")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 201 ]; then
  echo -e "${GREEN}    ✓ Отклик создан${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

echo "  Отклик от Oleg на проект ${project_ids[6]}..."
result=$(api_post_empty "$BASE_URL/projects/${project_ids[6]}/responses/" "$access_token2")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 201 ]; then
  echo -e "${GREEN}    ✓ Отклик создан${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

# =============================================================================
# Шаг 9: Приглашения от Stanislav
#   - Приглашает Kristina в проект #1 (OlegCo обучение с нуля) — draft
#   - Приглашает Evgeniy в проект #3 (Маркетплейс BarinoV) — draft
#
# Эндпоинт: POST /api/v1/projects/{project_id}/invite/{user_id}/
# В сериализаторе data={}, но нужно передать пустой JSON {}
# =============================================================================
echo -e "${YELLOW}[9/11] Приглашения от Stanislav...${NC}"

# Получаем user_id пользователей через GET /api/v1/user/profile/me/
# В ответе поле называется 'pk' (см. CustomUserDetailsSerializer.Meta.fields)
get_user_id() {
  local token=$1
  local response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "$BASE_URL/user/profile/me/" \
    -H "Authorization: Bearer $token")
  local body=$(echo "$response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")
  echo "$body" | python -c "import sys,json; print(json.load(sys.stdin).get('pk', 'unknown'))"
}

user_id_kristina=$(get_user_id "$access_token3")
echo "  user_id Kristina: $user_id_kristina"

user_id_evgeniy=$(get_user_id "$access_token4")
echo "  user_id Evgeniy: $user_id_evgeniy"

echo ""

if [ "$user_id_kristina" != "unknown" ] && [ "$user_id_evgeniy" != "unknown" ]; then
  echo "  Приглашение Kristina в проект ${project_ids[6]}..."
  # Сериализатор InviteUserProjectSerializer берёт project_id и user_id из контекста (URL)
  result=$(api_post_empty "$BASE_URL/projects/${project_ids[6]}/invite/$user_id_kristina/" "$access_token")
  code=$(echo "$result" | cut -d'|' -f1)
  body=$(echo "$result" | cut -d'|' -f2-)
  if [ "$code" -eq 200 ]; then
    echo -e "${GREEN}    ✓ Приглашение отправлено${NC}"
  else
    echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
  fi
  echo ""

  echo "  Приглашение Evgeniy в проект ${project_ids[1]}..."
  result=$(api_post_empty "$BASE_URL/projects/${project_ids[1]}/invite/$user_id_evgeniy/" "$access_token")
  code=$(echo "$result" | cut -d'|' -f1)
  body=$(echo "$result" | cut -d'|' -f2-)
  if [ "$code" -eq 200 ]; then
    echo -e "${GREEN}    ✓ Приглашение отправлено${NC}"
  else
    echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
  fi
  echo ""
else
  echo -e "${RED}  ✗ Не удалось получить user_id, пропускаем приглашения${NC}"
  echo ""
fi

# =============================================================================
# Шаг 10: Лайки проектов
#   - Kristina лайкает проект #5 (Сервис книг от Натальи)
#   - Evgeniy лайкает проект #2 (Kristina фитнесс приложение)
#   - Natalya лайкает проект #4 (Хитрый Евгений)
#   - Oleg лайкает проект #6 (E-Commerce Platform)
#   - Stanislav лайкает проект #7 (DevOps Infrastructure Automation)
#
# Эндпоинт: POST /api/v1/projects/{project_id}/like/
# В сериализаторе data={'project_id': project.project_id}, нужно передать JSON
# =============================================================================
echo -e "${YELLOW}[10/11] Лайки проектов...${NC}"

echo "  Лайк проекта ${project_ids[4]} от Kristina..."
result=$(api_post_json "$BASE_URL/projects/${project_ids[4]}/like/" "$access_token3" "{\"project_id\": \"${project_ids[4]}\"}")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 200 ]; then
  liked=$(echo "$body" | python -c "import sys,json; print(json.load(sys.stdin).get('liked', 'unknown'))")
  echo -e "${GREEN}    ✓ Лайк: $liked${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

echo "  Лайк проекта ${project_ids[1]} от Evgeniy..."
result=$(api_post_json "$BASE_URL/projects/${project_ids[1]}/like/" "$access_token4" "{\"project_id\": \"${project_ids[1]}\"}")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 200 ]; then
  liked=$(echo "$body" | python -c "import sys,json; print(json.load(sys.stdin).get('liked', 'unknown'))")
  echo -e "${GREEN}    ✓ Лайк: $liked${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

echo "  Лайк проекта ${project_ids[3]} от Natalya..."
result=$(api_post_json "$BASE_URL/projects/${project_ids[3]}/like/" "$access_token5" "{\"project_id\": \"${project_ids[3]}\"}")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 200 ]; then
  liked=$(echo "$body" | python -c "import sys,json; print(json.load(sys.stdin).get('liked', 'unknown'))")
  echo -e "${GREEN}    ✓ Лайк: $liked${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

echo "  Лайк проекта ${project_ids[6]} от Oleg..."
result=$(api_post_json "$BASE_URL/projects/${project_ids[6]}/like/" "$access_token2" "{\"project_id\": \"${project_ids[6]}\"}")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 200 ]; then
  liked=$(echo "$body" | python -c "import sys,json; print(json.load(sys.stdin).get('liked', 'unknown'))")
  echo -e "${GREEN}    ✓ Лайк: $liked${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

# =============================================================================
# Шаг 11: Лайки вопросов
#   - Kristina лайкает вопрос #1
#   - Evgeniy лайкает вопрос #2
#   - Natalya лайкает вопрос #3
#   - Oleg лайкает вопрос #4
#   - Stanislav лайкает вопрос #5
#
# Эндпоинт: POST /api/v1/qna/questions/{question_id}/like/
# Тело не требуется
# =============================================================================
echo -e "${YELLOW}[11/11] Лайки вопросов...${NC}"

echo "  Лайк вопроса ${question_ids[0]} от Kristina..."
result=$(api_post_empty "$BASE_URL/qna/questions/${question_ids[0]}/like/" "$access_token3")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 200 ]; then
  liked=$(echo "$body" | python -c "import sys,json; print(json.load(sys.stdin).get('liked', 'unknown'))")
  echo -e "${GREEN}    ✓ Лайк: $liked${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

echo "  Лайк вопроса ${question_ids[1]} от Evgeniy..."
result=$(api_post_empty "$BASE_URL/qna/questions/${question_ids[1]}/like/" "$access_token4")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 200 ]; then
  liked=$(echo "$body" | python -c "import sys,json; print(json.load(sys.stdin).get('liked', 'unknown'))")
  echo -e "${GREEN}    ✓ Лайк: $liked${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

echo "  Лайк вопроса ${question_ids[2]} от Natalya..."
result=$(api_post_empty "$BASE_URL/qna/questions/${question_ids[2]}/like/" "$access_token5")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 200 ]; then
  liked=$(echo "$body" | python -c "import sys,json; print(json.load(sys.stdin).get('liked', 'unknown'))")
  echo -e "${GREEN}    ✓ Лайк: $liked${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

echo "  Лайк вопроса ${question_ids[3]} от Oleg..."
result=$(api_post_empty "$BASE_URL/qna/questions/${question_ids[3]}/like/" "$access_token2")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 200 ]; then
  liked=$(echo "$body" | python -c "import sys,json; print(json.load(sys.stdin).get('liked', 'unknown'))")
  echo -e "${GREEN}    ✓ Лайк: $liked${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

echo "  Лайк вопроса ${question_ids[4]} от Stanislav..."
result=$(api_post_empty "$BASE_URL/qna/questions/${question_ids[4]}/like/" "$access_token")
code=$(echo "$result" | cut -d'|' -f1)
body=$(echo "$result" | cut -d'|' -f2-)
if [ "$code" -eq 200 ]; then
  liked=$(echo "$body" | python -c "import sys,json; print(json.load(sys.stdin).get('liked', 'unknown'))")
  echo -e "${GREEN}    ✓ Лайк: $liked${NC}"
else
  echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
fi
echo ""

# Удаляем временный файл
rm -f "$TEMP_JSON"

echo "=============================================="
echo -e "${GREEN} Все операции завершены!${NC}"
echo "=============================================="