# conftest.py
import sys
import os

# Adiciona o diretório 'src' ao sys.path para que os módulos possam ser importados absolutamente
# Calcula o caminho absoluto para o diretório 'src' baseado na localização deste conftest.py
REPO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, REPO_DIR)

#print(f"Added to sys.path: {REPO_DIR}")
#print(f"Current sys.path: {sys.path}")