package main

func processPrintCmdlineFlag(builder *commandBuilder) {
	printCmd := false
	builder.transformArgs(func(arg builderArg) string {
		if arg.value == "-print-cmdline" {
			printCmd = true
			return ""
		}
		return arg.value
	})
	if printCmd {
		builder.env = &printingEnv{builder.env}
	}
}
