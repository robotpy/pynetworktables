
#ifndef WIN32
    #error "This file should have never been included"
#else

    // compensate for network tables unixisms... 
    #include <Windows.h>

    static inline int read(SOCKET fd, char* buffer, int count)
    {
        return recv(fd, buffer, count, 0);
    }
    
    static inline int close(SOCKET fd)
    {
        return closesocket(fd);
    }

    static inline int write(SOCKET fd, const char * buf, int nbytes)
    {
        return send(fd, buf, nbytes, 0);
    }
    
    #define errno WSAGetLastError()
    #define EWOULDBLOCK WSAEWOULDBLOCK
    
#endif

