.PHONY: all clean run build-lib build-mojo

# Configuration
SRC_DIR = src
BUILD_DIR = build
CC = gcc
CFLAGS = -Wall -fPIC
LDFLAGS = -shared
MOJO = mojo
MOJO_FLAGS = 

# Files
WRAPPER_SRC = $(SRC_DIR)/sys_wrappers.c
WRAPPER_LIB = $(BUILD_DIR)/libserial_wrappers.so
MOJO_SRC = 1.mojo
MOJO_BIN = $(BUILD_DIR)/app

# Default target
all: $(BUILD_DIR) build-lib build-mojo

# Create build directory
$(BUILD_DIR):
    mkdir -p $(BUILD_DIR)

# Build C wrapper library
build-lib: $(WRAPPER_LIB)

$(WRAPPER_LIB): $(WRAPPER_SRC) | $(BUILD_DIR)
    $(CC) $(CFLAGS) $(LDFLAGS) -o $@ $<

# Build Mojo app
build-mojo: $(MOJO_BIN)

$(MOJO_BIN): $(MOJO_SRC) $(WRAPPER_LIB)
    $(MOJO) build $(MOJO_FLAGS) -o $@ $<

# Run the application with library path set
run: all
    @echo "Running the application..."
    @LD_LIBRARY_PATH=$(shell pwd)/$(BUILD_DIR) $(MOJO_BIN)

# Clean build files
clean:
    rm -rf $(BUILD_DIR)
    rm -f *.o *.so