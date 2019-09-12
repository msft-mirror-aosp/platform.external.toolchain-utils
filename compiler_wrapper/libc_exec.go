// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

// #include <errno.h>
// #include <stdlib.h>
// #include <string.h>
// #include <unistd.h>
//
// int libc_exec(const char *pathname, char *const argv[], char *const env_updates[]) {
//	// Note: We are not using execve and pass the new environment here
//	// as that sometimes doesn't work well with the gentoo sandbox to
//	// pick up changes to SANDBOX_WRITE env variable (needed for ccache).
//	// Instead, we are updating our own environment and call execv.
//	// This update of global state is ok as we won't execute anything else
//	// after the exec.
//	// Note: We don't update the environment already in go as these somehow
//	// don't seem to update the real environment...
//	int i;
//	for (i = 0; env_updates[i] != NULL; ++i) {
//		const char* update = env_updates[i];
//		const char* pos = strchr(update, '=');
//		if (pos == NULL) {
//			continue;
//		}
//		char key[pos - update + 1];
//		key[pos - update] = 0;
//		strncpy(key, update, pos - update);
//		if (pos[1] == 0) {
//			// update has no value
//			unsetenv(key);
//		} else {
//			setenv(key, &pos[1], /*overwrite=*/1);
//		}
//	}
//	if (execv(pathname, argv) != 0) {
//		return errno;
//	}
//	return 0;
//}
import "C"
import (
	"os/exec"
	"unsafe"
)

// Replacement for syscall.Execve that uses the libc.
// This allows tools that rely on intercepting syscalls via
// LD_PRELOAD to work properly (e.g. gentoo sandbox).
// Note that this changes the go binary to be a dynamically linked one.
// See crbug.com/1000863 for details.
func libcExec(cmd *command) error {
	freeList := []unsafe.Pointer{}
	defer func() {
		for _, ptr := range freeList {
			C.free(ptr)
		}
	}()

	goStrToC := func(goStr string) *C.char {
		cstr := C.CString(goStr)
		freeList = append(freeList, unsafe.Pointer(cstr))
		return cstr
	}

	goSliceToC := func(goSlice []string) **C.char {
		// len(goSlice)+1 as the c array needs to be null terminated.
		cArray := C.malloc(C.size_t(len(goSlice)+1) * C.size_t(unsafe.Sizeof(uintptr(0))))
		freeList = append(freeList, cArray)

		// Convert the C array to a Go Array so we can index it.
		// Note: Storing pointers to the c heap in go pointer types is ok
		// (see https://golang.org/cmd/cgo/).
		cArrayForIndex := (*[1<<30 - 1]*C.char)(cArray)
		for i, str := range goSlice {
			cArrayForIndex[i] = goStrToC(str)
		}
		cArrayForIndex[len(goSlice)] = nil

		return (**C.char)(cArray)
	}

	execCmd := exec.Command(cmd.Path, cmd.Args...)
	if errno := C.libc_exec(goStrToC(execCmd.Path), goSliceToC(execCmd.Args), goSliceToC(cmd.EnvUpdates)); errno != 0 {
		return newErrorwithSourceLocf("exec error: %d", errno)
	}

	return nil
}
