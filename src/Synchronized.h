

#ifndef SYNCHRONIZED_H
#define SYNCHRONIZED_H

#ifdef WIN32
    #include <Windows.h>
#else
    #include <pthread.h>
#endif


#define CRITICAL_REGION(s) { Synchronized _sync(s);
#define END_REGION }

class Synchronized;

class ReentrantSemaphore
{
public:

    #if WIN32
        // not exactly a semaphore implementation, but this isn't what it's
        // used for anyways. 

        explicit ReentrantSemaphore() 
        {
            m_handle = CreateMutex(NULL, FALSE, NULL);
        }
        
        ~ReentrantSemaphore() {
            
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
    
        explicit ReentrantSemaphore()
        {
            pthread_mutexattr_t attr;
            
            pthread_mutexattr_init(&attr);
            pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
            
            pthread_mutex_init(&m_mutex, &attr);
        }
        
        ~ReentrantSemaphore() 
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
    
    
    friend class Synchronized;
};

class Synchronized
{
public:
	explicit Synchronized(ReentrantSemaphore& sem)
    {
        m_sem.take();
    }
    
	virtual ~Synchronized()
    {
        m_sem.give();
    }

    
private:
    ReentrantSemaphore m_sem;
};

#endif
