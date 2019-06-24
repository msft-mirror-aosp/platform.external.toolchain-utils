package main

import (
	"path/filepath"
	"strings"
)

func processSysrootFlag(rootPath string, builder *commandBuilder) string {
	fromUser := false
	for _, arg := range builder.args {
		if arg.fromUser && strings.HasPrefix(arg.value, "--sysroot=") {
			fromUser = true
			break
		}
	}
	sysroot := builder.env.getenv("SYSROOT")
	if sysroot != "" {
		builder.updateEnv("SYSROOT=")
	} else {
		// Use the bundled sysroot by default.
		sysroot = filepath.Join(rootPath, "usr", builder.target.target)
	}
	if !fromUser {
		builder.addPreUserArgs("--sysroot=" + sysroot)
	}
	return sysroot
}
