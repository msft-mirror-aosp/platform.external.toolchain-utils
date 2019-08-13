// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"fmt"
	"io/ioutil"
	"path"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

const oldHardenedWrapperPathForTest = "/usr/x86_64-pc-linux-gnu/x86_64-cros-linux-gnu/gcc-bin/4.9.x/sysroot_wrapper.hardened"
const crosHardenedGoldenDir = "testdata/cros_hardened_golden"
const crosHardenedNoCCacheGoldenDir = "testdata/cros_hardened_noccache_golden"

func TestCrosHardenedConfig(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		useCCache := true
		ctx.updateConfig(oldHardenedWrapperPathForTest, getCrosHardenedConfig(useCCache))

		runGoldenRecords(ctx, crosHardenedGoldenDir, createSyswrapperGoldenInputs(ctx))
	})
}

func TestCrosHardenedConfigWithoutCCache(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		useCCache := false
		ctx.updateConfig(oldHardenedWrapperPathForTest, getCrosHardenedConfig(useCCache))

		// Create a copy of the old wrapper where the CCACHE_DEFAULT is false.
		if ctx.cfg.oldWrapperPath != "" {
			oldWrapperContent, err := ioutil.ReadFile(ctx.cfg.oldWrapperPath)
			if err != nil {
				t.Fatal(err)
			}
			oldWrapperContent = regexp.MustCompile(`True\s+#\s+@CCACHE_DEFAULT@`).ReplaceAll(oldWrapperContent, []byte("False #"))
			ctx.cfg.oldWrapperPath = filepath.Join(ctx.tempDir, "oldwrapper_noccache")
			if err := ioutil.WriteFile(ctx.cfg.oldWrapperPath, oldWrapperContent, 0666); err != nil {
				t.Fatal(err)
			}
		}

		// Only run the subset of the sysroot wrapper tests that execute commands.
		gomaPath := path.Join(ctx.tempDir, "gomacc")
		ctx.writeFile(gomaPath, "")
		gomaEnv := "GOMACC_PATH=" + gomaPath
		runGoldenRecords(ctx, crosHardenedNoCCacheGoldenDir, []goldenFile{
			createGccPathGoldenInputs(gomaEnv),
			createClangPathGoldenInputs(gomaEnv),
			createClangSyntaxGoldenInputs(gomaEnv),
			createBisectGoldenInputs(),
			createForceDisableWErrorGoldenInputs(),
			createClangTidyGoldenInputs(gomaEnv),
		})
	})
}

func createSyswrapperGoldenInputs(ctx *testContext) []goldenFile {
	gomaPath := path.Join(ctx.tempDir, "gomacc")
	ctx.writeFile(gomaPath, "")
	gomaEnv := "GOMACC_PATH=" + gomaPath

	return []goldenFile{
		createGccPathGoldenInputs(gomaEnv),
		createGoldenInputsForAllTargets("gcc", mainCc),
		createSysrootWrapperCommonGoldenInputs("gcc", gomaEnv),
		createSanitizerGoldenInputs("gcc"),
		createGccArgsGoldenInputs(),
		createClangSyntaxGoldenInputs(gomaEnv),
		createClangPathGoldenInputs(gomaEnv),
		createGoldenInputsForAllTargets("clang", mainCc),
		createGoldenInputsForAllTargets("clang", "-ftrapv", mainCc),
		createSysrootWrapperCommonGoldenInputs("clang", gomaEnv),
		createSanitizerGoldenInputs("clang"),
		createClangArgsGoldenInputs(),
		createBisectGoldenInputs(),
		createForceDisableWErrorGoldenInputs(),
		createClangTidyGoldenInputs(gomaEnv),
	}
}

func createGoldenInputsForAllTargets(compiler string, args ...string) goldenFile {
	argsReplacer := strings.NewReplacer(".", "", "-", "")
	return goldenFile{
		Name: fmt.Sprintf("%s_%s_target_specific.json", compiler, argsReplacer.Replace(strings.Join(args, "_"))),
		Records: []goldenRecord{
			{
				WrapperCmd: newGoldenCmd("./x86_64-cros-linux-gnu-"+compiler, args...),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd("./x86_64-cros-linux-eabi-"+compiler, args...),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd("./x86_64-cros-win-gnu-"+compiler, args...),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd("./armv7m-cros-linux-gnu-"+compiler, args...),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd("./armv7m-cros-linux-eabi-"+compiler, args...),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd("./armv7m-cros-win-gnu-"+compiler, args...),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd("./armv8m-cros-linux-gnu-"+compiler, args...),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd("./armv8m-cros-linux-eabi-"+compiler, args...),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd("./armv8m-cros-win-gnu-"+compiler, args...),
				Cmds:       okResults,
			},
		},
	}
}

