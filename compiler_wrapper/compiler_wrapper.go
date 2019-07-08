package main

import (
	"fmt"
	"io"
	"path/filepath"
	"strings"
	"syscall"
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
		exitCode, compilerErr = callCompilerWithExec(env, cfg, inputCmd)
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
	compilerCmd, exitCode, err := calcCompilerCommand(recordingEnv, cfg, inputCmd)
	if err != nil || exitCode != 0 {
		return exitCode, err
	}
	exitCode = 0
	// Note: we are not using env.exec here so that we can compare the exit code
	// against the old wrapper too.
	if err := recordingEnv.run(compilerCmd, env.stdout(), env.stderr()); err != nil {
		if userErr, ok := getCCacheError(compilerCmd, err); ok {
			return exitCode, userErr
		}
		var ok bool
		if exitCode, ok = getExitCode(err); !ok {
			return exitCode, wrapErrorwithSourceLocf(err, "failed to execute %#v", compilerCmd)
		}
	}
	if err := compareToOldWrapper(env, cfg, inputCmd, recordingEnv.cmdResults); err != nil {
		return exitCode, err
	}
	return exitCode, nil
}

func callCompilerWithExec(env env, cfg *config, inputCmd *command) (exitCode int, err error) {
	compilerCmd, exitCode, err := calcCompilerCommand(env, cfg, inputCmd)
	if err != nil || exitCode != 0 {
		return exitCode, err
	}
	if err := env.exec(compilerCmd); err != nil {
		// Note: No need to check for exit code error as exec will
		// stop this control flow once the command started executing.
		if userErr, ok := getCCacheError(compilerCmd, err); ok {
			return exitCode, userErr
		}
		return exitCode, wrapErrorwithSourceLocf(err, "failed to execute %#v", compilerCmd)
	}
	return exitCode, nil
}

func calcCompilerCommand(env env, cfg *config, inputCmd *command) (compilerCmd *command, exitCode int, err error) {
	if err := checkUnsupportedFlags(inputCmd); err != nil {
		return nil, exitCode, err
	}
	mainBuilder, err := newCommandBuilder(env, cfg, inputCmd)
	if err != nil {
		return nil, exitCode, err
	}
	clangSyntax := processClangSyntaxFlag(mainBuilder)
	if mainBuilder.target.compilerType == clangType {
		compilerCmd, err = calcClangCommand(mainBuilder)
		if err != nil {
			return nil, exitCode, err
		}
	} else {
		if clangSyntax {
			clangCmd, err := calcClangCommand(mainBuilder.clone())
			if err != nil {
				return nil, 0, err
			}
			exitCode, err = checkClangSyntax(env, clangCmd)
			if err != nil || exitCode != 0 {
				return nil, exitCode, err
			}
		}
		compilerCmd = calcGccCommand(mainBuilder)
	}

	return compilerCmd, exitCode, nil
}

func calcClangCommand(builder *commandBuilder) (*command, error) {
	sysroot := processSysrootFlag(builder)
	builder.addPreUserArgs(builder.cfg.clangFlags...)
	calcCommonPreUserArgs(builder)
	if err := processClangFlags(builder); err != nil {
		return nil, err
	}
	processGomaCCacheFlags(sysroot, builder)
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

func getCCacheError(compilerCmd *command, compilerCmdErr error) (ccacheErr userError, ok bool) {
	if en, ok := compilerCmdErr.(syscall.Errno); ok && en == syscall.ENOENT &&
		strings.Contains(compilerCmd.path, "ccache") {
		ccacheErr =
			newUserErrorf("ccache not found under %s. Please install it",
				compilerCmd.path)
		return ccacheErr, ok
	}
	return ccacheErr, false
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
