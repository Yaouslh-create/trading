import sys, os, subprocess, glob

base = os.path.dirname(os.path.abspath(__file__))
print(f"Base dir: {base}")
print(f"Contenu: {os.listdir(base)}")

# Cherche récursivement start_cloud.py
matches = glob.glob(os.path.join(base, "**", "start_cloud.py"), recursive=True)
print(f"Fichiers trouvés: {matches}")

if matches:
    cloud_dir = os.path.dirname(matches[0])
    project_dir = os.path.dirname(cloud_dir)
    sys.path.insert(0, project_dir)
    sys.path.insert(0, base)
    os.chdir(project_dir)
    print(f"Lancement depuis: {project_dir}")
    exec(open(matches[0]).read())
else:
    print("ERREUR: start_cloud.py introuvable")
    print("Structure complète:")
    for r, d, f in os.walk(base):
        level = r.replace(base, '').count(os.sep)
        print('  ' * level + os.path.basename(r) + '/')
        for file in f:
            print('  ' * (level+1) + file)
