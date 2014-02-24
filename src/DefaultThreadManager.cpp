/*
 * DefaultThreadManger.cpp
 *
 *  Created on: Sep 21, 2012
 *      Author: Mitchell Wills
 */

#include "networktables2/util/System.h"
#include "DefaultThreadManager.h"
#include <stdio.h>


PeriodicNTThread::PeriodicNTThread(PeriodicRunnable* _r, const char* _name) : 
			name(_name), thread(new NTTask(name, (FUNCPTR)PeriodicNTThread::taskMain)), r(_r), run(true), is_running(true){
	fprintf(stdout, "Starting task: %s\n", name);
	fflush(stdout);
	thread->Start(this);
}

PeriodicNTThread::~PeriodicNTThread(){
	// do the equivalent of join() to the thread. this implementation
	// is not perfect, but at least the task will exit relatively soon.
	run = false;
	while (is_running)
		sleep_ms(1);

	delete thread;
}
int PeriodicNTThread::taskMain(PeriodicNTThread* o){//static wrapper
	return o->_taskMain();
}
int PeriodicNTThread::_taskMain(){
	try {
		while(run){
			r->run();
		}
	} catch (...) {
		is_running = false;
		fprintf(stdout, "NTTask exited with uncaught exception %s\n", name);
		fflush(stdout);
		return 1;
	}
	is_running = false;
	fprintf(stdout, "NTTask exited normally: %s\n", name);
	fflush(stdout);
	return 0;
}
void PeriodicNTThread::stop() {
	run = false;
}
bool PeriodicNTThread::isRunning() {
	return thread->IsReady();
}

NTThread* DefaultThreadManager::newBlockingPeriodicThread(PeriodicRunnable* r, const char* name) {
	return new PeriodicNTThread(r, name);
}
