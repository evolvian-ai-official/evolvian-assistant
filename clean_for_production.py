import os
import shutil

# Archivos específicos a eliminar
FILES_TO_DELETE = [
    "EstadodeCuenta (3).pdf",
    "test_rag_script.py",
    "test_openai_chain.py",
    "test_imports.py",
    "requirements_raw.txt",
    "python-version.txt",
    "ejemplo.pdf",
    ".DS_Store"
]

# Carpetas completas a eliminar
FOLDERS_TO_DELETE = [
    "__pycache__",
    "notebooks"
]

def delete_files(base_path):
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file in FILES_TO_DELETE:
                full_path = os.path.join(root, file)
                print(f"Eliminando archivo: {full_path}")
                os.remove(full_path)

def delete_folders(base_path):
    for root, dirs, files in os.walk(base_path):
        for folder in dirs:
            if folder in FOLDERS_TO_DELETE:
                full_path = os.path.join(root, folder)
                print(f"Eliminando carpeta: {full_path}")
                shutil.rmtree(full_path)

if __name__ == "__main__":
    PROJECT_PATH = "."  # Cambia esto si ejecutas desde fuera del proyecto
    delete_files(PROJECT_PATH)
    delete_folders(PROJECT_PATH)
    print("✔️ Limpieza completada. Tu proyecto está listo para producción.")
