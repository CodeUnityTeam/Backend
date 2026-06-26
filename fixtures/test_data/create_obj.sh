#!/bin/bash
# =============================================================================
# Скрипт для создания тестовых данных
# Запускать из корня проекта: bash fixtures/test_data/create_obj.sh
# =============================================================================
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/utils.sh"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/actions.sh"

echo "=============================================="
echo " Создание тестовых данных"
echo "=============================================="
echo ""

load_users; load_roles; load_user_ids; echo ""

project_ids=(); question_ids=(); answer_ids=()
response_ids=(); invite_response_ids=()
total_actions=0; success_actions=0

# =============================================================================
# Диспетчер: по типу действия вызывает нужный обработчик
# =============================================================================
dispatch() {
  local token=$1 action=$2; shift 2
  case "$(json_extract "$action" "type")" in
    "update_profile")         do_update_profile         "$token" "$action";;
    "create_projects")        do_create_project         "$token" "$action" project_ids;;
    "create_questions")       do_create_question        "$token" "$action" question_ids;;
    "create_answers")         do_create_answer          "$token" "$action" question_ids answer_ids;;
    "create_experience")      do_create_experience      "$token" "$action";;
    "respond")                do_respond                "$token" "$action" project_ids response_ids;;
    "invite")                 do_invite                 "$token" "$action" project_ids invite_response_ids;;
    "update_response_status")
      local ref_name; ref_name=$(json_extract "$action" "ref")
      case "$ref_name" in
        "response_ids")       do_update_response_status "$token" "$action" response_ids;;
        "invite_response_ids") do_update_response_status "$token" "$action" invite_response_ids;;
        *) echo -e "${RED}    ✗ Неизвестный ref: $ref_name${NC}";;
      esac
      ;;
    "like_project")           do_like "$token" "$action" project_ids  "$BASE_URL/projects/{id}/like/"       "проекта"      200 '{"project_id":"{id}"}';;
    "like_question")          do_like "$token" "$action" question_ids "$BASE_URL/qna/questions/{id}/like/"  "вопроса"      200 "";;
    "like_answer")            do_like "$token" "$action" answer_ids   "$BASE_URL/qna/answers/{id}/like/"    "ответа"       200 "";;
    "like_user")              do_like "$token" "$action" user_ids     "$BASE_URL/user/profile/{id}/like/"   "пользователя" 201 "";;
    *) echo -e "${RED}    ✗ Неизвестный тип: $(json_extract "$action" "type")${NC}";;
  esac
}

# =============================================================================
# Обработка одного пользователя
# =============================================================================
process_user() {
  local token=$1 actions_json=$2
  while IFS= read -r action; do
    [ -z "$action" ] && continue
    ((total_actions++))
    echo "  Действие: $(json_extract "$action" "type")"
    dispatch "$token" "$action"
    echo ""
  done < <(echo "$actions_json" | $PYTHON -c "
import json, sys
for a in json.load(sys.stdin):
    sys.stdout.write(json.dumps(a, ensure_ascii=False) + '\n')
")
}

# =============================================================================
# Основной цикл по пользователям
# =============================================================================
for user_role in "${ROLES_USERS[@]}"; do
  u_idx=$(json_extract "$user_role" "user_index")
  actions_json=$(echo "$user_role" | $PYTHON -c "
import json, sys
print(json.dumps(json.load(sys.stdin).get('actions', []), ensure_ascii=False))
")

  echo -e "${YELLOW}--- Пользователь: $(json_extract "${USERS_JSON[$u_idx]}" "first_name") $(json_extract "${USERS_JSON[$u_idx]}" "last_name") (индекс $u_idx) ---${NC}"
  token=$(login "$(json_extract "${USERS_JSON[$u_idx]}" "email")" "$(json_extract "${USERS_JSON[$u_idx]}" "password")")
  if [ -z "$token" ]; then echo -e "${RED}  ✗ Ошибка логина${NC}"; echo ""; continue; fi
  echo -e "${GREEN}  ✓ Успешный логин${NC}"
  process_user "$token" "$actions_json"
  echo ""
done

echo "=============================================="
echo -e "${GREEN} Все операции завершены!${NC}"
echo "=============================================="

# Удаляем файл с id пользователей, если не указана переменная KEEP_USER_IDS
if [ "${KEEP_USER_IDS:-false}" != "true" ]; then
  rm -f "$DATA_DIR/user_ids.json"
  echo -e "${GREEN}  ✓ Временные файлы очищены${NC}"
else
  echo -e "${YELLOW}  ⚠ Файл user_ids.json сохранён (KEEP_USER_IDS=true)${NC}"
fi