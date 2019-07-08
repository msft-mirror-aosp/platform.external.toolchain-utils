package main

import (
	"fmt"
	"path/filepath"
	"strings"
)

func processClangTidyFlags(builder *commandBuilder) (cSrcFile string, useClangTidy bool) {
	if builder.env.getenv("WITH_TIDY") == "" {
		return "", false
	}
	srcFileSuffixes := []string{
		".c",
		".cc",
		".cpp",
		".C",
		".cxx",
		".c++",
	}
	cSrcFile = ""
	lastArg := ""
	for _, arg := range builder.args {
		if hasAtLeastOneSuffix(arg.value, srcFileSuffixes) && lastArg != "-o" {
			cSrcFile = arg.value
		}
		lastArg = arg.value
	}
	useClangTidy = cSrcFile != ""
	return cSrcFile, useClangTidy
}

func runClangTidy(env env, clangCmd *command, cSrcFile string) error {
	defaultTidyChecks := strings.Join([]string{
		"*",
		"google*",
		"-bugprone-narrowing-conversions",
		"-cppcoreguidelines-*",
		"-fuchsia-*",
		"-google-build-using-namespace",
		"-google-default-arguments",
		"-google-explicit-constructor",
		"-google-readability*",
		"-google-runtime-int",
		"-google-runtime-references",
		"-hicpp-avoid-c-arrays",
		"-hicpp-braces-around-statements",
		"-hicpp-no-array-decay",
		"-hicpp-signed-bitwise",
		"-hicpp-uppercase-literal-suffix",
		"-hicpp-use-auto",
		"-llvm-namespace-comment",
		"-misc-non-private-member-variables-in-classes",
		"-misc-unused-parameters",
		"-modernize-*",
		"-readability-*",
	}, ",")

	resourceDir, err := getClangResourceDir(env, clangCmd.path)
	if err != nil {
		return err
	}

	clangTidyPath := filepath.Join(filepath.Dir(clangCmd.path), "clang-tidy")
	clangTidyCmd := &command{
		path: clangTidyPath,
		args: append([]string{
			"-checks=" + defaultTidyChecks,
			cSrcFile,
			"--",
			"-resource-dir=" + resourceDir,
		}, clangCmd.args...),
		envUpdates: clangCmd.envUpdates,
	}

	if err := env.run(clangTidyCmd, env.stdout(), env.stderr()); err != nil {
		if _, ok := getExitCode(err); ok {
			// Note: We continue on purpose when clang-tidy fails
			// to maintain compatibility with the previous wrapper.
			fmt.Fprintf(env.stderr(), "clang-tidy failed")
		} else {
			return wrapErrorwithSourceLocf(err, "failed to call clang tidy. Command: %#v",
				clangTidyCmd)
		}
	}

	return nil
}

func hasAtLeastOneSuffix(s string, suffixes []string) bool {
	for _, suffix := range suffixes {
		if strings.HasSuffix(s, suffix) {
			return true
		}
	}
	return false
}
