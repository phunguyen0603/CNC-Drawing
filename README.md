# 🤖 Mini CNC Plotter - Máy Vẽ Tranh 2D Từ Ổ DVD Cũ

![STM32](https://img.shields.io/badge/MCU-STM32F103C8T6-blue)
![C/C++](https://img.shields.io/badge/Language-C%2FC%2B%2B-orange)
![Python](https://img.shields.io/badge/Language-Python-yellow)
![Status](https://img.shields.io/badge/Status-In_Progress-brightgreen)

> **Dự án xây dựng một hệ thống máy vẽ 2D (CNC Plotter) chi phí thấp, tận dụng cơ cấu cơ khí từ ổ đĩa DVD cũ. Hệ thống được điều khiển bởi vi điều khiển STM32 và phần mềm xử lý ảnh trên máy tính.**

<img src="image.jpg" width="600" alt="Toàn cảnh CNC Drawing">

---

## 📑 Mục lục
- [Giới thiệu dự án](#-giới-thiệu-dự-án)
- [Tính năng nổi bật](#-tính-năng-nổi-bật)
- [Cấu trúc hệ thống](#-cấu-trúc-hệ-thống)
- [Danh sách linh kiện (Hardware)](#-danh-sách-linh-kiện)
- [Video Demo](#-video-demo)
- [Phân công công việc nhóm](#-phân-công-công-việc)

---

## 🎯 Giới thiệu dự án
Dự án này là sự kết hợp giữa Xử lý ảnh, Truyền thông Serial và Điều khiển chuyển động (Motion Control). Hệ thống nhận đầu vào là một bức ảnh số (Raster), xử lý thành các đường nét (Vector), xuất ra mã G-code và gửi xuống vi điều khiển STM32 để điều khiển các động cơ bước vẽ lại bức tranh đó ra giấy.

## ✨ Tính năng nổi bật
* **Chuyển đổi Ảnh sang G-code:** Tự động tách viền và nội suy đường đi từ ảnh đầu vào.
* **Handshaking Protocol:** Giao thức giao tiếp UART ổn định giữa PC và STM32 (Send - Wait "OK" - Send).
* **Thuật toán Bresenham:** Tính toán nội suy tuyến tính giúp 2 động cơ bước phối hợp mượt mà để vẽ các đường chéo không bị răng cưa.
* **Microstepping 1/16:** Sử dụng Driver A4988 với cấu hình vi bước, giúp tăng độ mịn của nét vẽ và giảm tiếng ồn động cơ.

---

## 🧠 Cấu trúc hệ thống
Dự án được chia làm 3 tầng (Layers) hoạt động độc lập và song song:

1. **High-Level (PC - Python):** Xử lý hình ảnh (OpenCV/Inkscape), tạo file `.nc` (G-code) và truyền dữ liệu qua cổng Serial.
2. **Middle-Level (STM32 - Parser):** Tiếp nhận chuỗi ký tự qua UART, bóc tách dữ liệu (Parser) thành các tọa độ X, Y và lệnh nâng/hạ bút.
3. **Low-Level (STM32 - Motion Control):** Sử dụng Hardware Timer ngắt để chạy thuật toán điều khiển động cơ bước và phát xung PWM điều khiển Servo.

[Chèn 1 tấm ảnh Sơ đồ khối hệ thống (Block Diagram) tại đây]

---

## 🛠 Danh sách linh kiện
| Linh kiện | Chức năng | Số lượng |
| :--- | :--- | :--- |
| **STM32F103C8T6 (Blue Pill)** | Vi điều khiển trung tâm | 1 |
| **CNC Shield V3** | Mạch đệm kết nối phần cứng | 1 |
| **A4988 Stepper Driver** | Điều khiển động cơ bước (chỉnh Vref < 0.2V) | 2 |
| **Động cơ bước đĩa quang (DVD)**| Trục X (Bàn vẽ) và Trục Y (Bút vẽ) | 2 |
| **Servo SG90** | Cơ cấu nâng/hạ bút (Z-axis) | 1 |
| **Mạch hạ áp LM2596** | Hạ 12V xuống 5V nuôi hệ thống Logic | 1 |
| **Nguồn PD Trigger 12V** | Cấp nguồn chính cho CNC Shield | 1 |

[Chèn 1 tấm ảnh chụp cận cảnh mạch điện / cách đi dây tại đây]

---

## 🎬 Video Demo

[![Mini CNC Plotter Demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/0.jpg)](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)

*(Click vào ảnh trên để xem video quá trình Robot hoạt động trên YouTube)*

---

## 👥 Phân công công việc (Team Members)
* **Nguyễn Hoàng Minh Phú (Software & Image Processing):** Phát triển GUI Python, xử lý ảnh và thuật toán gửi nhận G-code.
* **Hà Trọng Sơn (Firmware & G-code Parser):** Lập trình bộ dịch G-code trên STM32, quản lý luồng UART.
* **Lê Thanh Phong (Hardware & Motion Control):** Thiết kế khung cơ khí, đấu nối mạch điện, lập trình thuật toán nội suy Bresenham và điều khiển tín hiệu PWM/Timer.

---
*Dự án được thực hiện nhằm mục đích nghiên cứu và học tập.*
