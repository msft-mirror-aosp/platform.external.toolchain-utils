// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

const bisectPythonCommand = "import bisect_driver; sys.exit(bisect_driver.bisect_driver(sys.argv[1], sys.argv[2], sys.argv[3:]))"

func getBisectStage(env env) string {
	value, _ := env.getenv("BISECT_STAGE")
	return value
}

func calcBisectCommand(env env, bisectStage string, compilerCmd *command) *command {
	bisectDir, _ := env.getenv("BISECT_DIR")
	if bisectDir == "" {
		bisectDir = "/tmp/sysroot_bisect"
	}
	absCompilerPath := getAbsCmdPath(env, compilerCmd)
	return &command{
		Path: "/usr/bin/python2",
		Args: append([]string{
			"-c",
			bisectPythonCommand,
			bisectStage,
			bisectDir,
			absCompilerPath,
		}, compilerCmd.Args...),
		EnvUpdates: compilerCmd.EnvUpdates,
	}
}
