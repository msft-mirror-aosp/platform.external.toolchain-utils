// This binary requires the following linker variables:
// - main.UseCCache: Whether to use ccache.
// - main.ConfigName: Name of the configuration to use.
//   See config.go for the supported values.
//
// The script ./build simplifies the call to `go build`.
// E.g. ./build --use_ccache=true --config=cros.hardened will build a
// binary that uses the ccache for ChromeOS with hardened flags.
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
	cfg, err := getRealConfig()
	if err != nil {
		log.Fatal(err)
	}
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
