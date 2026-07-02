#!/bin/bash
# =============================================================================
# Загрузка тестовых данных на dev-сервер
#
# Запускать из контейнера backend:
#   sudo docker compose -f docker-compose.dev.yaml exec \
#     backend bash fixtures/test_data/load_on_dev.sh
#
# При необходимости можно переопределить переменные:
#   sudo docker compose -f docker-compose.dev.yaml exec \
#     -e BASE_URL="https://dev.code-unity.ru/api/v1" \
#     backend bash fixtures/test_data/load_on_dev.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'

# Значения по умолчанию — для запуска внутри контейнера backend
# При запуске с хоста нужно переопределить:
#   BASE_URL="https://dev.code-unity.ru/api/v1" \
#   FIXTURES_PYTHON="docker exec backend python" \
#   bash fixtures/test_data/load_on_dev.sh
export BASE_URL="${BASE_URL:-https://dev.code-unity.ru/api/v1}"
export FIXTURES_PYTHON="${FIXTURES_PYTHON:-docker exec backend python}"

echo "=============================================="
echo " Загрузка тестовых данных на dev-сервер"
echo "=============================================="
echo ""
echo "  BASE_URL:        $BASE_URL"
echo "  FIXTURES_PYTHON: $FIXTURES_PYTHON"
echo ""

# Шаг 1: Регистрация пользователей
echo -e "${GREEN}[1/2] Регистрация пользователей...${NC}"
bash "$SCRIPT_DIR/create_users.sh"
echo ""

# Шаг 2: Создание объектов (проекты, вопросы, ответы и т.д.)
echo -e "${GREEN}[2/2] Создание объектов...${NC}"
bash "$SCRIPT_DIR/create_obj.sh"
echo ""

echo "=============================================="
echo -e "${GREEN} Загрузка тестовых данных завершена!${NC}"
echo "=============================================="