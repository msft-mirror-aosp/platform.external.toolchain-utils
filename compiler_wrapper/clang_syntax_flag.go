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
		path:       clangCmd.path,
		args:       append(clangCmd.args, "-fsyntax-only", "-stdlib=libstdc++"),
		envUpdates: clangCmd.envUpdates,
	}
	return wrapSubprocessErrorWithSourceLoc(clangSyntaxCmd,
		env.run(clangSyntaxCmd, env.stdout(), env.stderr()))
}
