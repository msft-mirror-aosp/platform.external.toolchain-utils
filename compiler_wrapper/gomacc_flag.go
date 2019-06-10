package main

import (
	"os"
)

func processGomaCccFlags(builder *commandBuilder) (gomaUsed bool) {
	if gomaPath := builder.env.getenv("GOMACC_PATH"); gomaPath != "" {
		if _, err := os.Lstat(gomaPath); err == nil {
			builder.wrapPath(gomaPath)
			return true
		}
	}
	return false
}
