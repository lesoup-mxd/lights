from sys.ffi import external_call
from memory import UnsafePointer
from utils import StaticTuple


# Terminal control struct - define outside of libc namespace
@value
struct termios:
    var c_iflag: UInt32
    var c_oflag: UInt32
    var c_cflag: UInt32
    var c_lflag: UInt32
    var c_line: UInt8
    var c_cc: StaticTuple[UInt8, 32]  # Typically NCCS=32 in most systems
    var c_ispeed: UInt32
    var c_ospeed: UInt32

    fn __init__(mut self):
        """Initialize termios struct with default values."""
        self.c_iflag = 0
        self.c_oflag = 0
        self.c_cflag = 0
        self.c_lflag = 0
        self.c_line = 0
        self.c_cc = StaticTuple[UInt8, 32]()  # Initialize with zeros
        self.c_ispeed = 0
        self.c_ospeed = 0

    fn __init__(
        mut self,
        iflag: UInt32,
        oflag: UInt32,
        cflag: UInt32,
        lflag: UInt32,
        line: UInt8,
        cc: StaticTuple[UInt8, 32],
        ispeed: UInt32,
        ospeed: UInt32,
    ):
        """Initialize termios struct with provided values."""
        self.c_iflag = iflag
        self.c_oflag = oflag
        self.c_cflag = cflag
        self.c_lflag = lflag
        self.c_line = line
        self.c_cc = cc
        self.c_ispeed = ispeed
        self.c_ospeed = ospeed


# Define constants outside the namespace
# Define constants for open flags
alias O_RDWR: Int32 = 2
alias O_NOCTTY: Int32 = 256

# Constants for baud rate
alias B9600: UInt32 = 13
alias B115200: UInt32 = 4098

# Terminal attribute flags
alias CS8: UInt32 = 48
alias CLOCAL: UInt32 = 2048
alias CREAD: UInt32 = 128
alias TCSANOW: Int32 = 0

# ioctl request codes
alias TIOCMGET: UInt64 = 0x5415
alias TIOCMSET: UInt64 = 0x5418


# Create a namespace for C library functions to avoid conflicts
struct libc:
    """Namespace for C library function calls to avoid name conflicts."""

    """Sorry for the inconvenience, but this is a workaround, namespace method didn't work"""

    # File operations
    @staticmethod
    fn s_open(path: UnsafePointer[Int8], flags: Int32) -> Int32:
        return external_call["open", Int32, UnsafePointer[Int8], Int32](
            path, flags
        )

    @staticmethod
    fn s_close(fd: Int32) -> Int32:
        return external_call["close", Int32, Int32](fd)

    @staticmethod
    fn s_read(fd: Int32, buf: UnsafePointer[Int8], count: UInt64) -> Int64:
        return external_call["read", Int64, Int32, UnsafePointer[Int8], UInt64](
            fd, buf, count
        )

    @staticmethod
    fn s_write(fd: Int32, buf: UnsafePointer[Int8], count: UInt64) -> Int64:
        return external_call[
            "write", Int64, Int32, UnsafePointer[Int8], UInt64
        ](fd, buf, count)

    @staticmethod
    fn s_ioctl(fd: Int32, request: UInt64, arg: UnsafePointer[Int8]) -> Int32:
        return external_call[
            "ioctl", Int32, Int32, UInt64, UnsafePointer[Int8]
        ](fd, request, arg)


# Define terminal manipulation functions outside the namespace
fn tcgetattr(fd: Int32, termios_p: UnsafePointer[termios]) -> Int32:
    return external_call["tcgetattr", Int32, Int32, UnsafePointer[termios]](
        fd, termios_p
    )


fn tcsetattr(
    fd: Int32, optional_actions: Int32, termios_p: UnsafePointer[termios]
) -> Int32:
    return external_call[
        "tcsetattr", Int32, Int32, Int32, UnsafePointer[termios]
    ](fd, optional_actions, termios_p)


fn tcflush(fd: Int32, queue_selector: Int32) -> Int32:
    """Flush non-transmitted output data, non-read input data, or both."""
    return external_call["tcflush", Int32, Int32, Int32](fd, queue_selector)


fn cfsetispeed(termios_p: UnsafePointer[termios], speed: UInt32) -> Int32:
    return external_call["cfsetispeed", Int32, UnsafePointer[termios], UInt32](
        termios_p, speed
    )


fn cfsetospeed(termios_p: UnsafePointer[termios], speed: UInt32) -> Int32:
    return external_call["cfsetospeed", Int32, UnsafePointer[termios], UInt32](
        termios_p, speed
    )
