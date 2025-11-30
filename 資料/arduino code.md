---
上層:
  - "[[資訊專題(一)]]"
---
```arduino=
#include <Wire.h>

#include <Adafruit_PWMServoDriver.h>

#include <WiFi.h>

#include <WiFiUdp.h>

#include "soc/soc.h"

#include "soc/rtc_cntl_reg.h"

#include "esp_camera.h"

#include "esp_http_server.h"

#define LED_PIN 4

  

#define PWDN_GPIO_NUM     32

#define RESET_GPIO_NUM    -1

#define XCLK_GPIO_NUM      0

#define SIOD_GPIO_NUM     26

#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35

#define Y8_GPIO_NUM       34

#define Y7_GPIO_NUM       39

#define Y6_GPIO_NUM       36

#define Y5_GPIO_NUM       21

#define Y4_GPIO_NUM       19

#define Y3_GPIO_NUM       18

#define Y2_GPIO_NUM        5

#define VSYNC_GPIO_NUM    25

#define HREF_GPIO_NUM     23

#define PCLK_GPIO_NUM     22

  

// ===== Wi-Fi 設定（DHCP）=====

const char *WIFI_SSID = "Vvvvvv";

const char *WIFI_PSK  = "3.1415926535";

const uint16_t UDP_PORT = 4000;

  

IPAddress ALLOW_SRC(0, 0, 0, 0); // 樹莓派 IP；若不檢查就用 IPAddress(0,0,0,0)

  

WiFiUDP Udp;

  

// ===== I2C 腳位 / 舵角校正 =====

#define I2C_SDA 1

#define I2C_SCL 3

  

int head_delta = 8;

int tail_delta = -6;

int head_handler_left_bound  = 285 + head_delta;

int head_handler_right_bound = 455 + head_delta;

int tail_handler_right_bound = 285 + tail_delta;

int tail_handler_left_bound  = 455 + tail_delta;

short carStatus = 0; // -1 reverse, 0 stop, 1 forward

  

int threshold = 128; // 0..255

int handler   = 128; // 0..255

  

unsigned long lastPacketMs = 0;

const unsigned long TIMEOUT_MS = 300;

  

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

  

void carStop();

void parseAndApply(char *s);

void forward(int value);

void reverse(int value);

int mapThrottle(int val, bool reverseDir);

void startCameraServer();

  

static esp_err_t stream_handler(httpd_req_t *req) {

    camera_fb_t *fb = NULL;

    esp_err_t res = ESP_OK;

    char part_buf[64];

    static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=frame";

    static const char* _STREAM_BOUNDARY = "\r\n--frame\r\n";

    static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

  

    res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);

  

    while (true) {

        fb = esp_camera_fb_get();

        if (!fb) {

            // Serial.println("Camera capture failed");

            res = ESP_FAIL;

            break;

        }

        size_t hlen = snprintf(part_buf, 64, _STREAM_PART, fb->len);

        res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));

        if (res == ESP_OK) res = httpd_resp_send_chunk(req, part_buf, hlen);

        if (res == ESP_OK) res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);

        esp_camera_fb_return(fb);

        if (res != ESP_OK) break;

    }

    return res;

}

  

void startCameraServer() {

    httpd_config_t config = HTTPD_DEFAULT_CONFIG();

    config.server_port = 81;

    httpd_handle_t stream_httpd = NULL;

    httpd_uri_t stream_uri = {

        .uri       = "/stream",

        .method    = HTTP_GET,

        .handler   = stream_handler,

        .user_ctx  = NULL

    };

    if (httpd_start(&stream_httpd, &config) == ESP_OK) {

        httpd_register_uri_handler(stream_httpd, &stream_uri);

        // Serial.printf("Stream ready: http://%s:81/stream\n", WiFi.localIP().toString().c_str());

    } else {

        // Serial.println("Failed to start HTTP server");

    }

}

  

void setup()

{

    WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  

    // I2C / PWM

    Wire.begin(I2C_SDA, I2C_SCL);

    pwm.begin();

    pwm.setPWMFreq(50);

  

    // wifi

    WiFi.mode(WIFI_STA);

    WiFi.setHostname("esp-car");

    WiFi.begin(WIFI_SSID, WIFI_PSK);

    while (WiFi.status() != WL_CONNECTED) {

        delay(100);

    }

  

    // camera

    camera_config_t config;

    config.ledc_channel = LEDC_CHANNEL_0;

    config.ledc_timer   = LEDC_TIMER_0;

    config.pin_d0       = Y2_GPIO_NUM;

    config.pin_d1       = Y3_GPIO_NUM;

    config.pin_d2       = Y4_GPIO_NUM;

    config.pin_d3       = Y5_GPIO_NUM;

    config.pin_d4       = Y6_GPIO_NUM;

    config.pin_d5       = Y7_GPIO_NUM;

    config.pin_d6       = Y8_GPIO_NUM;

    config.pin_d7       = Y9_GPIO_NUM;

    config.pin_xclk     = XCLK_GPIO_NUM;

    config.pin_pclk     = PCLK_GPIO_NUM;

    config.pin_vsync    = VSYNC_GPIO_NUM;

    config.pin_href     = HREF_GPIO_NUM;

    config.pin_sscb_sda = SIOD_GPIO_NUM;

    config.pin_sscb_scl = SIOC_GPIO_NUM;

    config.pin_pwdn     = PWDN_GPIO_NUM;

    config.pin_reset    = RESET_GPIO_NUM;

    config.xclk_freq_hz = 20000000;

    config.pixel_format = PIXFORMAT_JPEG;

    config.frame_size   = FRAMESIZE_VGA;   // 可改 QVGA 增 FPS

    config.jpeg_quality = 15;              // 0~63，小=高畫質

    config.fb_count     = 1;

     config.grab_mode   = CAMERA_GRAB_LATEST;

  

    if (esp_camera_init(&config) != ESP_OK) {

        while (true) delay(100);

    }

  

    startCameraServer();

  

    // Serial.begin(115200);

    // Serial.println(WiFi.localIP());

  

    Udp.begin(UDP_PORT);

    lastPacketMs = millis();

    carStop();

    pwm.setPWM(8, 0, map(128, 0, 255, head_handler_right_bound, head_handler_left_bound));

    pwm.setPWM(9, 0, map(128, 0, 255, tail_handler_left_bound, tail_handler_right_bound));

}

  

void loop()

{

    // 收 UDP

    int packetSize = Udp.parsePacket();

    if (packetSize > 0)

    {

        // 檢查來源（可選）

        if (ALLOW_SRC != IPAddress(0, 0, 0, 0) && Udp.remoteIP() != ALLOW_SRC)

        {

            while (Udp.available()) Udp.read();

        }

        else

        {

            char buf[64] = {0};

            int len = Udp.read(buf, sizeof(buf) - 1);

            if (len > 0)

            {

                buf[len] = '\0';

                // Serial.printf("%s\n", buf);

                parseAndApply(buf);

                lastPacketMs = millis();

            }

        }

    }

  

    if (millis() - lastPacketMs > TIMEOUT_MS)

    {

        carStop();

    }

}

  

void parseAndApply(char *s)

{

    int th = 128, hd = 128;

    char *p = strtok(s, ",\n\r ");

    while (p)

    {

        if (strncmp(p, "th=", 3) == 0)      th = atoi(p + 3);

        else if (strncmp(p, "hd=", 3) == 0) hd = atoi(p + 3);

        p = strtok(NULL, ",\n\r ");

    }

    th = constrain(th, 0, 255);

    hd = constrain(hd, 0, 255);

  

    threshold = th;

    handler   = hd;

  

    if (threshold > 133)

    {

        if (carStatus == 1)

        {

            carStop();

            delay(20);

        }

        reverse(mapThrottle(threshold, true));  

    }

    else if (threshold < 123)

    {

        if (carStatus == -1)

        {

            carStop();

            delay(20);

        }

        forward(mapThrottle(threshold, false));

    }

    else

    {

        carStop();

    }

  

    // 舵角（頭 8、尾 9）

    pwm.setPWM(8, 0, map(handler, 0, 255, head_handler_right_bound, head_handler_left_bound));

    // pwm.setPWM(9, 0, map(handler, 0, 255, tail_handler_right_bound, tail_handler_left_bound));

}

  

void forward(int value)

{

    pwm.setPWM(7, 0, value);

    pwm.setPWM(4, 0, value);

    pwm.setPWM(3, 0, value);

    pwm.setPWM(2, 0, value);

  

    pwm.setPWM(6, 4095, 0);

    pwm.setPWM(5, 4095, 0);

    pwm.setPWM(0, 4095, 0);

    pwm.setPWM(1, 4095, 0);

}

  

void reverse(int value)

{

    pwm.setPWM(7, 0, value);

    pwm.setPWM(4, 0, value);

    pwm.setPWM(3, 0, value);

    pwm.setPWM(2, 0, value);

  

    pwm.setPWM(6, 0, 4095);

    pwm.setPWM(5, 0, 4095);

    pwm.setPWM(0, 0, 4095);

    pwm.setPWM(1, 0, 4095);

}

  

void carStop()

{

    pwm.setPWM(7, 0, 0);

    pwm.setPWM(4, 0, 0);

    pwm.setPWM(3, 0, 0);

    pwm.setPWM(2, 0, 0);

}

  

int mapThrottle(int val, bool reverseDir) {

    int minPWM = 300;

    int maxPWM = 4095;

  

    float inputMin = reverseDir ? 134.0 : 122.0;

    float inputMax = reverseDir ? 255.0 : 0.0;

    float raw = reverseDir ? (val - inputMin) / (inputMax - inputMin)

                           : (inputMin - val) / (inputMin - inputMax);

  

    raw = constrain(raw, 0.0f, 1.0f);

  

    float curve = pow(raw, 4);

  

    int pwm = minPWM + curve * (maxPWM - minPWM);

    return constrain(pwm, minPWM, maxPWM);

}
```