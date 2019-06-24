package main

import (
	"strings"
)

func processSanitizerFlags(builder *commandBuilder) {
	filterSanitizerFlags := false
	for _, arg := range builder.args {
		// TODO: This should probably be -fsanitize= to not match on
		// e.g. -fsanitize-blacklist
		if arg.fromUser && strings.HasPrefix(arg.value, "-fsanitize") {
			filterSanitizerFlags = true
			break
		}
	}
	if filterSanitizerFlags {
		// Flags not supported by sanitizers (ASan etc.)
		var unsupportedSanitizerFlags = map[string]bool{
			"-D_FORTIFY_SOURCE=1": true,
			"-D_FORTIFY_SOURCE=2": true,
			"-Wl,--no-undefined":  true,
			"-Wl,-z,defs":         true,
		}

		builder.transformArgs(func(arg builderArg) string {
			if unsupportedSanitizerFlags[arg.value] {
				return ""
			}
			return arg.value
		})
	}
}
