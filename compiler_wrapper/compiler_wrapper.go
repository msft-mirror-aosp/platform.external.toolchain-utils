// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"bytes"
	"fmt"
	"io"
	"path/filepath"
	"strings"
)

func callCompiler(env env, cfg *config, inputCmd *command) int {
	var compilerErr error

	if !filepath.IsAbs(inputCmd.Path) && !strings.HasPrefix(inputCmd.Path, ".") &&
		!strings.ContainsRune(inputCmd.Path, filepath.Separator) {
		if resolvedPath, err := resolveAgainstPathEnv(env, inputCmd.Path); err == nil {
			inputCmd = &command{
				Path:       resolvedPath,
				Args:       inputCmd.Args,
				EnvUpdates: inputCmd.EnvUpdates,
			}
		} else {
			compilerErr = err
		}
	}
	exitCode := 0
	if compilerErr == nil {
		if cfg.oldWrapperPath != "" {
			exitCode, compilerErr = callCompilerWithRunAndCompareToOldWrapper(env, cfg, inputCmd)
		} else {
			exitCode, compilerErr = callCompilerInternal(env, cfg, inputCmd)
		}
	}
	if compilerErr != nil {
		printCompilerError(env.stderr(), compilerErr)
		exitCode = 1
	}
	return exitCode
}

func callCompilerWithRunAndCompareToOldWrapper(env env, cfg *config, inputCmd *command) (exitCode int, err error) {
	stdinBuffer := &bytes.Buffer{}
	recordingEnv := &commandRecordingEnv{
		env:         env,
		stdinReader: teeStdinIfNeeded(env, inputCmd, stdinBuffer),
	}
	// Note: this won't do a real exec as recordingEnv redirects exec to run.
	if exitCode, err = callCompilerInternal(recordingEnv, cfg, inputCmd); err != nil {
		return 0, err
	}
	if err = compareToOldWrapper(env, cfg, inputCmd, stdinBuffer.Bytes(), recordingEnv.cmdResults, exitCode); err != nil {
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
		if err := processGomaCCacheFlags(sysroot, allowCCache, mainBuilder); err != nil {
			return 0, err
		}
		compilerCmd = mainBuilder.build()
	} else {
		if clangSyntax {
			allowCCache := false
			clangCmd, err := calcClangCommand(allowCCache, mainBuilder.clone())
			if err != nil {
				return 0, err
			}
			gccCmd, err := calcGccCommand(mainBuilder)
			if err != nil {
				return 0, err
			}
			return checkClangSyntax(env, clangCmd, gccCmd)
		}
		compilerCmd, err = calcGccCommand(mainBuilder)
		if err != nil {
			return 0, err
		}
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
	if shouldCompileWithFallback(env) {
		if rusageLogfileName != "" {
			return 0, newUserErrorf("GETRUSAGE is meaningless with FORCE_DISABLE_WERROR")
		}
		if bisectStage != "" {
			return 0, newUserErrorf("BISECT_STAGE is meaningless with FORCE_DISABLE_WERROR")
		}
		return compileWithFallback(env, cfg, compilerCmd, mainBuilder.absWrapperPath)
	}
	if rusageLogfileName != "" {
		if bisectStage != "" {
			return 0, newUserErrorf("BISECT_STAGE is meaningless with GETRUSAGE")
		}
		return logRusage(env, rusageLogfileName, compilerCmd)
	}
	if bisectStage != "" {
		compilerCmd, err = calcBisectCommand(env, cfg, bisectStage, compilerCmd)
		if err != nil {
			return 0, err
		}
	}
	// Note: We return an exit code only if the underlying env is not
	// really doing an exec, e.g. commandRecordingEnv.
	return wrapSubprocessErrorWithSourceLoc(compilerCmd, env.exec(compilerCmd))
}

func prepareClangCommand(builder *commandBuilder) (sysroot string, err error) {
	sysroot = ""
	if !builder.cfg.isHostWrapper && !builder.cfg.isAndroidWrapper {
		sysroot = processSysrootFlag(builder)
	}
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
	if err := processGomaCCacheFlags(sysroot, allowCCache, builder); err != nil {
		return nil, err
	}
	return builder.build(), nil
}

func calcGccCommand(builder *commandBuilder) (*command, error) {
	sysroot := ""
	if !builder.cfg.isHostWrapper {
		sysroot = processSysrootFlag(builder)
	}
	builder.addPreUserArgs(builder.cfg.gccFlags...)
	if !builder.cfg.isHostWrapper {
		calcCommonPreUserArgs(builder)
	}
	processGccFlags(builder)
	if !builder.cfg.isHostWrapper {
		allowCCache := true
		if err := processGomaCCacheFlags(sysroot, allowCCache, builder); err != nil {
			return nil, err
		}
	}
	return builder.build(), nil
}

func calcCommonPreUserArgs(builder *commandBuilder) {
	builder.addPreUserArgs(builder.cfg.commonFlags...)
	if !builder.cfg.isHostWrapper && !builder.cfg.isAndroidWrapper {
		processPieFlags(builder)
		processThumbCodeFlags(builder)
		processStackProtectorFlags(builder)
		processX86Flags(builder)
	}
	if !builder.cfg.isAndroidWrapper {
		processSanitizerFlags(builder)
	}
}

func processGomaCCacheFlags(sysroot string, allowCCache bool, builder *commandBuilder) (err error) {
	gomaccUsed := false
	if !builder.cfg.isHostWrapper {
		gomaccUsed, err = processGomaCccFlags(builder)
		if err != nil {
			return err
		}
	}
	if !gomaccUsed && allowCCache {
		processCCacheFlag(sysroot, builder)
	}
	return nil
}

func getAbsWrapperPath(env env, wrapperCmd *command) (string, error) {
	wrapperPath := getAbsCmdPath(env, wrapperCmd)
	evaledCmdPath, err := filepath.EvalSymlinks(wrapperPath)
	if err != nil {
		return "", wrapErrorwithSourceLocf(err, "failed to evaluate symlinks for %s", wrapperPath)
	}
	return evaledCmdPath, nil
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

func teeStdinIfNeeded(env env, inputCmd *command, dest io.Writer) io.Reader {
	// We can't use io.TeeReader unconditionally, as that would block
	// calls to exec.Cmd.Run(), even if the underlying process has already
	// terminated. See https://github.com/golang/go/issues/7990 for more details.
	lastArg := ""
	for _, arg := range inputCmd.Args {
		if arg == "-" && lastArg != "-o" {
			return io.TeeReader(env.stdin(), dest)
		}
		lastArg = arg
	}
	return env.stdin()
}
