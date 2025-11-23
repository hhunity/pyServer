from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from typing import Callable, Optional
import time
import os
import re

def find_latest_log(log_dir,fileRegX):
    """Find newest test*.log (numbers only)."""
    latest_path = None
    latest_mtime = -1
    for name in os.listdir(log_dir):
        if not re.fullmatch(fileRegX, name):
            continue
        path = os.path.join(log_dir, name)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime > latest_mtime:
            latest_path = path
            latest_mtime = mtime
    return latest_path

class TailHandler(FileSystemEventHandler):
    def __init__(self, log_dir,fileRegX, callback: Optional[Callable[[str, str, Optional[str]], None]] = None):
        self.log_dir = log_dir
        self.fileRegX= fileRegX
        self.callback = callback
        self.watch_file = find_latest_log(self.log_dir,self.fileRegX)
        self.last_size = os.path.getsize(self.watch_file) if self.watch_file and os.path.exists(self.watch_file) else 0
        if self.watch_file:
            print(f"[TAIL] Now watching latest log: {self.watch_file}")
        else:
            print("[TAIL] No test*.log found yet.")

    def update_target(self):
        latest = find_latest_log(self.log_dir,self.fileRegX)
        if latest and latest != self.watch_file:
            self.watch_file = latest
            print(f"[TAIL] Switched to latest log: {latest}")
            # 新しいファイルに切り替わったら中身を先頭から読む
            try:
                with open(self.watch_file, "r") as f:
                    data = f.read()
                if data:
                    print("[SWITCH]", data.strip())
                    if self.callback:
                        self.callback("switch", self.watch_file, data)
            except Exception as e:
                print(f"[TAIL] Error reading {self.watch_file}: {e}")

            self.last_size = os.path.getsize(latest) if os.path.exists(latest) else 0

    def on_created(self, event):
        if event.is_directory:
            return
        self.update_target()

    def on_modified(self, event):
        if event.is_directory:
            return
        self.update_target()
        if not self.watch_file or event.src_path != self.watch_file:
            return  # 最新の test*.log のみ

        try:
            new_size = os.path.getsize(self.watch_file)
        except OSError as e:
            print(f"[TAIL] Failed to stat {self.watch_file}: {e}")
            return

        if new_size < self.last_size:
            # File truncated or rotated; start from beginning
            self.last_size = 0
        if new_size > self.last_size:
            # 追加分だけ読む
            try:
                with open(self.watch_file, "r") as f:
                    f.seek(self.last_size)
                    added = f.read()
                print("[APPEND]", added.strip())
                if self.callback and added:
                    self.callback("append", self.watch_file, added)
            except Exception as e:
                print(f"[TAIL] Error reading {self.watch_file}: {e}")

        self.last_size = new_size

# ---- イベントハンドラ ----
class MyHandler(FileSystemEventHandler):
    def __init__(self, callback: Optional[Callable[[str, str, Optional[str]], None]] = None):
        self.callback = callback

    def on_created(self, event):
        if not event.is_directory:
            print(f"[CREATE] {event.src_path}")
            if self.callback:
                self.callback("create", event.src_path, None)
    
    # def on_modified(self, event):
    #     if not event.is_directory:
    #         print(f"[MODIFY] {event.src_path}")
    #         self.process(event.src_path)

    # def process(self, path):
    #     # ファイル内容を読むなど自由に
    #     try:
    #         with open(path, "r") as f:
    #             data = f.read()
    #         print(f"[DATA]\n{data[:200]}...\n")  # 最初200文字だけ
    #     except Exception as e:
    #         print(f"Error reading {path}: {e}")

# ---- メイン ----
def schedule_tailfile(observer, path:str,fileRegx:str, callback: Optional[Callable[[str, str, Optional[str]], None]] = None) -> bool:
    log_dir = os.path.abspath(os.path.abspath(path))
    
    if not os.path.isdir(log_dir):
        print(f"{log_dir} is not exit")
        return False

    tail_handler  = TailHandler(log_dir=log_dir,fileRegX=fileRegx, callback=callback)
    observer.schedule(tail_handler, path=log_dir, recursive=False)
    print(f"Watching file: {log_dir}¥{fileRegx}")
    
    return True

def schedule_newfile(observer, path:str, callback: Optional[Callable[[str, str, Optional[str]], None]] = None) -> bool:
    log_dir = os.path.abspath(os.path.abspath(path))

    if not os.path.isdir(log_dir):
        print(f"{log_dir} is not exit")
        return False

    event_handler = MyHandler(callback=callback)
    observer.schedule(event_handler, path=log_dir, recursive=False)
    
    print(f"Watching directory: {log_dir}")

    return True

if __name__ == "__main__":
    
    def on_event(kind, path, data):
        print("EVENT", kind, path, repr(data))

    observer = PollingObserver(timeout=1.0)

    schedule_tailfile(observer,"./logs",r"test\d+\.log",on_event)
    schedule_newfile(observer,"./logs/images",on_event)

    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping observer...")
        observer.stop()
    
    observer.join()
