---
上層:
  - "[[資訊專題(一)]]"
---

# 題目概述
使用XR技術即時監看並透過設備遠端操控一台實體小車，  透過後端運算，在用戶XR介面中實時呈現儀表板、油量、轉速、車速等實時UI渲染頁面。  
用戶能透過 XR 裝置進行沉浸式的駕駛模擬，即時接收車輛回傳的感測數據，並在 XR 介面上完成油門、方向、煞車等操作。

1. 結合AI運算在UI介面中渲染導航、避障提示、車道引導等功能。
2. ~~透過AI運算實現自動駕駛。~~
3. 透過外設多部相機實現多視角切換。
![[Pasted image 20250824140629.jpg]]

---
# 步驟規劃
1. 改裝組合RCcar，可以使用電腦輸出指令進行控制與操作
2. 裝上攝影機與感測器，並在電腦上可以看到畫面與數據，完成避障提示
3. 將輸出指令與攝影機畫面延伸到XR裝置上，完成UI繪製

# 目標規劃
以 XR 沉浸式介面遠端操控實體小車，於 XR UI 即時顯示「車速、轉速（馬達 RPM/車輪轉速）、電量、IMU 姿態」等儀表資訊，並提供**避障提示**與**最小化延遲**之遠端駕駛體驗。

# 流程規劃
![[XR流程規劃.excalidraw]]
---
擱置
## 量化成功指標
- [ ] 影像「玻璃到玻璃」延遲 ≤ **150 ms**（720p@30fps 基準）。
- [ ] 控制命令迴路延遲（XR→車輪）≤ **80 ms**（同網域 Wi-Fi 環境）。
- [ ] 儀表更新頻率 ≥ **20 Hz**（遙測 20–50 Hz；影像 30 fps）。
- [ ] 避障：室內樁桶測道「安全通過成功率 ≥ 90%」、最小通過間隙 ≥ 車體寬 + 20 cm。
- [ ] 安全：通訊中斷 **< 200 ms** 內自動煞停，E-Stop 實體按鈕可立即切電。

# 系統架構
##  資料流
- 視訊：車端攝影機 →（硬體編碼 H.264）→ WebRTC → XR 裝置顯示
- 遙測（Telemetry）：車端守護程式 → MQTT Publish → 伺服器 Broker → XR 客戶端 Subscribe
- 控制（Teleop）：XR 客戶端 → MQTT Publish → 車端橋接程式 → UART → ESP32 → 馬達/舵機
- 時基：NTP 對時，訊息皆含時間戳
## 分層模組
1. **操控端（Unity/Quest）**
    - WebRTC 播放器（Unity Render Streaming 或 MixedReality-WebRTC 套件）
    - MQTT over WebSocket（控制與訂閱遙測）
    - HUD 儀表（速度、RPM、電量、IMU 姿態、連線狀態）
    - 避障提示 Overlay（方向箭頭/色塊高亮）
    - 輸入映射：油門（Trigger/Thumbstick）、轉向（Thumbstick X）、煞車（Grip/按鍵）

2. **伺服端（雲或本地 NUC/筆電）**
    - MQTT Broker（Mosquitto/EMQX）
    - WebRTC 訊號伺服（可與 Broker 同機）
    - 日誌與資料庫（InfluxDB/TimescaleDB）＋ Grafana 觀測板（非必要但加分）
    - 使用者與車輛身分、Topic ACL（含 Token 驗證）

3. **車端（Companion + MCU）**
    - **Companion（Raspberry Pi 4/5 或 Orange Pi 5）**：
        - 影像串流：GStreamer + WebRTC，H.264 硬編碼
        - Teleop 橋接：MQTT Sub 命令 → UART → ESP32
        - Telemetry 守護：從 ESP32 拉資料 + 直接讀相機 FPS/CPU 溫度 → MQTT Pub
        - 避障（先超聲波/ToF，後續可加輕量 YOLO / ArUco 導引）

    - **ESP32（微控板，硬即時層）**：
        - 馬達/ESC 控制（PWM）與舵機轉向（PWM）
        - 編碼器/霍爾回授計速、PID 保速
        - IMU（ICM-20948/MPU-6050）讀值融合
        - 監測電壓/電流（分壓 + INA219）推估 SOC
        - 看門狗 + 失聯保護（無命令 > 200 ms → 漸進煞停）
        - E-Stop 腳位控制繼電器，硬切 ESC 供電

# 硬體設計
## 車體與動力
- 1/10 RC 車底盤（含差速與轉向機構）
- 無刷馬達 + ESC（≥30A）、金屬齒比更耐操
- 舵機（≥10–15 kg·cm 扭力）
- 電池：2S/3S LiPo（配平衡充電器）
- DC-DC：12→5V/3.3V 轉換供 Companion/ESP32/感測器
- **E-Stop**：繼電器或 MOSFET 切 ESC 主電，外加實體紅色蘑菇頭按鈕

## 感測器
- 車輪編碼器（光編/磁編）或直接讀馬達 RPM（若馬達支援）
- IMU（ICM-20948/MPU-6050）
- 超聲波/ToF 測距（HC-SR04 / VL53L0X，前方左右三顆起跳）
- 相機：Raspberry Pi Cam v3 或 UVC USB 攝影機（廣角 120–150° 佳）

