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

# Подключаем общие функции
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/utils.sh"

echo "=============================================="
echo " Регистрация пользователей"
echo "=============================================="
echo ""

# Загружаем пользователей
echo "Загрузка пользователей..."
load_users
echo ""

# =============================================================================
# Вспомогательные функции для извлечения полей пользователя
# =============================================================================
user_email()       { json_extract "${USERS_JSON[$1]}" "email"; }
user_password()    { json_extract "${USERS_JSON[$1]}" "password"; }
user_first_name()  { json_extract "${USERS_JSON[$1]}" "first_name"; }
user_last_name()   { json_extract "${USERS_JSON[$1]}" "last_name"; }

# =============================================================================
# Функция: подтверждение email через Django shell
# =============================================================================
confirm_email() {
  local email=$1

  # Подтверждаем email напрямую через manage.py shell
  # (allauth 65+ использует HMAC-ключи, которые не хранятся в БД)
  # email передаётся через переменную окружения, чтобы избежать shell injection
  local result
  result=$(EMAIL="$email" uv run python manage.py shell -c "
import os
from allauth.account.models import EmailAddress
email = os.environ['EMAIL']
try:
    ea = EmailAddress.objects.get(email=email)
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

# Временный файл для данных
TEMP_JSON="$DATA_DIR/temp_user_data.json"
USER_IDS_FILE="$DATA_DIR/user_ids.json"

# Удаляем старый файл с id, если есть
rm -f "$USER_IDS_FILE"

users_count=${#USERS_JSON[@]}
echo "  Всего пользователей для регистрации: $users_count"
echo ""

# Инициализируем массив для id пользователей
user_ids=()

for i in $(seq 0 $((users_count - 1))); do
  email=$(user_email "$i")
  password=$(user_password "$i")
  first_name=$(user_first_name "$i")
  last_name=$(user_last_name "$i")

  # Извлекаем данные пользователя во временный файл
  echo "${USERS_JSON[$i]}" > "$TEMP_JSON"

  echo "  Регистрация: $email ($first_name $last_name)"

  response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/user/auth/registration/" \
    -H "Content-Type: application/json; charset=utf-8" \
    --data-binary "@$TEMP_JSON")

  code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
  body=$(echo "$response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")

  if [ "$code" -eq 201 ]; then
    echo -e "${GREEN}    ✓ Успешно${NC}"
    # Подтверждаем email после регистрации
    echo "  Подтверждение email..."
    confirm_email "$email"

    # Логинимся и получаем pk пользователя
    echo "  Получение id пользователя..."
    token=$(login "$email" "$password")
    if [ -n "$token" ]; then
      uid=$(get_user_id "$token")
      user_ids+=("$uid")
      echo -e "${GREEN}    ✓ pk=$uid${NC}"
    else
      echo -e "${RED}    ✗ Ошибка логина после регистрации${NC}"
      user_ids+=("unknown")
    fi
  else
    echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}"
    user_ids+=("unknown")
  fi

  echo ""
done

# Сохраняем массив id в JSON-файл 
printf '%s\n' "${user_ids[@]}" | $PYTHON -c "
import json, sys
ids = [line.strip() for line in sys.stdin if line.strip()]
with open('$USER_IDS_FILE', 'w') as f:
    json.dump(ids, f, ensure_ascii=False)
"

# Удаляем временный файл
rm -f "$TEMP_JSON"

echo -e "${GREEN}  ✓ Сохранено ${#user_ids[@]} id пользователей в $USER_IDS_FILE${NC}"

echo "=============================================="
echo -e "${GREEN} Регистрация завершена!${NC}"
echo "=============================================="
