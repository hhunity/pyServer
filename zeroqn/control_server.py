import zmq
import time
import json

context = zmq.Context()

# REP: コマンド応答
rep = context.socket(zmq.REP)
rep.bind("tcp://*:5555")

# PUB: 状態配信（JSON）
pub = context.socket(zmq.PUB)
pub.bind("tcp://*:5556")

while True:
    # --- REQ → REP 処理 ---
    if rep.poll(10):  # 10msだけ待つ
        cmd = rep.recv_json()     # JSON受信
        print("cmd:", cmd)

        # 応答もJSON
        rep.send_json({"ack": True, "cmd": cmd})

    # --- 状態配信（PUB） ---
    status_msg = {
        "time": time.time(),
        "status": "running",
        "fps": 30.5,
        "temperature": 45.3
    }

    pub.send_json(status_msg)
    time.sleep(0.1)