## 計算與通訊
- Companion：Raspberry Pi 4/5（Wi-Fi 5/BT，或 USB-LTE 網卡做戶外）
- 微控：ESP32 DevKit（UART 與 Companion 溝通）
- 路由：Wi-Fi 5/6 AP（實驗室自備，確保低干擾）

**預估成本（不含 XR 頭顯）**：NT$ 15,000–25,000（依底盤/相機/單板電腦選擇浮動）

# 軟體設計重點
## XR（Unity/Quest）
- 框架：XR Interaction Toolkit + Oculus Integration（沿用你現有的 Sample Rig）
- 視訊：WebRTC 播放器疊於駕駛座視角（第一人稱），再覆蓋 HUD Canvas
- UI：時速表（車輪半徑×編碼器 RPM）、「擬 RPM」（馬達或輪速換算）、SOC 電量、姿態條、網路 RTT、失聯倒數
- 融合：Exponential Moving Average + 可調低通，避免 HUD 抖動
- 安全 UI：失聯（>200 ms）強制顯示「BRAKE HOLD」、命令頻率掉落警告
    
## 伺服端
- Auth：XR 啟動時以 Token（JWT）向 Signal 伺服與 MQTT Broker 換取臨時憑證
- 儲存：InfluxDB（字段：speed,rpm,battery,imu,temp,mode,estop）
- 可觀測：Grafana Dashboard（即時看延遲、丟包、CPU）

## 車端 Companion（Linux）
- Systemd 服務三個：`teleop-bridge`、`telemetryd`、`webrtc-streamer`
- `teleop-bridge`：MQTT Sub `/car/{id}/cmd` → 解析 → UART 丟到 ESP32（50 Hz）
- `telemetryd`：整合 ESP32 回傳、相機 FPS、板卡溫度 → MQTT Pub（20–50 Hz）
- `webrtc-streamer`：Camera → H.264 硬編碼 → WebRTC（DTLS/SRTP）
- 可選：OpenCV 輕量偵測（ArUco 導引/色塊障礙，先作提示，不直接自駕）

## ESP32（Firmware）
- UART 通訊（115200–921600）：命令與遙測雙向
- 控制迴圈：1 kHz 內部，外部命令 50 Hz；PID 車速；轉向限幅與加速度限制
- 供電監控：電壓閾值多段（低電→限速、極低電→強制返航/停車）
- 中斷/失聯：`last_cmd_age_ms > 200` → 線性降油門至 0 → 拉煞車
- E-Stop 腳：高/低觸發繼電器；啟動時預設斷電（Fail-safe）

# 通訊協定（MQTT Topic 與 Payload 範例）

- car/{id}/telemetry（20–50 Hz）
```json
{
  "ts": 1734892345123,
  "speed_mps": 1.82,
  "wheel_rpm": 210,
  "motor_rpm": 3150,
  "soc": 0.67,
  "voltage": 7.61,
  "imu": {"roll": 1.2, "pitch": -0.8, "yaw": 35.1},
  "temp_c": 54.3,
  "link_rssi": -51,
  "mode": "MANUAL",
  "estop": false
}
```

- car/{id}/cmd（30–50 Hz）
```json
{
  "ts": 1734892345107,
  "throttle": 0.32,   // -1..1 (若支援倒車)
  "steer": -0.15,     // -1..1 左負右正
  "brake": 0.0,       // 0..1
  "ui_profile": "LOW_LATENCY"
}
```

- car/{id}/obstacle（事件型）
```json
{
	"ts": 1734892345200,
	"type": "front",
	"distance_m": 0.85,
	"severity": "warn"
}
```

- car/{id}/health（5–10 秒一次）
```json
{
	"ts": 1734892345000,
	"cpu": 0.43,
	"mem": 0.62,
	"camera_fps": 30
}
```

# 驗證與量測方法
- **影像延遲**：LED 閃爍器 + 高幀率錄影量測「現場→XR畫面」幀差
- **控制迴路延遲**：XR 發送方同時打時間戳，車端反回 Echo，計算 RTT/單向
- **避障測試**：三種場景（直線、S 彎、窄門）各 10 次，記錄碰撞/急停次數
- **穩定性**：連續 30 分鐘運轉，溫度/丟包率門檻監控

# 風險與備援
- **影像延遲過高**：降解析度到 720p/480p、關閉過重影像後處理、固定 30fps；Wi-Fi 改用 5GHz、專用 AP；必要時 RTSP 作 Plan-B（較易搭建）。
- **丟包抖動**：WebRTC 啟用低延遲模式（UDP/SRTP）、關 FEC/強化 Jitter Buffer；MQTT QOS 0~1 視需求調整。
- **失聯**：ESP32 200 ms 內自煞停；Companion 心跳失敗觸發 E-Stop。
- **電量驟降**：低電限速與漸停；設 SOC 門檻；準備備用電池。
- **硬體損壞**：易損件（舵機/齒輪/螺絲/感測器）備品 ×1。
- **場地安全**：劃定測試區、速限（例：≤ 2 m/s）、周界防護、第二操作者監看。

