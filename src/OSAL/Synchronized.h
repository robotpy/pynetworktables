

#ifndef OSAL_SYNCHRONIZED_H
#define OSAL_SYNCHRONIZED_H

#ifdef WIN32
    #include <Windows.h>
#else
    #include <pthread.h>
#endif


#define CRITICAL_REGION(s) { NTSynchronized _sync(s);
#define END_REGION }

class NTSynchronized;

class NTReentrantSemaphore
{
public:

    #if WIN32
        // not exactly a semaphore implementation, but this isn't what it's
        // used for anyways. 

        explicit NTReentrantSemaphore()
        {
            m_handle = CreateMutex(NULL, FALSE, NULL);
        }
        
        ~NTReentrantSemaphore() {
            
        }
        
        int take() {
            WaitForSingleObject(m_handle, INFINITE);
            return 0;
        }

        int give() {
            ReleaseMutex(m_handle);
            return 0;
        }
        
        HANDLE m_handle;
        
    #else
    
        explicit NTReentrantSemaphore()
        {
            pthread_mutexattr_t attr;
            
            pthread_mutexattr_init(&attr);
            pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
            
            pthread_mutex_init(&m_mutex, &attr);
        }
        
        ~NTReentrantSemaphore()
        {
            pthread_mutex_destroy(&m_mutex);
        }
        
        int take() {
            pthread_mutex_lock(&m_mutex);
            return 0;
        }

        int give() {
            pthread_mutex_unlock(&m_mutex);
            return 0;
        }
        
        pthread_mutex_t m_mutex;
    
    #endif
    
    
    friend class NTSynchronized;
};

class NTSynchronized
{
public:
	explicit NTSynchronized(NTReentrantSemaphore& sem)
        : m_sem(sem)
    {
        m_sem.take();
    }
    
	virtual ~NTSynchronized()
    {
        m_sem.give();
    }

    
private:
    NTReentrantSemaphore &m_sem;
};

#endif
