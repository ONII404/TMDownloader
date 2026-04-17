# /core/DownloadEngine.py
import concurrent.futures

class DownloadEngine:
    def __init__(self, session, max_workers=5):
        self.session = session
        self.max_workers = max_workers

    def download_image(self, url, dest_path, referer):
        """Descarga una sola imagen. Retorna (True/False, url)."""
        headers = {"Referer": referer}
        try:
            for verify in [True, False]:
                try:
                    r = self.session.get(url, headers=headers, timeout=20, stream=True, verify=verify)
                    if r.status_code == 200:
                        with open(dest_path, "wb") as f:
                            for chunk in r.iter_content(8192):
                                f.write(chunk)
                        return True, url
                    break  # 404 u otro error HTTP: no reintentar con SSL
                except Exception:
                    continue
        except Exception:
            pass
        return False, url

    def download_manga(self, image_tasks):
        """
        image_tasks: Lista de tuplas (url, dest_path, referer)
        Imprime progreso en tiempo real y al final lista los fallos.
        Retorna True si todas las imágenes se bajaron correctamente.
        """
        total = len(image_tasks)
        done = 0
        failed_urls = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.download_image, *task): task for task in image_tasks}

            for future in concurrent.futures.as_completed(futures):
                success, url = future.result()
                done += 1
                if success:
                    print(f"\r  [*] Progreso: {done}/{total}", end="", flush=True)
                else:
                    failed_urls.append(url)
                    print(f"\r  [!] Fallo ({done}/{total}): {url}", flush=True)

        print()  # salto de línea tras el progreso

        if failed_urls:
            print(f"\n  [!] {len(failed_urls)} imagen(s) no se pudieron descargar:")
            for u in failed_urls:
                print(f"      - {u}")

        return len(failed_urls) == 0