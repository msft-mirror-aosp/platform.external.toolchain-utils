package main

import (
	"fmt"
	"io"
	"path/filepath"
)

func callCompiler(env env, cfg *config, inputCmd *command) int {
	exitCode := 0
	var compilerErr error
	if shouldForwardToOldWrapper(env, inputCmd) {
		// TODO: Once this is only checking for bisect, create a command
		// that directly calls the bisect driver in calcCompilerCommand.
		exitCode, compilerErr = forwardToOldWrapper(env, cfg, inputCmd)
	} else if cfg.oldWrapperPath != "" {
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
	var compilerCmd *command
	clangSyntax := processClangSyntaxFlag(mainBuilder)
	if mainBuilder.target.compilerType == clangType {
		cSrcFile, useClangTidy := processClangTidyFlags(mainBuilder)
		compilerCmd, err = calcClangCommand(useClangTidy, mainBuilder)
		if err != nil {
			return 0, err
		}
		if useClangTidy {
			if err := runClangTidy(env, compilerCmd, cSrcFile); err != nil {
				return 0, err
			}
		}
	} else {
		if clangSyntax {
			forceLocal := false
			clangCmd, err := calcClangCommand(forceLocal, mainBuilder.clone())
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
	if shouldForceDisableWError(env) {
		if rusageLogfileName != "" {
			return 0, newUserErrorf("GETRUSAGE is meaningless with FORCE_DISABLE_WERROR")
		}
		return doubleBuildWithWNoError(env, cfg, compilerCmd)
	}
	if rusageLogfileName != "" {
		return logRusage(env, rusageLogfileName, compilerCmd)
	}
	// Note: We return an exit code only if the underlying env is not
	// really doing an exec, e.g. commandRecordingEnv.
	return wrapSubprocessErrorWithSourceLoc(compilerCmd, env.exec(compilerCmd))
}

func calcClangCommand(forceLocal bool, builder *commandBuilder) (*command, error) {
	sysroot := processSysrootFlag(builder)
	builder.addPreUserArgs(builder.cfg.clangFlags...)
	calcCommonPreUserArgs(builder)
	if err := processClangFlags(builder); err != nil {
		return nil, err
	}
	if !forceLocal {
		processGomaCCacheFlags(sysroot, builder)
	}
	return builder.build(), nil
}

func calcGccCommand(builder *commandBuilder) *command {
	sysroot := processSysrootFlag(builder)
	builder.addPreUserArgs(builder.cfg.gccFlags...)
	calcCommonPreUserArgs(builder)
	processGccFlags(builder)
	processGomaCCacheFlags(sysroot, builder)
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

func processGomaCCacheFlags(sysroot string, builder *commandBuilder) {
	gomaccUsed := processGomaCccFlags(builder)
	if !gomaccUsed {
		processCCacheFlag(sysroot, builder)
	}
}

func getAbsWrapperDir(env env, wrapperPath string) (string, error) {
	if !filepath.IsAbs(wrapperPath) {
		wrapperPath = filepath.Join(env.getwd(), wrapperPath)
	}
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
