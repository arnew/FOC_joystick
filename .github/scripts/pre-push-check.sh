#!/bin/bash
# Pre-push validation script for CI compliance
# Run this before pushing to catch issues early
set -e

echo "🔍 Running pre-push checks..."

# 1. Function size compliance (AGENTS.md: max 43 lines)
echo "  Checking function sizes (AGENTS.md)..."
python3 - <<'PY'
import pathlib
import re
import sys

max_lines = 43
func_start = re.compile(r'^\s*[\w:<>~*&\s]+\s+[\w:~]+\s*\([^;]*\)\s*\{\s*$')
control_start = re.compile(r'^\s*(if|for|while|switch|else|do|catch)\b')

failures = []

for path in sorted(pathlib.Path('src').glob('*.cpp')):
    lines = path.read_text(encoding='utf-8').splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if func_start.match(line) and not control_start.match(line):
            start = i
            sig = line.strip()
            depth = line.count('{') - line.count('}')
            i += 1
            while i < len(lines) and depth > 0:
                depth += lines[i].count('{') - lines[i].count('}')
                i += 1
            end = i - 1
            body_len = max(0, end - start - 1)
            if body_len > max_lines:
                failures.append(f"FAIL: {path}:{start + 1} - {sig} ({body_len} lines, max {max_lines})")
        else:
            i += 1

if failures:
    print('\n'.join(failures))
    print(f"\n❌ {len(failures)} function(s) exceed {max_lines} lines")
    print("   Refactor large functions before pushing")
    sys.exit(1)

print('    ✅ All functions ≤43 lines')
PY

# 2. Build check (pico_1motor_endless is default)
echo "  Building firmware..."
platformio run -e pico_1motor_endless >/dev/null 2>&1 || {
  echo "    ❌ Build failed"
  echo "   Run: platformio run -e pico_1motor_endless"
  exit 1
}
echo "    ✅ Build successful"

# 3. Headless tests
echo "  Running headless tests..."
python -m pytest test/ -q --tb=no >/dev/null 2>&1 || {
  echo "    ❌ Tests failed"
  echo "   Run: python -m pytest test/ -v"
  exit 1
}
echo "    ✅ Tests passed"

echo ""
echo "✅ All pre-checks passed"
echo "📤 Safe to push - CI will run full validation"