func createBisectGoldenInputs() goldenFile {
	return goldenFile{
		Name: "bisect.json",
		// Disable comparing to the old wrapper as that calls the bisect_driver
		// directly from python, and the new wrapper calls it via a separate
		// sub command.
		ignoreOldWrapper: true,
		Records: []goldenRecord{
			{
				WrapperCmd: newGoldenCmd(clangX86_64, mainCc),
				Env: []string{
					"BISECT_STAGE=someBisectStage",
					"BISECT_DIR=someBisectDir",
				},
				Cmds: okResults,
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, mainCc),
				Env: []string{
					"BISECT_STAGE=someBisectStage",
					"BISECT_DIR=someBisectDir",
				},
				Cmds: errorResults,
			},
		},
	}
}

func createForceDisableWErrorGoldenInputs() goldenFile {
	return goldenFile{
		Name: "force_disable_werror.json",
		Records: []goldenRecord{
			{
				WrapperCmd: newGoldenCmd(clangX86_64, mainCc),
				Env:        []string{"FORCE_DISABLE_WERROR=1"},
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, mainCc),
				Env:        []string{"FORCE_DISABLE_WERROR=1"},
				Cmds: []commandResult{
					{
						Stderr:   "-Werror originalerror",
						ExitCode: 1,
					},
					okResult,
				},
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, mainCc),
				Env:        []string{"FORCE_DISABLE_WERROR=1"},
				Cmds: []commandResult{
					{
						Stderr:   "-Werror originalerror",
						ExitCode: 1,
					},
					errorResult,
				},
			},
		},
	}
}

func createGccPathGoldenInputs(gomaEnv string) goldenFile {
	return goldenFile{
		Name: "gcc_path.json",
		Records: []goldenRecord{
			{
				WrapperCmd: newGoldenCmd("./x86_64-cros-linux-gnu-gcc", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd("./x86_64-cros-linux-gnu-gcc", mainCc),
				Cmds:       errorResults,
			},
		},
	}
}

func createClangPathGoldenInputs(gomaEnv string) goldenFile {
	return goldenFile{
		Name: "clang_path.json",
		Records: []goldenRecord{
			{
				WrapperCmd: newGoldenCmd("./x86_64-cros-linux-gnu-clang", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd("./x86_64-cros-linux-gnu-clang", mainCc),
				Cmds:       errorResults,
			},
			{
				WrapperCmd: newGoldenCmd("./x86_64-cros-linux-gnu-clang++", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, mainCc),
				Env:        []string{"CLANG=somepath/clang"},
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, "-Xclang-path=/somedir", mainCc),
				Cmds: []commandResult{
					{Stdout: "someResourceDir"},
					okResult,
				},
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, "-Xclang-path=/somedir", mainCc),
				Env:        []string{gomaEnv},
				Cmds: []commandResult{
					{Stdout: "someResourceDir"},
					okResult,
				},
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, "-Xclang-path=/somedir", mainCc),
				Cmds: []commandResult{
					{Stdout: "someResourceDir"},
					errorResult,
				},
			},
		},
	}
}

func createClangTidyGoldenInputs(gomaEnv string) goldenFile {
	tidyEnv := "WITH_TIDY=1"
	return goldenFile{
		Name: "clangtidy.json",
		Records: []goldenRecord{
			{
				WrapperCmd: newGoldenCmd(clangX86_64, mainCc),
				Env:        []string{tidyEnv},
				Cmds: []commandResult{
					{Stdout: "someResourceDir"},
					okResult,
					okResult,
				},
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, mainCc),
				Env:        []string{tidyEnv, gomaEnv},
				Cmds: []commandResult{
					{Stdout: "someResourceDir"},
					okResult,
					okResult,
				},
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, mainCc),
				Env:        []string{tidyEnv, gomaEnv},
				Cmds: []commandResult{
					{Stdout: "someResourceDir"},
					errorResult,
					// TODO: we don't fail the compilation due to clang-tidy, as that
					// is the behavior in the old wrapper. Consider changing this in
					// the future.
					okResult,
				},
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, mainCc),
				Env:        []string{tidyEnv, gomaEnv},
				Cmds: []commandResult{
					{Stdout: "someResourceDir"},
					okResult,
					errorResult,
				},
			},
		},
	}
}

