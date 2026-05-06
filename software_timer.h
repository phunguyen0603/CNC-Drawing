/*
 * software_timer.h
 *
 *  Created on: Oct 11, 2025
 *      Author: minhp
 */

#ifndef INC_SOFTWARE_TIMER_H_
#define INC_SOFTWARE_TIMER_H_

#define MAX_TIMER 10
#define TIMER_CYCLE 10

void setTimer(int index, int duration);
int isTimerExpired(int index);
void timerRun(void);

#endif /* INC_SOFTWARE_TIMER_H_ */
