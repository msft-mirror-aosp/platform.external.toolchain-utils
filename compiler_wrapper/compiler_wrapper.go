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
		compilerErr = callCompilerWithExec(env, cfg, inputCmd)
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
	compilerCmd, err := calcCompilerCommand(recordingEnv, cfg, inputCmd)
	if err != nil {
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
			return exitCode, wrapErrorwithSourceLocf(err, "failed to execute %s %s", compilerCmd.path, compilerCmd.args)
		}
	}
	if err := compareToOldWrapper(env, cfg, inputCmd, recordingEnv.cmdResults); err != nil {
		return exitCode, err
	}
	return exitCode, nil
}

func callCompilerWithExec(env env, cfg *config, inputCmd *command) error {
	compilerCmd, err := calcCompilerCommand(env, cfg, inputCmd)
	if err != nil {
		return err
	}
	if err := env.exec(compilerCmd); err != nil {
		// Note: No need to check for exit code error as exec will
		// stop this control flow once the command started executing.
		if userErr, ok := getCCacheError(compilerCmd, err); ok {
			return userErr
		}
		return wrapErrorwithSourceLocf(err, "failed to execute %s %s", compilerCmd.path, compilerCmd.args)
	}
	return nil
}

func calcCompilerCommand(env env, cfg *config, inputCmd *command) (*command, error) {
	if err := checkUnsupportedFlags(inputCmd); err != nil {
		return nil, err
	}
	absWrapperDir, err := getAbsWrapperDir(env, inputCmd.path)
	if err != nil {
		return nil, err
	}
	rootPath := filepath.Join(absWrapperDir, cfg.rootRelPath)
	builder, err := newCommandBuilder(env, cfg, inputCmd)
	if err != nil {
		return nil, err
	}
	useClang := builder.target.compilerType == clangType
	sysroot := processSysrootFlag(rootPath, builder)
	if useClang {
		builder.addPreUserArgs(cfg.clangFlags...)
	} else {
		builder.addPreUserArgs(cfg.gccFlags...)
	}
	builder.addPreUserArgs(cfg.commonFlags...)
	processPieFlags(builder)
	processStackProtectorFlags(builder)
	processThumbCodeFlags(builder)
	processX86Flags(builder)
	processSanitizerFlags(builder)
	if useClang {
		if err := processClangFlags(rootPath, builder); err != nil {
			return nil, err
		}
	} else {
		processGccFlags(builder)
	}
	gomaccUsed := processGomaCccFlags(builder)
	if !gomaccUsed {
		processCCacheFlag(sysroot, builder)
	}

	return builder.build(), nil
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