func createClangSyntaxGoldenInputs(gomaEnv string) goldenFile {
	return goldenFile{
		Name: "gcc_clang_syntax.json",
		Records: []goldenRecord{
			{
				WrapperCmd: newGoldenCmd(gccX86_64, "-clang-syntax", mainCc),
				Cmds: []commandResult{
					okResult,
					okResult,
				},
			},
			{
				WrapperCmd: newGoldenCmd(gccX86_64, "-clang-syntax", mainCc),
				Env:        []string{gomaEnv},
				Cmds: []commandResult{
					okResult,
					okResult,
				},
			},
			{
				WrapperCmd: newGoldenCmd(gccX86_64, "-clang-syntax", mainCc),
				Cmds:       errorResults,
			},
			{
				WrapperCmd: newGoldenCmd(gccX86_64, "-clang-syntax", mainCc),
				Cmds: []commandResult{
					okResult,
					errorResult,
				},
			},
		},
	}
}

func createSysrootWrapperCommonGoldenInputs(compiler string, gomaEnv string) goldenFile {
	// We are using a fixed target as all of the following args are target independent.
	wrapperPath := "./x86_64-cros-linux-gnu-" + compiler
	return goldenFile{
		Name: compiler + "_sysroot_wrapper_common.json",
		Records: []goldenRecord{
			{
				WrapperCmd: newGoldenCmd(gccX86_64, "-noccache", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(wrapperPath, mainCc),
				Env:        []string{"GOMACC_PATH=someNonExistingPath"},
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(wrapperPath, mainCc),
				Env:        []string{gomaEnv},
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(wrapperPath, "-nopie", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(wrapperPath, "-D__KERNEL__", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(wrapperPath, "--sysroot=xyz", mainCc),
				Cmds:       okResults,
			},
		},
	}
}

func createSanitizerGoldenInputs(compiler string) goldenFile {
	// We are using a fixed target as all of the following args are target independent.
	wrapperPath := "./x86_64-cros-linux-gnu-" + compiler
	return goldenFile{
		Name: compiler + "_sanitizer_args.json",
		Records: []goldenRecord{
			{
				WrapperCmd: newGoldenCmd(wrapperPath, "-fsanitize=kernel-address", "-Wl,--no-undefined", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(wrapperPath, "-fsanitize=kernel-address", "-Wl,-z,defs", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(wrapperPath, "-fsanitize=kernel-address", "-D_FORTIFY_SOURCE=1", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(wrapperPath, "-fsanitize=kernel-address", "-D_FORTIFY_SOURCE=2", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(wrapperPath, "-fsanitize=fuzzer", mainCc),
				Cmds:       okResults,
			},
		},
	}
}

func createGccArgsGoldenInputs() goldenFile {
	return goldenFile{
		Name: "gcc_specific_args.json",
		Records: []goldenRecord{
			{
				WrapperCmd: newGoldenCmd(gccX86_64, "-march=goldmont", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(gccX86_64, "-march=goldmont-plus", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(gccX86_64, "-march=skylake", mainCc),
				Cmds:       okResults,
			},
		},
	}
}

func createClangArgsGoldenInputs() goldenFile {
	return goldenFile{
		Name: "clang_specific_args.json",
		Records: []goldenRecord{
			{
				WrapperCmd: newGoldenCmd(clangX86_64, "-mno-movbe", "-pass-exit-codes", "-Wclobbered", "-Wno-psabi", "-Wlogical-op",
					"-Wmissing-parameter-type", "-Wold-style-declaration", "-Woverride-init", "-Wunsafe-loop-optimizations",
					"-Wstrict-aliasing=abc", "-finline-limit=abc", mainCc),
				Cmds: okResults,
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, "-Wno-error=cpp", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, "-Wno-error=maybe-uninitialized", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, "-Wno-error=unused-but-set-variable", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, "-Wno-unused-but-set-variable", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, "-Wunused-but-set-variable", mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(clangX86_64, "-Xclang-only=-someflag", mainCc),
				Cmds:       okResults,
			},
		},
	}
}
