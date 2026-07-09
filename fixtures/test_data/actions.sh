#!/bin/bash
# =============================================================================
# Обработчики действий для создания тестовых данных
# =============================================================================

# =============================================================================
# call_api — универсальный вызов API с обработкой ответа
# Аргументы: method url token [json_body] [success_code=201]
# Глобальные: success_actions (инкремент при успехе)
# =============================================================================
call_api() {
  local method=$1 url=$2 token=$3 json_body=$4 success_code=${5:-201}
  local result; result=$(api_request "$method" "$url" "$token" "$json_body")
  local code="${result%%|*}" body="${result#*|}"
  if [ "$code" -eq "$success_code" ]; then
    ((success_actions++))
    echo "$body"
    return 0
  else
    echo -e "${RED}    ✗ Ошибка (HTTP $code): $body${NC}" >&2
    return 1
  fi
}

# =============================================================================
# Обработчики действий
#
# Соглашение об именовании полей:
#   - массивы (множественное число): indices, project_indices, question_indices,
#     user_indices, answer_indices, invitee_indices
#   - единственное число (одна зависимость): question_index, project_index
# =============================================================================

do_create_project() {
  local token=$1 action=$2; local -n ref=$3
  for idx in $(json_extract "$action" "indices"); do
    local data; data=$(json_from_file "projects.json" "$idx")
    local title; title=$(json_extract "$data" "title" "Без названия")
    echo "    Создание проекта: $title"
    local body; body=$(call_api "POST" "$BASE_URL/projects/" "$token" "$data") || continue
    local pid; pid=$(json_extract "$body" "project_id")
    ref["$idx"]="$pid"; echo -e "${GREEN}    ✓ Создан project_id: $pid (индекс $idx)${NC}"
  done
}

do_create_question() {
  local token=$1 action=$2; local -n ref=$3
  for idx in $(json_extract "$action" "indices"); do
    local data; data=$(json_from_file "questions.json" "$idx")
    local title; title=$(json_extract "$data" "title" "Без названия")
    echo "    Создание вопроса: $title"
    local body; body=$(call_api "POST" "$BASE_URL/qna/questions/" "$token" "$data") || continue
    local qid; qid=$(json_extract "$body" "question_id")
    ref["$idx"]="$qid"; echo -e "${GREEN}    ✓ Создан question_id: $qid (индекс $idx)${NC}"
  done
}

do_create_answer() {
  local token=$1 action=$2; local -n qref=$3 aref=$4
  local q_idx; q_idx=$(json_extract "$action" "question_index")
  local qid="${qref[$q_idx]}"
  for a_idx in $(json_extract "$action" "answer_indices"); do
    local data; data=$(json_from_file "answers.json" "$a_idx")
    local content; content=$(json_extract "$data" "content" "")
    echo "    Создание ответа на вопрос $qid: ${content:0:50}..."
    local body; body=$(call_api "POST" "$BASE_URL/qna/questions/$qid/answers/" "$token" "$data") || continue
    local aid; aid=$(json_extract "$body" "answer_id")
    aref["$a_idx"]="$aid"; echo -e "${GREEN}    ✓ Создан answer_id: $aid (индекс $a_idx)${NC}"
  done
}

do_respond() {
  local token=$1 action=$2; local -n ref=$3; local -n resp_ref=$4
  for p_idx in $(json_extract "$action" "project_indices"); do
    local pid="${ref[$p_idx]}"
    echo "    Отклик на проект $pid..."
    local body; body=$(call_api "POST" "$BASE_URL/projects/$pid/responses/" "$token" "" 200) || continue
    local rid; rid=$(json_extract "$body" "response_id")
    resp_ref["$p_idx"]="$rid"; echo -e "${GREEN}    ✓ Отклик создан response_id: $rid (индекс $p_idx)${NC}"
  done
}

