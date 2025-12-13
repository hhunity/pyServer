import zmq
import time

context = zmq.Context()

# REQ: コマンド送信
req = context.socket(zmq.REQ)
req.connect("tcp://localhost:5555")

# SUB: 状態購読
sub = context.socket(zmq.SUB)
sub.connect("tcp://localhost:5556")
sub.setsockopt_string(zmq.SUBSCRIBE, "")

# 状態受信スレッド
import threading

def recv_status():
    while True:
        msg = sub.recv_json()
        print("[STATUS]", msg)

threading.Thread(target=recv_status, daemon=True).start()

# 制御コマンド
while True:
    req.send_json({"cmd":"action"})
    reply = req.recv_string()
    print("reply:", reply)
    time.sleep(5)