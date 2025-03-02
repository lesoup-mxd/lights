"""
Serial communication module for Mojo.

Provides a PySerial-like interface for serial port communication.
"""

from src import binds
from src.binds import libc, termios
from memory import UnsafePointer
import time


@value
struct Serial:
    """
    Serial port communication class for Mojo.

    Provides a higher-level interface for serial port communication,
    inspired by PySerial.
    """

    # Serial port configuration
    var port: String
    var baudrate: UInt32
    var bytesize: UInt32
    var parity: String
    var stopbits: Int
    var timeout: Float64

    # Internal state
    var _fd: Int32
    var _is_open: Bool

    fn __init__(
        mut self,
        port: String,
        baudrate: UInt32 = binds.B9600,
        bytesize: UInt32 = 8,
        parity: String = "N",
        stopbits: Int = 1,
        timeout: Float64 = 1.0,
    ) raises:
        """Initialize a serial port object."""
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout
        self._fd = -1
        self._is_open = False

        # Validate parameters
        if self.bytesize != 8:
            raise Error("Only 8-bit bytesize is currently supported")

        if self.parity != "N":
            raise Error("Only no parity (N) is currently supported")

        if self.stopbits != 1:
            raise Error("Only 1 stop bit is currently supported")

    fn open(mut self) raises:
        """Open the serial port."""
        if self._is_open:
            return

        # Use StringLiteral's unsafe_cstr_ptr to get a proper C string pointer
        var port_ptr = self.port.unsafe_cstr_ptr()

        # Open port using libc namespace
        self._fd = libc.open(port_ptr, binds.O_RDWR | binds.O_NOCTTY)
        if self._fd < 0:
            raise Error("Could not open port " + self.port)

        # Configure port
        self._configure_port()
        self._is_open = True

    fn _configure_port(self) raises:
        """Configure the serial port with the current settings."""
        # Get current port settings
        var options = termios()
        var options_ptr = UnsafePointer[termios].address_of(options)

        var result = binds.tcgetattr(self._fd, options_ptr)
        if result != 0:
            libc.close(self._fd)
            raise Error("Could not get port attributes")

        # Set input and output baud rates
        result = binds.cfsetispeed(options_ptr, self.baudrate)
        if result != 0:
            libc.close(self._fd)
            raise Error("Could not set input baud rate")

        result = binds.cfsetospeed(options_ptr, self.baudrate)
        if result != 0:
            libc.close(self._fd)
            raise Error("Could not set output baud rate")

        # 8N1 (8 bits, no parity, 1 stop bit)
        options.c_cflag &= ~0o000060  # Clear parity bit
        options.c_cflag |= binds.CS8  # 8 bits
        options.c_cflag &= ~0o000400  # 1 stop bit

        # No flow control
        options.c_cflag &= ~0o010000  # No hardware flow control
        options.c_iflag &= ~(0o000001 | 0o000002)  # No software flow control

        # Enable receiver, local mode
        options.c_cflag |= binds.CREAD | binds.CLOCAL

        # Raw input (no special processing)
        options.c_lflag &= ~(0o000010 | 0o000100 | 0o000002 | 0o040000)

        # Raw output (no special processing)
        options.c_oflag &= ~0o000001

        # Set the attributes
        result = binds.tcsetattr(self._fd, binds.TCSANOW, options_ptr)
        if result != 0:
            libc.close(self._fd)
            raise Error("Could not set port attributes")

    fn close(mut self):
        """Close the serial port."""
        if self._is_open:
            _ = libc.close(
                self._fd
            )  # Add underscore to handle unused result warning
            self._is_open = False

    fn read(self, size: Int) raises -> String:
        """Read up to size bytes from the serial port."""
        if not self._is_open:
            raise Error("Port not open")

        # Allocate buffer with direct memory allocation
        var buffer = UnsafePointer[Int8].alloc(size)

        # Read directly into the buffer using libc namespace
        var bytes_read = libc.read(self._fd, buffer, UInt64(size))

        if bytes_read < 0:
            buffer.free()
            raise Error("Error reading from port")

        # Create a string from the buffer
        var result = String("")
        for i in range(bytes_read):
            result += chr(Int(buffer.load(i)))

        # Free the allocated memory
        buffer.free()

        return result

    fn write(self, data: String) raises -> Int:
        """Write data to the serial port."""
        if not self._is_open:
            raise Error("Port not open")

        # Use unsafe_cstr_ptr to get a C string pointer
        var write_ptr = data.unsafe_cstr_ptr()

        # Use libc namespace
        var bytes_written = libc.write(self._fd, write_ptr, UInt64(len(data)))

        if bytes_written < 0:
            raise Error("Error writing to port")

        return Int(bytes_written)

    fn readline(self, size: Int = 1024) raises -> String:
        """
        Read a line from the serial port.

        Reads until a newline character is found or until size bytes have been read.
        """
        if not self._is_open:
            raise Error("Port not open")

        # Allocate buffer for reading one byte at a time
        var buffer = UnsafePointer[Int8].alloc(1)
        var result = String("")

        # Read one byte at a time until newline or size limit
        for _ in range(size):
            # Use libc namespace
            var bytes_read = libc.read(self._fd, buffer, 1)

            if bytes_read <= 0:
                # End of file or error
                break

            # Convert byte to character and append
            var char = chr(Int(buffer.load()))
            result += char

            if char == "\n":
                # End of line
                break

        # Free the buffer
        buffer.free()
        return result

    fn flush(self) raises:
        """Flush the serial port input and output buffers."""
        if not self._is_open:
            raise Error("Port not open")

        # TCIOFLUSH = 2 (flush both input and output buffers)
        var result = binds.tcflush(self._fd, 2)
        if result != 0:
            raise Error("Could not flush buffers")

    fn __enter__(mut self) raises -> Self:
        """Context manager entry."""
        self.open()
        return self

    fn __exit__(mut self, exc_type: AnyType, exc_val: AnyType, exc_tb: AnyType):
        """Context manager exit."""
        self.close()
