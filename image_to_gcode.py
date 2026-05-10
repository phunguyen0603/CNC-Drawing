"""
=============================================================================
IMAGE TO G-CODE CONVERTER - CNC Drawing Robot (STM32 + Stepper + Servo)
=============================================================================
Pipeline: Image → Grayscale → Threshold → Edge Detection → Contours → 
          Optimize Path → Generate G-code

Phần cứng:
  - STM32 + 2x Stepper (DVD) + 2x A4988 + CNC Shield + 1x Servo
  - Servo Z: UP = pen up (G0), DOWN = pen down (G1)

Cấu trúc thư mục:
  images/    - Ảnh đầu vào
  output/    - File G-code xuất ra
  review/    - Ảnh preview + debug

Cách dùng:
  python image_to_gcode.py                              # Dùng ảnh mặc định
  python image_to_gcode.py --input images/star.jpg      # Chỉ định ảnh
  python image_to_gcode.py --input images/star.jpg --width 35 --height 35

Yêu cầu:
  pip install opencv-python numpy
=============================================================================
"""

import cv2
import numpy as np
import argparse
import os
import time
from math import sqrt

# =============================================================================
# CẤU HÌNH - Thay đổi theo phần cứng của bạn
# =============================================================================
class Config:
    # --- Kích thước vùng vẽ (mm) ---
    # Khổ giấy 3.8cm x 3.8cm
    BED_WIDTH_MM = 38.0
    BED_HEIGHT_MM = 38.0

    # --- Xử lý ảnh ---
    IMAGE_RESIZE = 500          # Resize ảnh về max pixel này (giảm noise)
    BLUR_KERNEL = 5             # Gaussian blur kernel size (lẻ)
    CANNY_LOW = 50              # Canny edge: ngưỡng thấp
    CANNY_HIGH = 150            # Canny edge: ngưỡng cao
    THRESHOLD_VALUE = 127       # Binary threshold (0-255)
    USE_ADAPTIVE_THRESHOLD = False  # True = adaptive, False = fixed threshold

    # --- Contour ---
    MIN_CONTOUR_LENGTH = 10     # Bỏ contour quá ngắn (pixel)
    APPROX_EPSILON = 1.0        # Độ chính xác xấp xỉ contour (pixel)
                                # Nhỏ = chi tiết hơn, Lớn = ít điểm hơn

    # --- G-code ---
    FEED_RATE = 200             # Tốc độ vẽ (mm/min) - dùng cho G1
    TRAVEL_RATE = 500           # Tốc độ di chuyển nhanh (mm/min) - dùng cho G0
    Z_UP = 5.0                  # Servo position: bút lên (mm giả lập)
    Z_DOWN = 0.0                # Servo position: bút xuống
    DECIMAL_PLACES = 2          # Số chữ số thập phân trong G-code

    # --- Tối ưu ---
    OPTIMIZE_PATH = True        # Sắp xếp contour theo nearest neighbor
    MERGE_DISTANCE = 2.0        # Khoảng cách merge contour gần nhau (pixel)


