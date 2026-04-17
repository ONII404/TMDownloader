# /utils/FileManager.py
import zipfile
import shutil
from pathlib import Path

class FileManager:
    @staticmethod
    def prepare_dir(base_path, folder_name):
        path = Path(base_path) / folder_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def compress_and_clean(folder_path):
        zip_path = folder_path.parent / f"{folder_path.name}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in folder_path.iterdir():
                if file.is_file():
                    zf.write(file, arcname=file.name)
        
        shutil.rmtree(folder_path)
        return zip_path