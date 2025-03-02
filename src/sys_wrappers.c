#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <termios.h>

// Wrapper functions with unique names that won't conflict
int serial_open(const char *path, int flags)
{
    return open(path, flags);
}

int serial_close(int fd)
{
    return close(fd);
}

ssize_t serial_read(int fd, void *buf, size_t count)
{
    return read(fd, buf, count);
}

ssize_t serial_write(int fd, const void *buf, size_t count)
{
    return write(fd, buf, count);
}

int serial_ioctl(int fd, unsigned long request, void *arg)
{
    return ioctl(fd, request, arg);
}

// Terminal-specific functions
int serial_tcgetattr(int fd, struct termios *termios_p)
{
    return tcgetattr(fd, termios_p);
}

int serial_tcsetattr(int fd, int optional_actions, const struct termios *termios_p)
{
    return tcsetattr(fd, optional_actions, termios_p);
}

int serial_tcflush(int fd, int queue_selector)
{
    return tcflush(fd, queue_selector);
}

int serial_cfsetispeed(struct termios *termios_p, speed_t speed)
{
    return cfsetispeed(termios_p, speed);
}

int serial_cfsetospeed(struct termios *termios_p, speed_t speed)
{
    return cfsetospeed(termios_p, speed);
}