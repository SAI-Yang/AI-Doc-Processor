"""Cross-platform install script"""
import subprocess, sys, os
from pathlib import Path

root = Path(__file__).parent
os.chdir(root)

print('Installing AI Doc Processor...')
print()

# Upgrade pip
subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'],
               capture_output=True)

# Install from requirements
req = root / 'requirements.txt'
if req.exists():
    result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(req)])
    if result.returncode != 0:
        print('Retry with mirror...')
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(req),
                       '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple'])

# Ensure PyQt5
result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'PyQt5'])
if result.returncode != 0:
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'PyQt5',
                   '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple'])

# Verify
try:
    from PyQt5.QtWidgets import QApplication
    print('PyQt5 OK')
except:
    print('WARNING: PyQt5 may not be installed correctly')

print()
print('Install complete. Run: python -m app.main')
