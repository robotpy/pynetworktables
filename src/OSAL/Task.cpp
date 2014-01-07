
#include "Task.h"

NTTask::NTTask(const char* name, FUNCPTR function, INT32 priority, UINT32 stackSize)
{
    m_function = function;
}

NTTask::~NTTask()
{
}

bool NTTask::IsReady()
{
    return true;
}


#ifdef WIN32

    #include <Windows.h>

    bool NTTask::Start(void * arg0)
    {
        HANDLE thread = CreateThread(NULL, 0, (LPTHREAD_START_ROUTINE)m_function, arg0, 0, NULL);
        if (!thread)
            return false;
            
        CloseHandle(thread);
        return true;
    }

#else

    #include <pthread.h>
    
    struct tmp_arg_t
    {
        FUNCPTR fn;
        void * arg0;
    };
    
    static void * trampoline(void * arg)
    {
        tmp_arg_t * tmp = (tmp_arg_t*)arg;
        tmp->fn(tmp->arg0);        
        delete tmp;
        
        return NULL;
    }

    bool NTTask::Start(void * arg0)
    {
        pthread_t thread;
        tmp_arg_t * tmp = new tmp_arg_t;
        
        tmp->fn = m_function;
        tmp->arg0 = arg0;
        
        if (pthread_create(&thread, NULL, trampoline, tmp))
        {
            return false;
        }
        
        return true;
    }

#endif
