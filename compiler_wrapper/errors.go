package main

import (
	"fmt"
	"os/exec"
	"runtime"
	"strings"
	"syscall"
)

type userError struct {
	err string
}

var _ error = userError{}

func (err userError) Error() string {
	return err.err
}

func newUserErrorf(format string, v ...interface{}) userError {
	return userError{err: fmt.Sprintf(format, v...)}
}

func newErrorwithSourceLocf(format string, v ...interface{}) error {
	return newErrorwithSourceLocfInternal(2, format, v...)
}

func wrapErrorwithSourceLocf(err error, format string, v ...interface{}) error {
	return newErrorwithSourceLocfInternal(2, "%s: %s", fmt.Sprintf(format, v...), err.Error())
}

// Based on the implementation of log.Output
func newErrorwithSourceLocfInternal(skip int, format string, v ...interface{}) error {
	_, file, line, ok := runtime.Caller(skip)
	if !ok {
		file = "???"
		line = 0
	}
	if lastSlash := strings.LastIndex(file, "/"); lastSlash >= 0 {
		file = file[lastSlash+1:]
	}

	return fmt.Errorf("%s:%d: %s", file, line, fmt.Sprintf(format, v...))
}

func getExitCode(err error) (exitCode int, ok bool) {
	if err == nil {
		return 0, true
	}
	if exiterr, ok := err.(*exec.ExitError); ok {
		if status, ok := exiterr.Sys().(syscall.WaitStatus); ok {
			return status.ExitStatus(), true
		}
	}
	return 0, false
}
