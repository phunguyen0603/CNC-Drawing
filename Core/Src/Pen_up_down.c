#include "main.h"
extern TIM_HandleTypeDef htim1;

void Pen_up_down(uint8_t lift){
	if (lift == 1){
		// Nâng bút
		__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 700);
	}
	else {
		// Hạ bút
		__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 500);
	}
	HAL_Delay(200);
}
