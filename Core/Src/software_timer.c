/*
 * software_timer.c
 *
 *  Created on: Oct 11, 2025
 *      Author: minhp
 */

#include "software_timer.h"

int timer_counter[MAX_TIMER];
int timer_flag[MAX_TIMER];

void setTimer(int index, int duration) {
	timer_counter[index] = duration / TIMER_CYCLE;
    timer_flag[index] = 0;
}

int isTimerExpired(int index) {
    if (timer_flag[index] == 1) {
        timer_flag[index] = 0;
        return 1;
    }
    return 0;
}

void timerRun(void) {
    for (int i = 0; i < MAX_TIMER; i++) {
        if (timer_counter[i] > 0) {
            timer_counter[i]--;
            if (timer_counter[i] == 0) {
                timer_flag[i] = 1;
            }
        }
    }
}
