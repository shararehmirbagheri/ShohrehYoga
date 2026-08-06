#
# FreeType 2 template for Unix-specific compiler definitions
#

# Copyright (C) 1996-2025 by
# David Turner, Robert Wilhelm, and Werner Lemberg.
#
# This file is part of the FreeType project, and may only be used, modified,
# and distributed under the terms of the FreeType project license,
# LICENSE.TXT.  By continuing to use, modify, or distribute this file you
# indicate that you have read the license and understand and accept it
# fully.


CC           := /home/sharareh/.buildozer/android/platform/android-ndk-r28c/toolchains/llvm/prebuilt/linux-x86_64/bin/clang -target aarch64-linux-android24 -fomit-frame-pointer -march=armv8-a -fPIC
COMPILER_SEP := $(SEP)
FT_LIBTOOL_DIR ?= $(PLATFORM_DIR)

LIBTOOL := $(FT_LIBTOOL_DIR)/libtool


# The object file extension (for standard and static libraries).  This can be
# .o, .tco, .obj, etc., depending on the platform.
#
O  := lo
SO := o


# The executable file extension.  Although most Unix platforms use no
# extension, we copy the extension detected by autoconf.  Useful for cross
# building on Unix systems for non-Unix systems.
#
E := 


# The library file extension (for standard and static libraries).  This can
# be .a, .lib, etc., depending on the platform.
#
A  := la
SA := a


# The name of the final library file.  Note that the DOS-specific Makefile
# uses a shorter (8.3) name.
#
LIBRARY := lib$(PROJECT)


# Path inclusion flag.  Some compilers use a different flag than `-I' to
# specify an additional include path.  Examples are `/i=' or `-J'.
#
I := -I


# C flag used to define a macro before the compilation of a given source
# object.  Usually it is `-D' like in `-DDEBUG'.
#
D := -D


# The link flag used to specify a given library file on link.  Note that
# this is only used to compile the demo programs, not the library itself.
#
L := -l


# Target flag.
#
T := -o$(space)


# C flags
#
#   These should concern: debug output, optimization & warnings.
#
#   Use the ANSIFLAGS variable to define the compiler flags used to enforce
#   ANSI compliance.
#
#   We use our own FreeType configuration files overriding defaults.
#
CPPFLAGS := -DANDROID -I/home/sharareh/.buildozer/android/platform/android-ndk-r28c/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include -I/home/sharareh/ShohrehYoga/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/build/other_builds/python3/arm64-v8a__ndk_target_24/python3/android-build/android-root/include/python3.14
CFLAGS   := -c -Wall -target aarch64-linux-android24 -fomit-frame-pointer -march=armv8-a -fPIC -I/home/sharareh/.buildozer/android/platform/android-ndk-r28c/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/include -fvisibility=hidden  -pthread \
            $DFT_CONFIG_CONFIG_H="<ftconfig.h>" \
            $DFT_CONFIG_MODULES_H="<ftmodule.h>" \
            $DFT_CONFIG_OPTIONS_H="<ftoption.h>"

# ANSIFLAGS: Put there the flags used to make your compiler ANSI-compliant.
#
ANSIFLAGS :=  -pedantic -std=c99

# C compiler to use -- we use libtool!
#
# CC might be set on the command line; we store this value in `CCraw'.
# Consequently, we use the `override' directive to ensure that the
# libtool call is always prepended.
#
CCraw       := $(CC)
override CC := $(LIBTOOL) --mode=compile $(CCraw)

# Resource compiler to use on Cygwin/MinGW, usually windres.
#
RCraw := 
ifneq ($(RCraw),)
  RC := $(LIBTOOL) --tag=RC --mode=compile $(RCraw)
endif

# Linker flags.
#
LDFLAGS :=   -L/home/sharareh/ShohrehYoga/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/build/libs_collections/attendance_app/arm64-v8a -L/home/sharareh/.buildozer/android/platform/android-ndk-r28c/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/24 -march=armv8-a -lz -pthread 

# export symbols
#
CCraw_build   := gcc               # native CC of building system
E_BUILD       :=            # extension for executable on
                                          # building system
EXPORTS_LIST  := $(OBJ_DIR)/ftexport.sym
CCexe         := $(CCraw_build)           # used to compile `apinames` only,
                                          # see `exports.mk`
CCexe_CFLAGS  :=            # ditto
CCexe_LDFLAGS :=           # ditto


# Library linking.
#
LINK_LIBRARY = $(LIBTOOL) --mode=link $(CCraw) -o $@ $(OBJECTS_LIST) \
                          -rpath $(libdir) -version-info $(version_info) \
                          $(LDFLAGS) -no-undefined \
                          -export-symbols $(EXPORTS_LIST)

# For the demo programs.
FT_DEMO_CFLAGS := 
FT_DEMO_LDFLAGS := 

# EOF
