from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import os

WATCH_FILE = os.path.abspath("./logs/test.log")
WATCH_DIR  = os.path.dirname(WATCH_FILE)

class TailHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_size = os.path.getsize(WATCH_FILE) if os.path.exists(WATCH_FILE) else 0

    def on_modified(self, event):
        if event.src_path != WATCH_FILE:
            return  # 特定のファイルのみ

        new_size = os.path.getsize(WATCH_FILE)
        if new_size > self.last_size:
            # 追加分だけ読む
            with open(WATCH_FILE, "r") as f:
                f.seek(self.last_size)
                added = f.read()
                print("[APPEND]", added.strip())

        self.last_size = new_size

# ---- イベントハンドラ ----
class MyHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            print(f"[CREATE] {event.src_path}")
            self.process(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            print(f"[MODIFY] {event.src_path}")
            self.process(event.src_path)

    def process(self, path):
        # ファイル内容を読むなど自由に
        try:
            with open(path, "r") as f:
                data = f.read()
            print(f"[DATA]\n{data[:200]}...\n")  # 最初200文字だけ
        except Exception as e:
            print(f"Error reading {path}: {e}")


# ---- メイン ----
if __name__ == "__main__":
    target_dir = "./logs"   # 監視したいディレクトリ
    os.makedirs(target_dir, exist_ok=True)

    event_handler = MyHandler()
    handler = TailHandler()
    observer = Observer()
    observer.schedule(event_handler, path=target_dir, recursive=False)
    observer.schedule(handler, os.path.dirname(WATCH_FILE), recursive=False)
    
    print(f"Watching directory: {target_dir}")
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping observer...")
        observer.stop()

    observer.join()