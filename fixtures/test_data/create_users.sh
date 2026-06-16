#!/bin/bash

# =============================================================================
# Скрипт для регистрации пользователей из users.json
#
# Запускать из корня проекта:
#   bash fixtures/test_data/create_users.sh
#
# С переменной окружения BASE_URL (для dev-сервера):
#   BASE_URL="https://dev.code-unity.ru/api/v1" bash fixtures/test_data/create_users.sh
# =============================================================================

# Конфигурация
BASE_URL="${BASE_URL:-http://127.0.0.1:8000/api/v1}"
JSON_FILE="fixtures/test_data/users.json"

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=============================================="
echo " Регистрация пользователей"
echo "=============================================="
echo ""

# Считаем количество пользователей
users_count=$(python -c "
import json
with open('$JSON_FILE', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(len(data))
")

echo "  Всего пользователей для регистрации: $users_count"
echo ""

# Временный файл для данных
TEMP_JSON="fixtures/test_data/temp_user_data.json"

for i in $(seq 0 $((users_count - 1))); do
  # Извлекаем данные пользователя
  python -c "
import json, os, sys
json_file = '$JSON_FILE'
with open(json_file, 'r', encoding='utf-8') as f:
    users = json.load(f)
user = users[$i]
with open('$TEMP_JSON', 'w', encoding='utf-8') as f:
    json.dump(user, f, ensure_ascii=False)
"

  email=$(python -c "
import json
with open('$TEMP_JSON', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(data.get('email', ''))
")

  first_name=$(python -c "
import json
with open('$TEMP_JSON', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(data.get('first_name', ''))
")

  last_name=$(python -c "
import json
with open('$TEMP_JSON', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(data.get('last_name', ''))
")

  echo "  Регистрация: $email ($first_name $last_name)"

  response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/user/auth/registration/" \
    -H "Content-Type: application/json; charset=utf-8" \
    --data-binary "@$TEMP_JSON")

  code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
  body=$(echo "$response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")

  if [ "$code" -eq 201 ]; then
    echo -e "${GREEN}    ✓ Успешно${NC}"
  else
    echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
  fi

  echo ""
  sleep 1
done

# Удаляем временный файл
rm -f "$TEMP_JSON"

echo "=============================================="
echo -e "${GREEN} Регистрация завершена!${NC}"
echo "=============================================="
