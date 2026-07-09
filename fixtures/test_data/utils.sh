#!/bin/bash
# =============================================================================
# Общие функции для скриптов создания тестовых данных
# =============================================================================

# Цвета для вывода
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

# Конфигурация
BASE_URL="${BASE_URL:-http://127.0.0.1:8000/api/v1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -W 2>/dev/null || pwd)"
DATA_DIR="$SCRIPT_DIR"
USERS_FILE="$DATA_DIR/users.json"
ROLES_FILE="$DATA_DIR/roles.json"
PYTHON="${FIXTURES_PYTHON:-python}"
export PYTHONIOENCODING=utf-8

# =============================================================================
# Загрузка данных
# =============================================================================
load_users() {
  USERS_JSON=()
  while IFS= read -r line; do USERS_JSON+=("$line"); done < <(
    $PYTHON -c "
import json, sys
with open(r'$USERS_FILE', encoding='utf-8') as f:
    users = json.load(f)
for u in users:
    sys.stdout.write(json.dumps(u, ensure_ascii=False) + '\n')
")
  echo -e "${GREEN}  ✓ Загружено ${#USERS_JSON[@]} пользователей${NC}"
}

load_roles() {
  ROLES_USERS=()
  while IFS= read -r line; do ROLES_USERS+=("$line"); done < <(
    $PYTHON -c "
import json, sys
with open(r'$ROLES_FILE', encoding='utf-8') as f:
    roles = json.load(f)
for item in roles.get('users', []):
    sys.stdout.write(json.dumps(item, ensure_ascii=False) + '\n')
")
  echo -e "${GREEN}  ✓ Загружено ${#ROLES_USERS[@]} пользователей с ролями${NC}"
}

load_user_ids() {
  USER_IDS_FILE="$DATA_DIR/user_ids.json"
  user_ids=()
  if [ ! -f "$USER_IDS_FILE" ]; then
    echo -e "${RED}  ✗ Файл $USER_IDS_FILE не найден. Сначала выполните create_users.sh${NC}"
    return 1
  fi
  while IFS= read -r line; do
    # Удаляем \r (carriage return), который может появиться
    # при работе в Git Bash на Windows из-за преобразования
    # \n в \r\n в stdout Python
    line="${line%%$'\r'}"
    [ -z "$line" ] && continue
    user_ids+=("$line")
  done < <(
    # Используем buffer для избежания преобразования \n в \r\n
    $PYTHON -c "
import json, sys
with open(r'$USER_IDS_FILE', encoding='utf-8') as f:
    for uid in json.load(f):
        sys.stdout.buffer.write((str(uid) + '\n').encode('utf-8'))
")
  echo -e "${GREEN}  ✓ Загружено ${#user_ids[@]} id пользователей${NC}"
}

# =============================================================================
# Утилиты для работы с JSON
# =============================================================================
json_extract() {  # json_str key [default]
  local default="${3:-}"
  echo "$1" | KEY="$2" DEFAULT="$default" $PYTHON -c "
import json, os, sys
try:
    d = json.load(sys.stdin)
    key = os.environ['KEY']
    default = os.environ.get('DEFAULT', '')
    v = d.get(key, default)
    if isinstance(v, list):
        print(' '.join(str(x) for x in v))
    elif isinstance(v, bool):
        print(str(v).lower())
    elif v is None:
        print(default)
    else:
        print(v)
except Exception:
    print(os.environ.get('DEFAULT', ''))
"
}

json_from_file() {  # filename index
  local filename=$1 index=$2
  $PYTHON -c "
import json, os, sys
filename = '$filename'
index = $index
data_dir = r'$DATA_DIR'
try:
    with open(os.path.join(data_dir, filename), encoding='utf-8') as f:
        data = json.load(f)
    print(json.dumps(data[index], ensure_ascii=False))
except IndexError:
    print(f'ERROR: Индекс {index} отсутствует в файле {filename}. Доступны индексы 0..{len(data)-1}.', file=sys.stderr)
    sys.exit(1)
except FileNotFoundError:
    print(f'ERROR: Файл {filename} не найден в {data_dir}.', file=sys.stderr)
    sys.exit(1)
"
}

# =============================================================================
# HTTP-запросы
# =============================================================================
api_request() {  # method url token [json_body]
  local method=$1 url=$2 token=$3 json_body=$4
  if [ -n "$json_body" ]; then
    # Передаём тело запроса через stdin, чтобы избежать повреждения UTF-8
    local response=$(echo "$json_body" | curl -s -w "\nHTTP_CODE:%{http_code}" \
      -X "$method" "$url" \
      -H "Authorization: Bearer $token" \
      -H "Content-Type: application/json; charset=utf-8" \
      --data-binary @-)
  else
    local response=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
      -X "$method" "$url" \
      -H "Authorization: Bearer $token")
  fi
  local code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
  local body=$(echo "$response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")
  echo "$code|$body"
}

api_upload_file() {  # method url token file_path [field_name=file]
  local method=$1 url=$2 token=$3 file_path=$4 field_name=${5:-file}
  local response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X "$method" "$url" \
    -H "Authorization: Bearer $token" \
    -F "$field_name=@$file_path")
  local code=$(echo "$response" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
  local body=$(echo "$response" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")
  echo "$code|$body"
}

login() {  # email password → token or empty
  local r=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/user/auth/login/" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d "{\"email\":\"$1\",\"password\":\"$2\"}")
  local c=$(echo "$r" | grep -o "HTTP_CODE:[0-9]*" | cut -d: -f2)
  local b=$(echo "$r" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")
  if [ "$c" -eq 200 ]; then
    echo "$b" | $PYTHON -c "
import json, sys
print(json.load(sys.stdin)['access'])
"
    return 0
  fi
  echo ""; return 1
}

get_user_id() {  # token → pk
  local r=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X GET "$BASE_URL/user/profile/me/" -H "Authorization: Bearer $1")
  local b=$(echo "$r" | sed -n '/^{/,/^HTTP_CODE:/p' | grep -v "HTTP_CODE:")
  echo "$b" | $PYTHON -c "
import json, sys
print(json.load(sys.stdin).get('pk', 'unknown'))
"
}
