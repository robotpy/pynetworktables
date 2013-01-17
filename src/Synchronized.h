

#ifndef SYNCHRONIZED_H
#define SYNCHRONIZED_H

#ifdef WIN32
    #include <Windows.h>
#else
    #error "Not implemented yet"
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
    
        #error "Not implemented yet"
    
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
