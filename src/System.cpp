
#include <stdio.h>

#ifdef WIN32
    #include <Windows.h>
#else
    #include <unistd.h>
#endif


void sleep_ms(unsigned long ms)
{
    #ifdef WIN32
        Sleep(ms);
    #else
        usleep(ms*1000);
    #endif
}

unsigned long currentTimeMillis()
{
    #ifdef WIN32
        return GetTickCount();
    #else
        struct timespec tp;
        clock_gettime(CLOCK_REALTIME,&tp);
        return tp.tv_sec*1000 + tp.tv_nsec/1000;
    #endif
}

void writeWarning(const char* message)
{
	fprintf(stderr, "%s\n", message);
	fflush(stderr);
}



