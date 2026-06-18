OUTPUT_DIR="docs/erd"
mkdir -p "$OUTPUT_DIR"


MY_APPS="feedback projects qna users"

for APP in $MY_APPS; do
    python manage.py graph_models "$APP" -o "$OUTPUT_DIR/${APP}_erd.svg"
done

python manage.py graph_models -a -g -o "$OUTPUT_DIR/_full_project_erd.svg" --rankdir=LR --layout=sfdp

python manage.py graph_models $MY_APPS -g -o "$OUTPUT_DIR/_full_project_clean_erd.svg" --rankdir=LR --layout=fdp --exclude-models="User,Group,Permission,ContentType,Session"
