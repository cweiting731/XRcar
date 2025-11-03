import socket
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QSlider, QLabel, QGroupBox)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont

ESP_IP   = "10.30.157.12"
# ESP_IP   = "192.168.0.154"
ESP_PORT = 4000
SEND_HZ  = 15

# ESP32 舵角校正參數
HEAD_DELTA = 8
TAIL_DELTA = -6
HEAD_HANDLER_LEFT_BOUND  = 285 + HEAD_DELTA
HEAD_HANDLER_RIGHT_BOUND = 455 + HEAD_DELTA
TAIL_HANDLER_RIGHT_BOUND = 285 + TAIL_DELTA
TAIL_HANDLER_LEFT_BOUND  = 455 + TAIL_DELTA

def map_value(x, in_min, in_max, out_min, out_max):
    """Arduino map() 函式的 Python 實現"""
    return int((x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

def constrain(val, min_val, max_val):
    """Arduino constrain() 函式的 Python 實現"""
    return max(min_val, min(max_val, val))

def map_throttle(val, reverse_dir):
    """根據 ESP32 程式碼計算油門 PWM 值"""
    min_pwm = 300
    max_pwm = 4095
    
    input_min = 134.0 if reverse_dir else 122.0
    input_max = 255.0 if reverse_dir else 0.0
    
    if reverse_dir:
        raw = (val - input_min) / (input_max - input_min)
    else:
        raw = (input_min - val) / (input_min - input_max)
    
    raw = constrain(raw, 0.0, 1.0)
    curve = pow(raw, 4)
    pwm = int(min_pwm + curve * (max_pwm - min_pwm))
    return constrain(pwm, min_pwm, max_pwm)

def calculate_pwm_values(threshold, handler):
    """計算所有 PWM 值，返回字典"""
    pwm_values = {
        'motor_pwm': 0,
        'head_servo': 0,
        'tail_servo': 0,
        'car_status': 'STOP',
        'direction': 'FORWARD'
    }
    
    # 計算馬達 PWM
    if threshold > 133:
        # 後退
        pwm_values['motor_pwm'] = map_throttle(threshold, True)
        pwm_values['car_status'] = 'REVERSE'
        pwm_values['direction'] = 'REVERSE'
    elif threshold < 123:
        # 前進
        pwm_values['motor_pwm'] = map_throttle(threshold, False)
        pwm_values['car_status'] = 'FORWARD'
        pwm_values['direction'] = 'FORWARD'
    else:
        # 停止
        pwm_values['motor_pwm'] = 0
        pwm_values['car_status'] = 'STOP'
        pwm_values['direction'] = 'STOP'
    
    # 計算舵機 PWM (通道 8: 頭部, 通道 9: 尾部)
    pwm_values['head_servo'] = map_value(handler, 0, 255, HEAD_HANDLER_RIGHT_BOUND, HEAD_HANDLER_LEFT_BOUND)
    pwm_values['tail_servo'] = map_value(handler, 0, 255, TAIL_HANDLER_LEFT_BOUND, TAIL_HANDLER_RIGHT_BOUND)
    
    return pwm_values

class CarControlGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.threshold = 128  # 油門值 (0-255)
        self.handler = 128    # 方向值 (0-255)
        
        # 建立 UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # 建立定時器用於定期發送資料
        self.timer = QTimer()
        self.timer.timeout.connect(self.send_data)
        self.timer.start(int(1000 / SEND_HZ))  # 轉換為毫秒
        
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('小車遙控介面')
        self.setGeometry(100, 100, 500, 600)
        
        # 主要容器
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # 標題
        title = QLabel('ESP32 小車控制')
        title.setFont(QFont('Arial', 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)
        
        # 連線資訊
        info_label = QLabel(f'目標: {ESP_IP}:{ESP_PORT} | 頻率: {SEND_HZ} Hz')
        info_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(info_label)
        
        # 方向控制區域
        direction_group = QGroupBox('方向控制')
        direction_layout = QVBoxLayout()
        
        # 上下左右按鈕布局
        btn_layout = QVBoxLayout()
        
        # 前進按鈕
        forward_layout = QHBoxLayout()
        forward_layout.addStretch()
        self.btn_forward = QPushButton('↑\n前進')
        self.btn_forward.setMinimumSize(80, 60)
        self.btn_forward.pressed.connect(self.move_forward)
        self.btn_forward.released.connect(self.stop_throttle)
        forward_layout.addWidget(self.btn_forward)
        forward_layout.addStretch()
        btn_layout.addLayout(forward_layout)
        
        # 左轉、停止、右轉按鈕
        middle_layout = QHBoxLayout()
        self.btn_left = QPushButton('←\n左轉')
        self.btn_left.setMinimumSize(80, 60)
        self.btn_left.pressed.connect(self.turn_left)
        self.btn_left.released.connect(self.stop_steering)
        
        self.btn_stop = QPushButton('◉\n停止')
        self.btn_stop.setMinimumSize(80, 60)
        self.btn_stop.clicked.connect(self.stop_all)
        
        self.btn_right = QPushButton('→\n右轉')
        self.btn_right.setMinimumSize(80, 60)
        self.btn_right.pressed.connect(self.turn_right)
        self.btn_right.released.connect(self.stop_steering)
        
        middle_layout.addWidget(self.btn_left)
        middle_layout.addWidget(self.btn_stop)
        middle_layout.addWidget(self.btn_right)
        btn_layout.addLayout(middle_layout)
        
        # 後退按鈕
        backward_layout = QHBoxLayout()
        backward_layout.addStretch()
        self.btn_backward = QPushButton('↓\n後退')
        self.btn_backward.setMinimumSize(80, 60)
        self.btn_backward.pressed.connect(self.move_backward)
        self.btn_backward.released.connect(self.stop_throttle)
        backward_layout.addWidget(self.btn_backward)
        backward_layout.addStretch()
        btn_layout.addLayout(backward_layout)
        
        direction_layout.addLayout(btn_layout)
        direction_group.setLayout(direction_layout)
        main_layout.addWidget(direction_group)
        
        # 精細控制區域
        slider_group = QGroupBox('精細控制')
        slider_layout = QVBoxLayout()
        
        # 油門滑桿
        throttle_layout = QVBoxLayout()
        self.throttle_label = QLabel(f'油門: {self.threshold}')
        self.throttle_label.setAlignment(Qt.AlignCenter)
        throttle_layout.addWidget(self.throttle_label)
        
        self.throttle_slider = QSlider(Qt.Horizontal)
        self.throttle_slider.setMinimum(0)
        self.throttle_slider.setMaximum(255)
        self.throttle_slider.setValue(128)
        self.throttle_slider.setTickPosition(QSlider.TicksBelow)
        self.throttle_slider.setTickInterval(32)
        self.throttle_slider.valueChanged.connect(self.on_throttle_changed)
        throttle_layout.addWidget(self.throttle_slider)
        slider_layout.addLayout(throttle_layout)
        
        # 方向滑桿
        steering_layout = QVBoxLayout()
        self.steering_label = QLabel(f'方向: {self.handler}')
        self.steering_label.setAlignment(Qt.AlignCenter)
        steering_layout.addWidget(self.steering_label)
        
        self.steering_slider = QSlider(Qt.Horizontal)
        self.steering_slider.setMinimum(0)
        self.steering_slider.setMaximum(255)
        self.steering_slider.setValue(128)
        self.steering_slider.setTickPosition(QSlider.TicksBelow)
        self.steering_slider.setTickInterval(32)
        self.steering_slider.valueChanged.connect(self.on_steering_changed)
        steering_layout.addWidget(self.steering_slider)
        slider_layout.addLayout(steering_layout)
        
        slider_group.setLayout(slider_layout)
        main_layout.addWidget(slider_group)
        
        # PWM 顯示區域
        pwm_group = QGroupBox('PWM 即時資訊')
        pwm_layout = QVBoxLayout()
        
        # 馬達 PWM
        self.motor_pwm_label = QLabel('馬達 PWM: 0')
        self.motor_pwm_label.setFont(QFont('Consolas', 10))
        pwm_layout.addWidget(self.motor_pwm_label)
        
        # 舵機 PWM
        self.head_servo_label = QLabel('頭部舵機 (CH8): 0')
        self.head_servo_label.setFont(QFont('Consolas', 10))
        pwm_layout.addWidget(self.head_servo_label)
        
        self.tail_servo_label = QLabel('尾部舵機 (CH9): 0')
        self.tail_servo_label.setFont(QFont('Consolas', 10))
        pwm_layout.addWidget(self.tail_servo_label)
        
        # 車輛狀態
        self.car_status_label = QLabel('車輛狀態: STOP')
        self.car_status_label.setFont(QFont('Consolas', 10, QFont.Bold))
        pwm_layout.addWidget(self.car_status_label)
        
        pwm_group.setLayout(pwm_layout)
        main_layout.addWidget(pwm_group)
        
        # 狀態顯示
        self.status_label = QLabel('狀態: 就緒')
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        main_layout.addStretch()
        
    def move_forward(self):
        """前進"""
        self.threshold = 0
        self.throttle_slider.setValue(0)
        self.update_status('前進')
        
    def move_backward(self):
        """後退"""
        self.threshold = 255
        self.throttle_slider.setValue(255)
        self.update_status('後退')
        
    def turn_left(self):
        """左轉"""
        self.handler = 0
        self.steering_slider.setValue(0)
        self.update_status('左轉')
        
    def turn_right(self):
        """右轉"""
        self.handler = 255
        self.steering_slider.setValue(255)
        self.update_status('右轉')
        
    def stop_throttle(self):
        """停止油門"""
        self.threshold = 128
        self.throttle_slider.setValue(128)
        self.update_status('油門中立')
        
    def stop_steering(self):
        """停止轉向"""
        self.handler = 128
        self.steering_slider.setValue(128)
        self.update_status('方向中立')
        
    def stop_all(self):
        """全部停止"""
        self.threshold = 128
        self.handler = 128
        self.throttle_slider.setValue(128)
        self.steering_slider.setValue(128)
        self.update_status('停止')
        
    def on_throttle_changed(self, value):
        """油門滑桿變化"""
        self.threshold = value
        self.throttle_label.setText(f'油門: {value}')
        self.update_pwm_display()
        
    def on_steering_changed(self, value):
        """方向滑桿變化"""
        self.handler = value
        self.steering_label.setText(f'方向: {value}')
        self.update_pwm_display()
        
    def update_pwm_display(self):
        """更新 PWM 顯示"""
        pwm_info = calculate_pwm_values(self.threshold, self.handler)
        
        # 更新馬達 PWM 顯示
        self.motor_pwm_label.setText(
            f'馬達 PWM: {pwm_info["motor_pwm"]} / 4095 ({pwm_info["direction"]})'
        )
        
        # 更新舵機 PWM 顯示
        self.head_servo_label.setText(
            f'頭部舵機 (CH8): {pwm_info["head_servo"]}'
        )
        
        self.tail_servo_label.setText(
            f'尾部舵機 (CH9): {pwm_info["tail_servo"]}'
        )
        
        # 更新車輛狀態
        status_color = {
            'FORWARD': 'green',
            'REVERSE': 'orange',
            'STOP': 'red'
        }.get(pwm_info['car_status'], 'black')
        
        self.car_status_label.setText(f'車輛狀態: {pwm_info["car_status"]}')
        self.car_status_label.setStyleSheet(f'color: {status_color}; font-weight: bold;')
        
    def update_status(self, status_text):
        """更新狀態顯示"""
        self.status_label.setText(f'狀態: {status_text} | 油門={self.threshold}, 方向={self.handler}')
        self.update_pwm_display()
        
    def send_data(self):
        """定期發送資料到 ESP32"""
        try:
            # 計算反轉的 handler 值
            inverted_handler = 255 if (256 - self.handler) == 256 else 256 - self.handler
            pkt = f"th={self.threshold},hd={inverted_handler}\n".encode("ascii")
            self.sock.sendto(pkt, (ESP_IP, ESP_PORT))
        except Exception as e:
            print(f"發送失敗: {e}")
            
    def closeEvent(self, event):
        """關閉視窗時的清理工作"""
        try:
            # 發送中立指令
            self.sock.sendto(b"th=128,hd=128\n", (ESP_IP, ESP_PORT))
        except:
            print("UDP 發送失敗")
        finally:
            self.timer.stop()
            self.sock.close()
            print("已將小車置中並停止伺服器")
        event.accept()

def main():
    app = QApplication(sys.argv)
    gui = CarControlGUI()
    gui.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()