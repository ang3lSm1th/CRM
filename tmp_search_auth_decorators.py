from pathlib import Path
root = Path('.')
for f in root.rglob('*.py'):
    if 'env' in f.parts:
        continue
    txt = f.read_text(encoding='utf-8', errors='ignore')
    if 'login_required' in txt or 'role_required' in txt:
        print(f)
