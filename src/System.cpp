
#include <stdio.h>

#ifdef WIN32
    #include <Windows.h>    

    void sleep_ms(unsigned long ms)
    {
        Sleep(ms);
    }

    unsigned long currentTimeMillis()
    {
        return GetTickCount();
    }
    
#else
    #include <unistd.h>
    #include <sys/time.h>
    
    void sleep_ms(unsigned long ms)
    {
        usleep(ms*1000);
    }

    unsigned long currentTimeMillis()
    {
        struct timeval tv;
        gettimeofday(&tv, NULL);
        return tv.tv_sec*1000 + tv.tv_usec/1000;
    }

#endif

void writeWarning(const char* message)
{
	fprintf(stderr, "%s\n", message);
	fflush(stderr);
}



