package main

import (
	"errors"
)

func checkUnsupportedFlags(cmd *command) error {
	for _, arg := range cmd.args {
		if arg == "-fstack-check" {
			return errors.New(`option "-fstack-check" is not supported; crbug/485492`)
		}
	}
	return nil
}