do_update_profile() {
  local token=$1 action=$2
  local profile_index; profile_index=$(json_extract "$action" "profile_index")
  local avatar_file; avatar_file=$(json_extract "$action" "avatar_file")

  echo "    Обновление профиля из profiles.json (индекс $profile_index)..."
  local profile_data; profile_data=$(json_from_file "profiles.json" "$profile_index")
  local body; body=$(call_api "PATCH" "$BASE_URL/user/profile/me/" "$token" "$profile_data" 200) || return 1
  echo -e "${GREEN}    ✓ Профиль обновлён${NC}"

  # Загрузка аватара (если указан файл)
  if [ -n "$avatar_file" ] && [ -f "$DATA_DIR/$avatar_file" ]; then
    echo "    Загрузка аватара из $avatar_file..."
    local result; result=$(api_upload_file "POST" "$BASE_URL/user/profile/me/avatar/" "$token" "$DATA_DIR/$avatar_file")
    local code="${result%%|*}" body="${result#*|}"
    if [ "$code" -eq 200 ] || [ "$code" -eq 201 ]; then
      echo -e "${GREEN}    ✓ Аватар загружен${NC}"
      ((success_actions++))
    else
      echo -e "${RED}    ✗ Ошибка загрузки аватара (HTTP $code): $body${NC}" >&2
    fi
  fi
}

do_create_experience() {
  local token=$1 action=$2
  for idx in $(json_extract "$action" "indices"); do
    local data; data=$(json_from_file "experience.json" "$idx")
    local company; company=$(json_extract "$data" "company" "")
    local position; position=$(json_extract "$data" "position" "")
    echo "    Создание опыта: $position в $company"
    local body; body=$(call_api "POST" "$BASE_URL/user/profile/me/experience/" "$token" "$data" 201) || continue
    echo -e "${GREEN}    ✓ Опыт создан${NC}"
  done
}

do_invite() {
  local token=$1 action=$2; local -n ref=$3; local -n inv_resp_ref=$4
  local p_idx; p_idx=$(json_extract "$action" "project_index")
  local pid="${ref[$p_idx]}"
  for inv_idx in $(json_extract "$action" "invitee_indices"); do
    local inv_uid="${user_ids[$inv_idx]}"
    echo "    Приглашение $(json_extract "${USERS_JSON[$inv_idx]}" "first_name") в проект $pid..."
    local body; body=$(call_api "POST" "$BASE_URL/projects/$pid/invite/$inv_uid/" "$token" "" 200) || continue
    local rid; rid=$(json_extract "$body" "response_id")
    inv_resp_ref["$inv_idx"]="$rid"; echo -e "${GREEN}    ✓ Приглашение отправлено response_id: $rid (индекс $inv_idx)${NC}"
  done
}

do_update_response_status() {
  local token=$1 action=$2; local -n resp_ref=$3
  local status_value; status_value=$(json_extract "$action" "status")
  for idx in $(json_extract "$action" "response_indices"); do
    local rid="${resp_ref[$idx]}"
    echo "    Обновление статуса response $rid → $status_value..."
    call_api "PATCH" "$BASE_URL/projects/responses/$rid/status/" "$token" "{\"status\": \"$status_value\"}" 200 && \
      echo -e "${GREEN}    ✓ Статус обновлён на $status_value${NC}"
  done
}

# =============================================================================
# do_like — универсальная функция для лайков проектов, вопросов и пользователей
#
# Аргументы:
#   token         — токен авторизованного пользователя (кто ставит лайк)
#   action        — JSON-объект действия из roles.json
#   ref           — nameref на массив с id объектов (project_ids/question_ids/user_ids)
#   url_template  — шаблон URL с плейсхолдером {id}
#   label         — метка для сообщений ("проекта", "вопроса", "пользователя")
#   success_code  — ожидаемый HTTP-код успеха (200 или 201)
#   json_body     — тело запроса (может быть пустым)
# =============================================================================
do_like() {
  local token=$1 action=$2; local -n ref=$3
  local url_template=$4 label=$5 success_code=$6 json_body=$7

  # Определяем ключ для извлечения индексов из action по типу
  local action_type; action_type=$(json_extract "$action" "type")
  local indices_key
  case "$action_type" in
    "like_project")  indices_key="project_indices";;
    "like_question") indices_key="question_indices";;
    "like_answer")   indices_key="answer_indices";;
    "like_user")     indices_key="user_indices";;
    *) echo -e "${RED}    ✗ Неизвестный тип лайка: $action_type${NC}"; return 1;;
  esac

  for idx in $(json_extract "$action" "$indices_key"); do
    local obj_id="${ref[$idx]}"
    local url="${url_template//\{id\}/$obj_id}"
    echo "    Лайк $label $obj_id..." >&2
    local body; body=$(call_api "POST" "$url" "$token" "$json_body" "$success_code") || return 1
    echo -e "${GREEN}    ✓ Лайк $label: $(json_extract "$body" "liked")${NC}"
  done
}