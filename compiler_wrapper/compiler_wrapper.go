package main

import (
	"log"
	"path/filepath"
	"strings"
)

func calcCompilerCommand(env env, cfg *config, wrapperCmd *command) (*command, error) {
	absWrapperDir, err := getAbsWrapperDir(env, wrapperCmd.path)
	if err != nil {
		return nil, err
	}
	rootPath := filepath.Join(absWrapperDir, cfg.rootRelPath)
	if err := checkUnsupportedFlags(wrapperCmd); err != nil {
		return nil, err
	}
	builder, err := newCommandBuilder(env, wrapperCmd)
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

func calcCompilerCommandAndCompareToOld(env env, cfg *config, wrapperCmd *command) (*command, error) {
	compilerCmd, err := calcCompilerCommand(env, cfg, wrapperCmd)
	if err != nil {
		return nil, err
	}
	if cfg.oldWrapperPath == "" {
		return compilerCmd, nil
	}
	oldCmds, err := calcOldCompilerCommands(env, cfg, wrapperCmd)
	if err != nil {
		return nil, err
	}
	if err := compilerCmd.verifySimilarTo(oldCmds[0]); err != nil {
		return nil, err
	}
	return compilerCmd, nil
}

func getAbsWrapperDir(env env, wrapperPath string) (string, error) {
	if !filepath.IsAbs(wrapperPath) {
		wrapperPath = filepath.Join(env.getwd(), wrapperPath)
	}
	evaledCmdPath, err := filepath.EvalSymlinks(wrapperPath)
	if err != nil {
		log.Printf("Unable to EvalSymlinks for %s. Error: %s", evaledCmdPath, err)
		return "", err
	}
	return filepath.Dir(evaledCmdPath), nil
}

// Whether the command should be executed by the old wrapper as we don't
// support it yet.
func shouldForwardToOldWrapper(env env, wrapperCmd *command) bool {
	for _, arg := range wrapperCmd.args {
		switch {
		case strings.HasPrefix(arg, "-Xclang-path="):
			fallthrough
		case arg == "-clang-syntax":
			return true
		}
	}
	switch {
	case env.getenv("WITH_TIDY") != "":
		fallthrough
	case env.getenv("FORCE_DISABLE_WERROR") != "":
		fallthrough
	case env.getenv("GETRUSAGE") != "":
		fallthrough
	case env.getenv("BISECT_STAGE") != "":
		return true
	}
	return false
}
