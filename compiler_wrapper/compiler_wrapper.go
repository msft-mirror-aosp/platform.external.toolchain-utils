// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"io"
	"path/filepath"
)

func callCompiler(env env, cfg *config, inputCmd *command) int {
	exitCode := 0
	var compilerErr error
	if cfg.oldWrapperPath != "" {
		exitCode, compilerErr = callCompilerWithRunAndCompareToOldWrapper(env, cfg, inputCmd)
	} else {
		exitCode, compilerErr = callCompilerInternal(env, cfg, inputCmd)
	}
	if compilerErr != nil {
		printCompilerError(env.stderr(), compilerErr)
		exitCode = 1
	}
	return exitCode
}

func callCompilerWithRunAndCompareToOldWrapper(env env, cfg *config, inputCmd *command) (exitCode int, err error) {
	recordingEnv := &commandRecordingEnv{
		env: env,
	}
	// Note: this won't do a real exec as recordingEnv redirects exec to run.
	if exitCode, err = callCompilerInternal(recordingEnv, cfg, inputCmd); err != nil {
		return 0, err
	}
	if err = compareToOldWrapper(env, cfg, inputCmd, recordingEnv.cmdResults, exitCode); err != nil {
		return exitCode, err
	}
	return exitCode, nil
}

func callCompilerInternal(env env, cfg *config, inputCmd *command) (exitCode int, err error) {
	if err := checkUnsupportedFlags(inputCmd); err != nil {
		return 0, err
	}
	mainBuilder, err := newCommandBuilder(env, cfg, inputCmd)
	if err != nil {
		return 0, err
	}
	processPrintConfigFlag(mainBuilder)
	processPrintCmdlineFlag(mainBuilder)
	env = mainBuilder.env
	var compilerCmd *command
	clangSyntax := processClangSyntaxFlag(mainBuilder)
	if mainBuilder.target.compilerType == clangType {
		cSrcFile, useClangTidy := processClangTidyFlags(mainBuilder)
		sysroot, err := prepareClangCommand(mainBuilder)
		if err != nil {
			return 0, err
		}
		allowCCache := true
		if useClangTidy {
			allowCCache = false
			clangCmdWithoutGomaAndCCache := mainBuilder.build()
			if err := runClangTidy(env, clangCmdWithoutGomaAndCCache, cSrcFile); err != nil {
				return 0, err
			}
		}
		processGomaCCacheFlags(sysroot, allowCCache, mainBuilder)
		compilerCmd = mainBuilder.build()
	} else {
		if clangSyntax {
			allowCCache := false
			clangCmd, err := calcClangCommand(allowCCache, mainBuilder.clone())
			if err != nil {
				return 0, err
			}
			exitCode, err = checkClangSyntax(env, clangCmd)
			if err != nil || exitCode != 0 {
				return exitCode, err
			}
		}
		compilerCmd = calcGccCommand(mainBuilder)
	}
	rusageLogfileName := getRusageLogFilename(env)
	bisectStage := getBisectStage(env)
	if shouldForceDisableWError(env) {
		if rusageLogfileName != "" {
			return 0, newUserErrorf("GETRUSAGE is meaningless with FORCE_DISABLE_WERROR")
		}
		if bisectStage != "" {
			return 0, newUserErrorf("BISECT_STAGE is meaningless with FORCE_DISABLE_WERROR")
		}
		return doubleBuildWithWNoError(env, cfg, compilerCmd)
	}
	if rusageLogfileName != "" {
		if bisectStage != "" {
			return 0, newUserErrorf("BISECT_STAGE is meaningless with GETRUSAGE")
		}
		return logRusage(env, rusageLogfileName, compilerCmd)
	}
	if bisectStage != "" {
		compilerCmd = calcBisectCommand(env, bisectStage, compilerCmd)
	}
	// Note: We return an exit code only if the underlying env is not
	// really doing an exec, e.g. commandRecordingEnv.
	return wrapSubprocessErrorWithSourceLoc(compilerCmd, env.exec(compilerCmd))
}

func prepareClangCommand(builder *commandBuilder) (sysroot string, err error) {
	sysroot = processSysrootFlag(builder)
	builder.addPreUserArgs(builder.cfg.clangFlags...)
	calcCommonPreUserArgs(builder)
	if err := processClangFlags(builder); err != nil {
		return "", err
	}
	return sysroot, nil
}

func calcClangCommand(allowCCache bool, builder *commandBuilder) (*command, error) {
	sysroot, err := prepareClangCommand(builder)
	if err != nil {
		return nil, err
	}
	processGomaCCacheFlags(sysroot, allowCCache, builder)
	return builder.build(), nil
}

func calcGccCommand(builder *commandBuilder) *command {
	sysroot := processSysrootFlag(builder)
	builder.addPreUserArgs(builder.cfg.gccFlags...)
	calcCommonPreUserArgs(builder)
	processGccFlags(builder)
	allowCCache := true
	processGomaCCacheFlags(sysroot, allowCCache, builder)
	return builder.build()
}

func calcCommonPreUserArgs(builder *commandBuilder) {
	builder.addPreUserArgs(builder.cfg.commonFlags...)
	processPieFlags(builder)
	processStackProtectorFlags(builder)
	processThumbCodeFlags(builder)
	processX86Flags(builder)
	processSanitizerFlags(builder)
}

func processGomaCCacheFlags(sysroot string, allowCCache bool, builder *commandBuilder) {
	gomaccUsed := processGomaCccFlags(builder)
	if !gomaccUsed && allowCCache {
		processCCacheFlag(sysroot, builder)
	}
}

func getAbsWrapperDir(env env, wrapperCmd *command) (string, error) {
	wrapperPath := getAbsCmdPath(env, wrapperCmd)
	evaledCmdPath, err := filepath.EvalSymlinks(wrapperPath)
	if err != nil {
		return "", wrapErrorwithSourceLocf(err, "failed to evaluate symlinks for %s", wrapperPath)
	}
	return filepath.Dir(evaledCmdPath), nil
}

func printCompilerError(writer io.Writer, compilerErr error) {
	if _, ok := compilerErr.(userError); ok {
		fmt.Fprintf(writer, "%s\n", compilerErr)
	} else {
		fmt.Fprintf(writer,
			"Internal error. Please report to chromeos-toolchain@google.com.\n%s\n",
			compilerErr)
	}
}
