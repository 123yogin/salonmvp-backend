import os

env_path = '.env'
key = 'DATABASE_URL'
value = 'postgresql://neondb_owner:npg_ObATxZhCP0c3@ep-restless-hall-a4tvp8w8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require'

lines = []
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        lines = f.readlines()

# Remove existing DATABASE_URL if any
lines = [l for l in lines if not l.startswith(f'{key}=')]

# Add new key
if lines and not lines[-1].endswith('\n'):
    lines[-1] += '\n'
lines.append(f'{key}={value}\n')

with open(env_path, 'w') as f:
    f.writelines(lines)

print("Updated .env with Neon DB URL")
