import json
with open(r"d:/Dev/Backend/fixtures/test_data/users.json") as f:
    users = json.load(f)
print(f"Loaded {len(users)} users")