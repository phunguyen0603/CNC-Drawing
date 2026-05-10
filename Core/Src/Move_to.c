/*
 * Move_to.c
 *
 *  Created on: 9 thg 5, 2026
 *      Author: Thanh Phong
 */

#include "Move_to.h"
#include "main.h"
#include "software_timer.h"


extern float current_X; //Vị trí hiện tại
extern float current_Y;
int MAX_X_STEPS = 4150; //Step max mà motor step có thể đi
int MAX_Y_STEPS = 4150;
int current_step_X = 0; // Biến theo dõi vị trí hiện tại theo đơn vị số bước
int current_step_Y = 0;


//===========================================
// Di chuyển TRỤC X (Step: PA0 | Dir: PA1)
// Chiều dài max trục x vẽ được là 3.8cm và 4150 step
// ==========================================
void Move_X_To(int target_step) {
    // 1. CHẶN Ranh Giới (Soft Limit)
    if (target_step > MAX_X_STEPS) {
        target_step = MAX_X_STEPS; // Nếu mày lỡ ra lệnh quá đà, nó ép về Max an toàn
    }
    if (target_step < 0) {
        target_step = 0; // Không cho chạy âm (lùi quá gốc 0)
    }

    // 2. Tính xem cần đi bao nhiêu bước nữa
    int steps_to_move = target_step - current_step_X;

    // 3. Quyết định chiều chạy
    if (steps_to_move > 0) {
        // Chạy TIẾN
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_1, GPIO_PIN_SET); // Set chiều tiến
    } else if (steps_to_move < 0) {
        // Chạy LÙI
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_1, GPIO_PIN_RESET); // Set chiều lùi
        steps_to_move = -steps_to_move; // Đổi số âm thành số dương để bỏ vào vòng for
    } else {
        return; // Đang ở đúng chỗ rồi, không cần chạy
    }

    // 4. Bơm xung cho motor chạy
    for(int i = 0; i < steps_to_move; i++) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_0, GPIO_PIN_SET);
        for(int j=0; j<8000; j++) { __NOP(); }
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_0, GPIO_PIN_RESET);
        for(int j=0; j<8000; j++) { __NOP(); }
    }

    // 5. Cập nhật lại vị trí hiện tại
    current_step_X = target_step;
}



//==========================================
// TEST TRỤC Y (Step: PA2 | Dir: PA3)
// Chiều dài max trục Y vẽ được là 3.8cm và 4150 step
// ==========================================


void Move_Y_To(int target_step) {
    // 1. CHẶN Ranh Giới (Soft Limit)
    if (target_step > MAX_Y_STEPS) {
        target_step = MAX_Y_STEPS; // Nếu lố thì ép về kịch khung an toàn
    }
    if (target_step < 0) {
        target_step = 0; // Không cho chạy lùi qua vạch xuất phát
    }

    // 2. Tính xem cần đi bao nhiêu bước nữa
    int steps_to_move = target_step - current_step_Y;

    // 3. Quyết định chiều chạy của trục Y (Sử dụng chân PA3)
    if (steps_to_move > 0) {
        // Chạy TIẾN
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_SET);
    } else if (steps_to_move < 0) {
        // Chạy LÙI
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_RESET);
        steps_to_move = -steps_to_move; // Đổi số âm thành số dương để bỏ vào vòng for
    } else {
        return; // Đang ở đúng chỗ rồi, không làm gì cả
    }

    // 4. Bơm xung cho motor Y chạy (Sử dụng chân PA2)
    for(int i = 0; i < steps_to_move; i++) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_2, GPIO_PIN_SET);
        for(int j=0; j<8000; j++) { __NOP(); } // Tốc độ giống trục X để chạy đồng bộ
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_2, GPIO_PIN_RESET);
        for(int j=0; j<8000; j++) { __NOP(); }
    }

    // 5. Cập nhật lại vị trí hiện tại
    current_step_Y = target_step;
}

void Move_to(int target_X, int target_Y){ // Đầu vào là đơn vi step chứ không phải tọa độ
	if(target_X > MAX_X_STEPS) target_X = MAX_X_STEPS;
	if(target_X < 0) target_X = 0;

	if(target_Y > MAX_Y_STEPS) target_Y = MAX_Y_STEPS;
    if(target_Y < 0) target_Y = 0;

    int dx = abs(target_X - current_step_X);
    int dy = abs(target_Y - current_step_Y);

    int sx = (current_step_X < target_X) ? 1 : -1; // Hướng di chuyển trục X (1: tiến, -1: lùi)
    int sy = (current_step_Y < target_Y) ? 1 : -1;

    if (sx == 1) HAL_GPIO_WritePin(GPIOA, GPIO_PIN_1, GPIO_PIN_SET);
    else HAL_GPIO_WritePin(GPIOA, GPIO_PIN_1, GPIO_PIN_RESET);
    
    if (sy == 1) HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_SET);
    else HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3, GPIO_PIN_RESET);

    int err = (dx > dy ? dx : -dy) / 2;
    int e2;

    while (1) {
        // --- 1. ĐIỀU KIỆN DỪNG ---
        // Nếu vị trí hiện tại đã bằng chính xác vị trí đích của cả X và Y thì ngưng
        if (current_step_X == target_x && current_step_Y == target_y) break;

        e2 = err; // Lưu sai số hiện tại vào biến tạm
        
        // Tạo 2 cái "cờ" để đánh dấu xem nhịp này X có bước không, Y có bước không
        int step_x_made = 0; 
        int step_y_made = 0;

        // --- 2. QUYẾT ĐỊNH BƯỚC ĐI DỰA TRÊN SAI SỐ ---
        // Nếu sai số đang nghiêng về trục X, cho X nhích 1 bước và bù trừ sai số
        if (e2 > -dx) { 
            err -= dy; 
            current_step_X += sx; // Cập nhật vị trí X (cộng 1 hoặc trừ 1 tùy hướng)
            step_x_made = 1;      // Dựng cờ báo hiệu X sẽ bước
        }
        
        // Nếu sai số đang nghiêng về trục Y, cho Y nhích 1 bước và bù trừ sai số
        if (e2 < dy) { 
            err += dx; 
            current_step_Y += sy; // Cập nhật vị trí Y
            step_y_made = 1;      // Dựng cờ báo hiệu Y sẽ bước
        }

        // --- 3. BƠM ĐIỆN VÀO CHÂN STEP ---
        // Nhìn vào 2 cái cờ, thằng nào có cờ thì kéo chân STEP lên HIGH
        if (step_x_made) HAL_GPIO_WritePin(GPIOA, GPIO_PIN_0, GPIO_PIN_SET); // X dùng PA0
        if (step_y_made) HAL_GPIO_WritePin(GPIOA, GPIO_PIN_2, GPIO_PIN_SET); // Y dùng PA2

        // Nghỉ một chút để lõi nam châm trong motor kịp từ hóa
        for(int j=0; j<8000; j++) { __NOP(); } 

        // Kéo chân STEP xuống LOW để hoàn thành 1 chu kỳ xung
        if (step_x_made) HAL_GPIO_WritePin(GPIOA, GPIO_PIN_0, GPIO_PIN_RESET);
        if (step_y_made) HAL_GPIO_WritePin(GPIOA, GPIO_PIN_2, GPIO_PIN_RESET);

        // Nghỉ thêm một nhịp nữa trước khi lặp lại vòng lặp
        for(int j=0; j<8000; j++) { __NOP(); } 
    }
}
