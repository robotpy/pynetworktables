
#include "Task.h"
#include <Windows.h>


Task::Task(const char* name, FUNCPTR function, INT32 priority, UINT32 stackSize)
{
    m_function = function;
}

Task::~Task()
{
}

bool Task::Start(void * arg0)
{
    HANDLE thread = CreateThread(NULL, 0, (LPTHREAD_START_ROUTINE)m_function, arg0, 0, NULL);
    if (!thread)
        return false;
        
    CloseHandle(thread);
    return true;
}

bool Task::IsReady()
{
    return true;
}

