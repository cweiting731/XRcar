import socket, time, sys, os
from evdev import InputDevice, ecodes
from select import select

ESP_IP   = "192.168.0.154"
ESP_PORT = 4000
SEND_HZ  = 15
DEADZONE = 15   # from evtest Flat=15
INVERT_THROTTLE = False
INVERT_STEERING = False

DEV_PATH = "/dev/input/event5"   # handle device section

LY_AXIS = ecodes.ABS_Y   # 左搖桿 Y → threshold (0..255, center 128)
RX_AXIS = ecodes.ABS_RX  # 右搖桿 X → handler   (0..255, center 128)

def map_0_255(v, invert=False):
    # v 已是 0..255；做中心死區與反向
    out = 255 - v if invert else v
    if abs(out - 128) <= DEADZONE:
        out = 128
    # 夾限
    if out < 0: out = 0
    if out > 255: out = 255
    return out

def map_64_192(v, invert=False):
    mapped = 64 + (v * 128) // 255
    out = 192 - (mapped - 64) + 64 if invert else mapped
    if abs(out - 128) <= DEADZONE:
        out = 128
    if out < 64: out = 64
    if out > 192: out = 192
    return out

def main():
    if not os.path.exists(DEV_PATH):
        sys.exit(f"device not found: {DEV_PATH}")

    dev = InputDevice(DEV_PATH)
    print(f"using device: {dev.name} ({DEV_PATH})")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    threshold = 128
    handler   = 128
    period = 1.0 / SEND_HZ
    next_send = time.monotonic()

    print(f"sending UDP to {ESP_IP}:{ESP_PORT} ({SEND_HZ} Hz)")
    try:
        while True:
            timeout = max(0, next_send - time.monotonic())
            r, _, _ = select([dev.fd], [], [], timeout)
            if r:
                for e in dev.read():
                    if e.type == ecodes.EV_ABS:
                        if e.code == LY_AXIS:
                            threshold = map_0_255(e.value, INVERT_THROTTLE)
                            print(f"LY_AXIS value: {e.value}")
                        elif e.code == RX_AXIS:
                            handler   = map_0_255(e.value, INVERT_STEERING)
                            print(f"RX_AXIS value: {e.value}")

            now = time.monotonic()
            if now >= next_send:
                pkt = f"th={threshold},hd={255 if (256 - handler) == 256 else 256 - handler}\n".encode("ascii")
                # print(pkt)
                sock.sendto(pkt, (ESP_IP, ESP_PORT))
                next_send += period
                if next_send < now - 0.5*period:
                    next_send = now + period
    except KeyboardInterrupt:
        pass
    finally:
        try: sock.sendto(b"th=128,hd=128\n", (ESP_IP, ESP_PORT))
        except:
            print("UDP sned failed.")
        sock.close()
        print("\Centerized car and stop server.")

if __name__ == "__main__":
    main()  # run in sudo
