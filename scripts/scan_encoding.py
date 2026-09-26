"""
Scan for mojibake patterns in all source files.
"""
import os

MOJIBAKE = [b'\xe2\x80', b'\xc3\xa2\xe2\x82\xac', b'\xc3\xa2\xe2\x80']
SKIP_DIRS = {'node_modules', '.git', '__pycache__', 'dist', '.pytest_cache', '.vite', 'aetheris.db'}
EXTS = {'.py', '.jsx', '.js', '.json', '.md', '.txt', '.html', '.css', '.bat'}

found = []
clean = []

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
    for fname in files:
        if not any(fname.endswith(e) for e in EXTS):
            continue
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, 'rb') as f:
                raw = f.read()
            # Try decode as UTF-8
            try:
                text = raw.decode('utf-8')
            except UnicodeDecodeError:
                text = raw.decode('latin-1')
            
            issues = []
            # Check for common mojibake sequences (windows-1252 misread as latin-1)
            for seq in ['â€', 'â†', 'Ã©', 'Ã¢', 'â€™', 'â€œ', 'â€"']:
                if seq in text:
                    count = text.count(seq)
                    issues.append(f'{seq!r} x{count}')
            
            if issues:
                found.append((fpath, issues))
        except Exception as e:
            pass

print(f"Scanned source files for mojibake patterns")
if found:
    print(f"FOUND MOJIBAKE IN {len(found)} FILES:")
    for fpath, issues in found:
        print(f"  {fpath}: {', '.join(issues)}")
else:
    print("No mojibake patterns found. All source files clean.")

print(f"\nTotal files with issues: {len(found)}")
