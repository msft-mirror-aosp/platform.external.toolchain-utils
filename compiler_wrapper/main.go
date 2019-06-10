// +build cros

// This binary uses the following build tags:
// - cros: Whether the wrapper should be built for ChromeOS
// - nonhardened: For a non-hardened set of compiler flags
// - hardened: For a hardened set of compiler flags
//
// There is a bash script for every meaningful combination.
// E.g. ./build_cros_hardened_wrapper.sh will build the ChromeOS
// hardened compiler wrapper.
//
// Test arguments:
// - crosroot: Specifies the ChromeOS toolchain root directory (aka chroot).
//   If this is given, tests will compare the produced commands against the
//   old compiler wrapper.
//
// Examples:
// - run all tests and compare output against old compiler wrapper:
// 		go test third_party/toolchain-utils/compiler_wrapper/ -v --crosroot=$HOME/chromiumos/chroot/
// - run all tests in isolation:
// 		go test third_party/toolchain-utils/compiler_wrapper/ -v
package main

import (
	"log"
	"os/exec"
	"syscall"
)

func main() {
	wrapperCmd := newProcessCommand()
	env, err := newProcessEnv()
	if err != nil {
		log.Fatal(err)
	}
	cfg := getRealConfig()
	if shouldForwardToOldWrapper(env, wrapperCmd) {
		err := forwardToOldWrapper(env, cfg, wrapperCmd)
		if err != nil {
			log.Fatal(err)
		}
		return
	}

	cmd, err := calcCompilerCommandAndCompareToOld(env, cfg, wrapperCmd)
	if err != nil {
		log.Fatal(err)
	}
	if err := execCmd(newExecCmd(env, cmd)); err != nil {
		log.Fatal(err)
	}
}

func execCmd(cmd *exec.Cmd) error {
	return syscall.Exec(cmd.Path, cmd.Args, cmd.Env)
}
