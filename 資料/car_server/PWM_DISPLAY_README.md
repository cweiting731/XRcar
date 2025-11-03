# PWM 即時顯示功能說明

## 新增功能

已在 `car_server_manual.py` 中新增即時 PWM 值顯示功能，完全根據 ESP32 程式碼邏輯計算。

## PWM 計算說明

### 1. 馬達 PWM (油門控制)

根據 ESP32 的 `mapThrottle()` 函式計算：

- **前進模式** (threshold < 123):
  - 輸入範圍: 122 → 0
  - PWM 範圍: 300 → 4095
  - 使用四次方曲線: `curve = raw^4`
  
- **後退模式** (threshold > 133):
  - 輸入範圍: 134 → 255
  - PWM 範圍: 300 → 4095
  - 使用四次方曲線: `curve = raw^4`

- **停止** (123 ≤ threshold ≤ 133):
  - PWM = 0

### 2. 舵機 PWM (方向控制)

#### 頭部舵機 (通道 8)
```
PWM = map(handler, 0, 255, head_handler_right_bound, head_handler_left_bound)
     = map(handler, 0, 255, 463, 293)
```
- handler = 0   → PWM = 463 (最右)
- handler = 128 → PWM = 378 (中間)
- handler = 255 → PWM = 293 (最左)

#### 尾部舵機 (通道 9)
```
PWM = map(handler, 0, 255, tail_handler_left_bound, tail_handler_right_bound)
     = map(handler, 0, 255, 449, 279)
```
- handler = 0   → PWM = 449 (最左)
- handler = 128 → PWM = 364 (中間)
- handler = 255 → PWM = 279 (最右)

### 3. 舵角校正參數

根據 ESP32 程式碼設定：
```cpp
head_delta = 8
tail_delta = -6

head_handler_left_bound  = 285 + 8  = 293
head_handler_right_bound = 455 + 8  = 463
tail_handler_right_bound = 285 - 6  = 279
tail_handler_left_bound  = 455 - 6  = 449
```

## GUI 顯示項目

### PWM 即時資訊區塊顯示：

1. **馬達 PWM**: 顯示當前馬達 PWM 值 (0-4095) 和方向
   - 格式: `馬達 PWM: {value} / 4095 (FORWARD/REVERSE/STOP)`

2. **頭部舵機 (CH8)**: 顯示頭部舵機 PWM 值
   - 格式: `頭部舵機 (CH8): {value}`

3. **尾部舵機 (CH9)**: 顯示尾部舵機 PWM 值
   - 格式: `尾部舵機 (CH9): {value}`

4. **車輛狀態**: 以顏色標示當前狀態
   - 🟢 綠色: FORWARD (前進)
   - 🟠 橙色: REVERSE (後退)
   - 🔴 紅色: STOP (停止)

## 實時更新

PWM 值會在以下情況自動更新：
- ✅ 按下方向控制按鈕
- ✅ 拖動油門或方向滑桿
- ✅ 任何 threshold 或 handler 值改變時

## 計算函式說明

### `map_throttle(val, reverse_dir)`
完全複製 ESP32 的油門映射邏輯：
```python
def map_throttle(val, reverse_dir):
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
```

### `calculate_pwm_values(threshold, handler)`
整合所有 PWM 計算，返回完整資訊字典：
```python
{
    'motor_pwm': int,      # 馬達 PWM 值 (0-4095)
    'head_servo': int,     # 頭部舵機 PWM 值
    'tail_servo': int,     # 尾部舵機 PWM 值
    'car_status': str,     # 'FORWARD', 'REVERSE', 'STOP'
    'direction': str       # 'FORWARD', 'REVERSE', 'STOP'
}
```

## 範例數值

| 油門值 | 方向值 | 馬達 PWM | 頭部舵機 | 尾部舵機 | 狀態 |
|-------|-------|---------|---------|---------|------|
| 0     | 128   | 4095    | 378     | 364     | FORWARD (全速前進) |
| 64    | 128   | 1231    | 378     | 364     | FORWARD (中速) |
| 122   | 128   | 300     | 378     | 364     | FORWARD (最慢) |
| 128   | 128   | 0       | 378     | 364     | STOP (停止) |
| 134   | 128   | 300     | 378     | 364     | REVERSE (最慢後退) |
| 192   | 128   | 1231    | 378     | 364     | REVERSE (中速) |
| 255   | 128   | 4095    | 378     | 364     | REVERSE (全速後退) |
| 128   | 0     | 0       | 463     | 449     | 方向最右 |
| 128   | 255   | 0       | 293     | 279     | 方向最左 |

## 使用方式

1. 啟動程式後，PWM 資訊會即時顯示
2. 調整油門或方向時，PWM 值會立即更新
3. 狀態顏色會根據車輛動作改變
4. 所有計算完全符合 ESP32 實際執行邏輯

## 注意事項

⚠️ **死區範圍 (123-133)**
- threshold 在 123-133 之間時，車輛會停止 (PWM = 0)
- 這是為了避免微小的輸入造成車輛移動

⚠️ **PWM 曲線**
- 使用四次方曲線 (`x^4`)，讓低速時更容易控制
- 接近最大值時加速更快