# =============================================================================
# BƯỚC 1: TIỀN XỬ LÝ ẢNH
# =============================================================================
def preprocess_image(image_path, config=Config):
    """
    Tiền xử lý ảnh: đọc → resize → grayscale → blur → threshold → edge detect.
    
    Args:
        image_path: Đường dẫn file ảnh
        config: Cấu hình xử lý
    
    Returns:
        edges: Ảnh binary chứa các cạnh (edge)
        original: Ảnh gốc đã resize
    """
    # --- 1.1: Đọc ảnh ---
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Không tìm thấy ảnh: {image_path}")
    
    print(f"[1] Đọc ảnh: {image_path}")
    print(f"    Kích thước gốc: {img.shape[1]}x{img.shape[0]} pixels")

    # --- 1.2: Resize giữ tỷ lệ ---
    h, w = img.shape[:2]
    scale = config.IMAGE_RESIZE / max(h, w)
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), 
                         interpolation=cv2.INTER_AREA)
        print(f"    Resize → {img.shape[1]}x{img.shape[0]} pixels")

    original = img.copy()

    # --- 1.3: Chuyển grayscale ---
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # --- 1.4: Làm mờ giảm noise ---
    blurred = cv2.GaussianBlur(gray, (config.BLUR_KERNEL, config.BLUR_KERNEL), 0)

    # --- 1.5: Threshold (nhị phân hóa) ---
    if config.USE_ADAPTIVE_THRESHOLD:
        binary = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )
    else:
        _, binary = cv2.threshold(blurred, config.THRESHOLD_VALUE, 255, 
                                   cv2.THRESH_BINARY_INV)

    # --- 1.6: Edge detection (Canny) ---
    edges = cv2.Canny(blurred, config.CANNY_LOW, config.CANNY_HIGH)

    print(f"    Canny edges: {np.count_nonzero(edges)} edge pixels")

    # Lưu ảnh trung gian để debug vào thư mục review/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    review_dir = os.path.join(script_dir, "review")
    os.makedirs(review_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    cv2.imwrite(os.path.join(review_dir, f"{base_name}_1_gray.png"), gray)
    cv2.imwrite(os.path.join(review_dir, f"{base_name}_2_blurred.png"), blurred)
    cv2.imwrite(os.path.join(review_dir, f"{base_name}_3_binary.png"), binary)
    cv2.imwrite(os.path.join(review_dir, f"{base_name}_4_edges.png"), edges)
    print(f"    Debug images saved to: {review_dir}/")

    return edges, original


# =============================================================================
# BƯỚC 2: TRÍCH XUẤT CONTOUR (Chuyển pixel → danh sách điểm)
# =============================================================================
def extract_contours(edges, config=Config):
    """
    Tìm contours từ ảnh edge, xấp xỉ đa giác, lọc contour ngắn.
    
    Args:
        edges: Ảnh binary (output từ Canny)
        config: Cấu hình
    
    Returns:
        contours_simplified: List các contour, mỗi contour = list [(x,y), ...]
    """
    # --- 2.1: Tìm contours ---
    contours_raw, _ = cv2.findContours(edges, cv2.RETR_LIST, 
                                        cv2.CHAIN_APPROX_NONE)
    print(f"\n[2] Tìm contours:")
    print(f"    Contours thô: {len(contours_raw)}")

    # --- 2.2: Lọc + Xấp xỉ ---
    contours_simplified = []
    for cnt in contours_raw:
        # Bỏ contour quá ngắn
        length = cv2.arcLength(cnt, closed=False)
        if length < config.MIN_CONTOUR_LENGTH:
            continue
        
        # Xấp xỉ đa giác (giảm số điểm nhưng giữ hình dạng)
        # epsilon nhỏ = nhiều điểm (chi tiết), epsilon lớn = ít điểm (thô)
        approx = cv2.approxPolyDP(cnt, config.APPROX_EPSILON, closed=False)
        
        # Chuyển từ format OpenCV [[[x,y]]] → [(x,y)]
        points = [(int(p[0][0]), int(p[0][1])) for p in approx]
        
        if len(points) >= 2:
            contours_simplified.append(points)

    print(f"    Contours sau lọc: {len(contours_simplified)}")
    total_points = sum(len(c) for c in contours_simplified)
    print(f"    Tổng số điểm: {total_points}")

    return contours_simplified


# =============================================================================
# BƯỚC 3: TỐI ƯU ĐƯỜNG ĐI (Nearest Neighbor - giảm travel time)
# =============================================================================
def optimize_path(contours, config=Config):
    """
    Sắp xếp thứ tự vẽ contours theo thuật toán Nearest Neighbor.
    Giảm thời gian di chuyển không vẽ (G0).
    
    Ý tưởng: Sau khi vẽ xong contour A, tìm contour B có điểm đầu/cuối
    gần nhất với điểm cuối của A → vẽ B tiếp.
    
    Args:
        contours: List các contour [(x,y), ...]
        config: Cấu hình
    
    Returns:
        optimized: List contour đã sắp xếp lại
    """
    if not config.OPTIMIZE_PATH or len(contours) <= 1:
        return contours

    print(f"\n[3] Tối ưu đường đi...")

    def dist(p1, p2):
        return sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

    # Nearest Neighbor Sorting
    remaining = list(range(len(contours)))
    optimized = []
    current_pos = (0, 0)  # Bắt đầu từ gốc tọa độ

    while remaining:
        best_idx = -1
        best_dist = float('inf')
        best_reversed = False

        for idx in remaining:
            cnt = contours[idx]
            # Thử cả 2 hướng: đầu→cuối hoặc cuối→đầu
            d_start = dist(current_pos, cnt[0])
            d_end = dist(current_pos, cnt[-1])

            if d_start < best_dist:
                best_dist = d_start
                best_idx = idx
                best_reversed = False
            if d_end < best_dist:
                best_dist = d_end
                best_idx = idx
                best_reversed = True

        # Lấy contour tốt nhất
        cnt = contours[best_idx]
        if best_reversed:
            cnt = list(reversed(cnt))

        optimized.append(cnt)
        current_pos = cnt[-1]
        remaining.remove(best_idx)

    # Tính tổng travel distance trước/sau
    def total_travel(contour_list):
        total = 0
        pos = (0, 0)
        for cnt in contour_list:
            total += dist(pos, cnt[0])
            pos = cnt[-1]
        return total

    before = total_travel(contours)
    after = total_travel(optimized)
    print(f"    Travel distance: {before:.1f}px → {after:.1f}px "
          f"(giảm {(1-after/before)*100:.1f}%)")

    return optimized


# =============================================================================
# BƯỚC 4: SINH G-CODE
# =============================================================================
def generate_gcode(contours, image_shape, config=Config):
    """
    Chuyển contours → G-code.
    
    Quy ước:
      G0 Xnn Ynn      → Di chuyển nhanh (không vẽ), bút đang UP
      G1 Xnn Ynn      → Vẽ đường thẳng từ vị trí hiện tại đến (X,Y)
      M3 S90 / M3 S50 → Điều khiển servo (bút lên/xuống) [tùy firmware]
    
    Trong code này dùng format đơn giản:
      G0 Xnn Ynn Zup   → Di chuyển + bút lên
      G1 Xnn Ynn Zdown → Vẽ + bút xuống
    
    Mapping tọa độ:
      pixel (0..W, 0..H) → mm (0..BED_WIDTH, 0..BED_HEIGHT)
    
    Args:
        contours: List contour đã tối ưu
        image_shape: (height, width) ảnh gốc
        config: Cấu hình
    
    Returns:
        gcode_lines: List string các lệnh G-code
    """
    print(f"\n[4] Sinh G-code...")

    img_h, img_w = image_shape[:2]
    dp = config.DECIMAL_PLACES

    # --- Uniform scale: giữ tỷ lệ ảnh, fit vào khổ giấy, căn giữa ---
    scale_x = config.BED_WIDTH_MM / img_w
    scale_y = config.BED_HEIGHT_MM / img_h
    scale = min(scale_x, scale_y)  # Chọn scale nhỏ hơn để ảnh nằm gọn trong khổ giấy

    # Kích thước thực tế của ảnh sau khi scale (mm)
    draw_w = img_w * scale
    draw_h = img_h * scale

    # Offset để căn giữa ảnh trên khổ giấy
    offset_x = (config.BED_WIDTH_MM - draw_w) / 2
    offset_y = (config.BED_HEIGHT_MM - draw_h) / 2

    print(f"    Scale: {scale:.4f} mm/px (uniform)")
    print(f"    Draw area: {draw_w:.1f}x{draw_h:.1f} mm (centered in {config.BED_WIDTH_MM}x{config.BED_HEIGHT_MM} mm)")

    def px_to_mm(x_px, y_px):
        """Chuyển pixel → mm, uniform scale + căn giữa + lật trục Y"""
        x_mm = round(x_px * scale + offset_x, dp)
        y_mm = round((img_h - y_px) * scale + offset_y, dp)
        return x_mm, y_mm

    lines = []
    
    # --- Header ---
    lines.append("; G-code generated by image_to_gcode.py")
    lines.append(f"; Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"; Bed size: {config.BED_WIDTH_MM}x{config.BED_HEIGHT_MM} mm")
    lines.append(f"; Contours: {len(contours)}")
    lines.append(f"; Total points: {sum(len(c) for c in contours)}")
    lines.append("")
    lines.append("G21        ; Unit: mm")
    lines.append("G90        ; Absolute positioning")
    lines.append(f"G0 Z{config.Z_UP}    ; Pen UP (servo)")
    lines.append(f"G0 X0 Y0   ; Home position")
    lines.append("")

    g0_count = 0
    g1_count = 0

    for i, contour in enumerate(contours):
        if len(contour) < 2:
            continue

        lines.append(f"; --- Contour {i+1}/{len(contours)} "
                     f"({len(contour)} points) ---")

        # Di chuyển đến điểm đầu (PEN UP)
        x, y = px_to_mm(*contour[0])
        lines.append(f"G0 Z{config.Z_UP}")
        lines.append(f"G0 X{x} Y{y}")
        g0_count += 1

        # Hạ bút (PEN DOWN)
        lines.append(f"G1 Z{config.Z_DOWN} F{config.FEED_RATE}")

        # Vẽ các đoạn thẳng qua từng điểm
        for point in contour[1:]:
            x, y = px_to_mm(*point)
            lines.append(f"G1 X{x} Y{y}")
            g1_count += 1

        lines.append("")  # Dòng trống giữa contours

    # --- Footer ---
    lines.append(f"G0 Z{config.Z_UP}    ; Pen UP")
    lines.append("G0 X0 Y0   ; Home")
    lines.append("M2         ; End program")

    print(f"    G0 (travel): {g0_count} lệnh")
    print(f"    G1 (draw):   {g1_count} lệnh")
    print(f"    Tổng:        {len(lines)} dòng")

    return lines


# =============================================================================
# BƯỚC 5: LƯU FILE + VISUALIZATION
# =============================================================================
def save_gcode(lines, output_path):
    """Lưu G-code ra file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    file_size = os.path.getsize(output_path)
    print(f"\n[5] Lưu file: {output_path}")
    print(f"    Kích thước: {file_size:,} bytes")


def visualize_gcode(contours, image_shape, output_path, config=Config):
    """Vẽ preview G-code lên ảnh để kiểm tra."""
    canvas = np.ones((image_shape[0], image_shape[1], 3), dtype=np.uint8) * 255
    
    colors = [
        (0, 0, 255),    # Đỏ
        (0, 165, 255),  # Cam
        (0, 255, 0),    # Xanh lá
        (255, 0, 0),    # Xanh dương
        (255, 0, 255),  # Tím
    ]

    for i, contour in enumerate(contours):
        color = colors[i % len(colors)]
        for j in range(len(contour) - 1):
            pt1 = contour[j]
            pt2 = contour[j+1]
            cv2.line(canvas, pt1, pt2, color, 1, cv2.LINE_AA)
        # Đánh dấu điểm bắt đầu
        cv2.circle(canvas, contour[0], 3, (0, 255, 0), -1)

    cv2.imwrite(output_path, canvas)
    print(f"    Preview saved: {output_path}")


# =============================================================================
# CHECKLIST KIỂM TRA OUTPUT
# =============================================================================
def check_gcode(lines, contours, config=Config):
    """
    Kiểm tra chất lượng G-code output.
    In ra checklist để người dùng verify.
    """
    print("\n" + "="*50)
    print("CHECKLIST KIỂM TRA OUTPUT")
    print("="*50)

    # 1. File có rỗng?
    g1_lines = [l for l in lines if l.startswith("G1") and "X" in l]
    if len(g1_lines) == 0:
        print("❌ File G-code RỖNG (không có lệnh G1 vẽ)")
    else:
        print(f"✅ File có {len(g1_lines)} lệnh G1 (vẽ)")

    # 2. Quá nhiều điểm?
    total_points = sum(len(c) for c in contours)
    if total_points > 10000:
        print(f"⚠️  Quá nhiều điểm ({total_points}). Tăng APPROX_EPSILON.")
    elif total_points > 5000:
        print(f"⚠️  Nhiều điểm ({total_points}). Có thể chậm trên STM32.")
    else:
        print(f"✅ Số điểm hợp lý: {total_points}")

    # 3. Tọa độ trong phạm vi?
    out_of_bounds = False
    for line in g1_lines:
        parts = line.split()
        for p in parts:
            if p.startswith("X"):
                val = float(p[1:])
                if val < 0 or val > config.BED_WIDTH_MM:
                    out_of_bounds = True
            elif p.startswith("Y"):
                val = float(p[1:])
                if val < 0 or val > config.BED_HEIGHT_MM:
                    out_of_bounds = True
    if out_of_bounds:
        print("❌ Có tọa độ NGOÀI vùng vẽ!")
    else:
        print(f"✅ Tọa độ trong phạm vi (0-{config.BED_WIDTH_MM}mm)")

    # 4. Contour count
    print(f"✅ Số contour: {len(contours)}")

    # 5. File size
    total_chars = sum(len(l) for l in lines)
    print(f"✅ G-code size: ~{total_chars:,} chars")

    print("="*50)


# =============================================================================
# MAIN - Chạy toàn bộ pipeline
# =============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Chuyển ảnh sang G-code cho CNC Drawing Robot (STM32)")
    parser.add_argument("--input", "-i", default="images/image.jpg",
                        help="Đường dẫn ảnh đầu vào (trong thư mục images/)")
    parser.add_argument("--output", "-o", default=None,
                        help="File G-code đầu ra (mặc định: input_name.gcode)")
    parser.add_argument("--width", "-W", type=float, default=Config.BED_WIDTH_MM,
                        help=f"Chiều rộng vùng vẽ mm (default: {Config.BED_WIDTH_MM})")
    parser.add_argument("--height", "-H", type=float, default=Config.BED_HEIGHT_MM,
                        help=f"Chiều cao vùng vẽ mm (default: {Config.BED_HEIGHT_MM})")
    parser.add_argument("--epsilon", "-e", type=float, default=Config.APPROX_EPSILON,
                        help=f"Đơn giản hóa contour (default: {Config.APPROX_EPSILON})")
    parser.add_argument("--canny-low", type=int, default=Config.CANNY_LOW,
                        help=f"Canny low threshold (default: {Config.CANNY_LOW})")
    parser.add_argument("--canny-high", type=int, default=Config.CANNY_HIGH,
                        help=f"Canny high threshold (default: {Config.CANNY_HIGH})")

    args = parser.parse_args()

    # Cập nhật config từ arguments
    Config.BED_WIDTH_MM = args.width
    Config.BED_HEIGHT_MM = args.height
    Config.APPROX_EPSILON = args.epsilon
    Config.CANNY_LOW = args.canny_low
    Config.CANNY_HIGH = args.canny_high

    # Tạo thư mục output và review nếu chưa có
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")
    review_dir = os.path.join(script_dir, "review")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(review_dir, exist_ok=True)

    # Xác định output path: output/<tên ảnh>.gcode
    input_basename = os.path.splitext(os.path.basename(args.input))[0]
    if args.output is None:
        output_path = os.path.join(output_dir, input_basename + ".gcode")
    else:
        output_path = args.output

    print("=" * 60)
    print("  IMAGE TO G-CODE CONVERTER - CNC Drawing Robot")
    print("=" * 60)

    # === PIPELINE ===
    # Bước 1: Tiền xử lý
    edges, original = preprocess_image(args.input)

    # Bước 2: Trích xuất contours
    contours = extract_contours(edges)

    # Bước 3: Tối ưu đường đi
    contours = optimize_path(contours)

    # Bước 4: Sinh G-code
    gcode = generate_gcode(contours, original.shape)

    # Bước 5: Lưu file
    save_gcode(gcode, output_path)

    # Preview → review/<tên ảnh>_preview.png
    preview_path = os.path.join(review_dir, input_basename + "_preview.png")
    visualize_gcode(contours, original.shape, preview_path)

    # Checklist
    check_gcode(gcode, contours)

    print(f"\n✅ Hoàn tất! File G-code: {output_path}")


if __name__ == "__main__":
    main()
