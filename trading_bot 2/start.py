import sys, os

# Trouve automatiquement le bon chemin peu importe la structure
base = os.path.dirname(os.path.abspath(__file__))

# Cherche trading_bot dans tous les sous-dossiers possibles
for root, dirs, files in os.walk(base):
    if 'start_cloud.py' in files and 'cloud' in root:
        sys.path.insert(0, os.path.dirname(root))
        sys.path.insert(0, base)
        os.chdir(os.path.dirname(root))
        break

from cloud.start_cloud import *
