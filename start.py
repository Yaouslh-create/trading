import sys, os, glob

base = os.path.dirname(os.path.abspath(__file__))
print(f"Render base: {base}")
print(f"Contenu racine: {os.listdir(base)}")

# Cherche start_cloud.py dans tous les sous-dossiers
matches = glob.glob(os.path.join(base, "**", "start_cloud.py"), recursive=True)
print(f"start_cloud.py trouvé: {matches}")

if not matches:
    print("ERREUR: Fichiers non trouvés!")
    for r, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            print(os.path.join(r, f).replace(base, ""))
    sys.exit(1)

cloud_file   = matches[0]
cloud_dir    = os.path.dirname(cloud_file)
project_dir  = os.path.dirname(cloud_dir)

print(f"Projet: {project_dir}")
sys.path.insert(0, project_dir)
sys.path.insert(0, base)
os.chdir(project_dir)

exec(open(cloud_file).read())
