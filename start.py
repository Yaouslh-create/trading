import sys, os, glob

base = os.path.dirname(os.path.abspath(__file__))

# Affiche la structure pour debug
print("=== STRUCTURE DU PROJET ===")
for root, dirs, files in os.walk(base):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    level = root.replace(base, '').count(os.sep)
    print('  ' * level + os.path.basename(root) + '/')
    for f in files:
        print('  ' * (level+1) + f)

# Trouve start_cloud.py peu importe où il est
matches = glob.glob(os.path.join(base, "**", "start_cloud.py"), recursive=True)

if not matches:
    print("ERREUR CRITIQUE: start_cloud.py introuvable!")
    sys.exit(1)

cloud_file = matches[0]
project_dir = os.path.dirname(os.path.dirname(cloud_file))
print(f"\nFichier trouvé: {cloud_file}")
print(f"Répertoire projet: {project_dir}")

sys.path.insert(0, project_dir)
sys.path.insert(0, base)
os.chdir(project_dir)

exec(open(cloud_file).read())
