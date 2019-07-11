package main

import "path/filepath"

const bisectPythonCommand = "import bisect_driver; sys.exit(bisect_driver.bisect_driver(sys.argv[1], sys.argv[2], sys.argv[3:]))"

func getBisectStage(env env) string {
	return env.getenv("BISECT_STAGE")
}

func calcBisectCommand(env env, bisectStage string, compilerCmd *command) *command {
	bisectDir := env.getenv("BISECT_DIR")
	if bisectDir == "" {
		bisectDir = "/tmp/sysroot_bisect"
	}
	absCompilerPath := compilerCmd.path
	if !filepath.IsAbs(absCompilerPath) {
		absCompilerPath = filepath.Join(env.getwd(), absCompilerPath)
	}
	return &command{
		path: "/usr/bin/python2",
		args: append([]string{
			"-c",
			bisectPythonCommand,
			bisectStage,
			bisectDir,
			absCompilerPath,
		}, compilerCmd.args...),
	}
}
