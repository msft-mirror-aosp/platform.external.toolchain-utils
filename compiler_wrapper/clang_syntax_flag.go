package main

func processClangSyntaxFlag(builder *commandBuilder) (clangSyntax bool) {
	builder.transformArgs(func(arg builderArg) string {
		if arg.value == "-clang-syntax" {
			clangSyntax = true
			return ""
		}
		return arg.value
	})
	return clangSyntax
}

func checkClangSyntax(env env, clangCmd *command) (exitCode int, err error) {
	clangSyntaxCmd := &command{
		Path:       clangCmd.Path,
		Args:       append(clangCmd.Args, "-fsyntax-only", "-stdlib=libstdc++"),
		EnvUpdates: clangCmd.EnvUpdates,
	}
	return wrapSubprocessErrorWithSourceLoc(clangSyntaxCmd,
		env.run(clangSyntaxCmd, env.stdout(), env.stderr()))
}
