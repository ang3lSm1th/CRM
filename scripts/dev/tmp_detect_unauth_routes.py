from pathlib import Path
import re

root = Path('.')
pattern = re.compile(r'^\s*@(?P<decorator>\w+)')
route_pattern = re.compile(r'^\s*@.*\.route\(')
for f in root.rglob('*.py'):
    if 'env' in f.parts or f.name.startswith('tmp_'):
        continue
    lines = f.read_text(encoding='utf-8', errors='ignore').splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if route_pattern.match(line):
            decorators = []
            j = i-1
            while j >= 0 and lines[j].strip().startswith('@'):
                decorators.append(lines[j].strip())
                j -= 1
            # if no login or role required decorators in block of decorators
            if not any('login_required' in d or 'role_required' in d for d in decorators):
                func_line = lines[i+1] if i+1 < len(lines) else ''
                if 'def ' in func_line:
                    print(f'{f}:{i+2}: {func_line.strip()} -> decorators={decorators}')
        i += 1
