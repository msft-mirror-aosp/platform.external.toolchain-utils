package main

import (
	"path/filepath"
	"testing"
)

func TestClangBasename(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		var tests = []struct {
			in  string
			out string
		}{
			{"./x86_64-cros-linux-gnu-clang", ".*/clang"},
			{"./x86_64-cros-linux-gnu-clang++", ".*/clang\\+\\+"},
		}

		for _, tt := range tests {
			cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
				ctx.newCommand(tt.in, "-noccache", mainCc)))
			if err := verifyPath(cmd, tt.out); err != nil {
				t.Error(err)
			}
		}
	})
}

func TestClangPathGivenClangEnv(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.env = []string{"CLANG=/a/b/clang"}
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, "-noccache", mainCc)))
		if err := verifyPath(cmd, "/a/b/clang"); err != nil {
			t.Error(err)
		}
	})
}

func TestAbsoluteClangPathBasedOnRootPath(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.rootRelPath = "somepath"
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(filepath.Join(ctx.tempDir, clangX86_64), "-noccache", mainCc)))
		if err := verifyPath(cmd, filepath.Join(ctx.tempDir, "somepath/usr/bin/clang")); err != nil {
			t.Error(err)
		}
	})
}

func TestRelativeClangPathBasedOnRootPath(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.rootRelPath = "somepath"
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, "-noccache", mainCc)))
		if err := verifyPath(cmd, "somepath/usr/bin/clang"); err != nil {
			t.Error(err)
		}
	})
}

func TestConvertGccToClangFlags(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		var tests = []struct {
			in  string
			out string
		}{
			{"-Wno-error=unused-but-set-variable", "-Wno-error=unused-variable"},
			{"-Wno-error=maybe-uninitialized", "-Wno-error=uninitialized"},
			{"-Wno-unused-but-set-variable", "-Wno-unused-variable"},
			{"-Wunused-but-set-variable", "-Wunused-variable"},
			{"-Wno-error=cpp", "-Wno-#warnings"},
			{"-Xclang-only=-abc=xyz", "-abc=xyz"},
		}

		for _, tt := range tests {
			cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
				ctx.newCommand(clangX86_64, tt.in, mainCc)))
			if err := verifyArgCount(cmd, 0, tt.in); err != nil {
				t.Error(err)
			}
			if err := verifyArgOrder(cmd, tt.out, mainCc); err != nil {
				t.Error(err)
			}
		}
	})
}

func TestFilterUnsupportedClangFlags(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		var tests = []struct {
			compiler      string
			flag          string
			expectedCount int
		}{
			{clangX86_64, "-pass-exit-codes", 0},
			{clangX86_64, "-Wclobbered", 0},
			{clangX86_64, "-Wunsafe-loop-optimizations", 0},
			{clangX86_64, "-Wlogical-op", 0},
			{clangX86_64, "-Wmissing-parameter-type", 0},
			{clangX86_64, "-Woverride-init", 0},
			{clangX86_64, "-Wold-style-declaration", 0},
			{clangX86_64, "-Wno-psabi", 0},
			{clangX86_64, "-mno-movbe", 0},
			{clangX86_64, "-Wstrict-aliasing=xyz", 0},
			{clangX86_64, "-finline-limit=xyz", 0},
			{"./armv7a-cros-linux-gnu-clang", "-ftrapv", 0},
			{"./armv7a-cros-win-gnu-clang", "-ftrapv", 1},
			{"./armv8a-cros-win-gnu-clang", "-ftrapv", 1},
			{clangX86_64, "-ftrapv", 1},
		}

		for _, tt := range tests {
			cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
				ctx.newCommand(tt.compiler, tt.flag, mainCc)))
			if err := verifyArgCount(cmd, tt.expectedCount, tt.flag); err != nil {
				t.Error(err)
			}
		}
	})
}

func TestClangArchFlags(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		var tests = []struct {
			compiler string
			flags    []string
		}{
			{"./i686_64-cros-linux-gnu-clang", []string{mainCc, "-m32", "-Xclang", "-target-feature", "-Xclang", "-movbe"}},
			{"./x86_64-cros-linux-gnu-clang", []string{mainCc, "-target", "x86_64-cros-linux-gnu"}},
		}
		for _, tt := range tests {
			cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
				ctx.newCommand(tt.compiler, mainCc)))
			if err := verifyArgOrder(cmd, tt.flags...); err != nil {
				t.Error(err)
			}
		}
	})
}

func TestClangLinkerPathProbesBinariesOnPath(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		linkerPath := filepath.Join(ctx.tempDir, "a/b/c")
		ctx.writeFile(filepath.Join(linkerPath, "x86_64-cros-linux-gnu-ld"), "")
		ctx.env = []string{"PATH=nonExistantPath:" + linkerPath}
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand("./x86_64-cros-linux-gnu-clang", mainCc)))
		if err := verifyArgOrder(cmd, "-Ba/b/c"); err != nil {
			t.Error(err)
		}
	})
}

func TestClangLinkerPathEvaluatesSymlinksForBinariesOnPath(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		realLinkerPath := filepath.Join(ctx.tempDir, "a/original/path/somelinker")
		ctx.writeFile(realLinkerPath, "")
		linkedLinkerPath := filepath.Join(ctx.tempDir, "a/linked/path/x86_64-cros-linux-gnu-ld")
		ctx.symlink(realLinkerPath, linkedLinkerPath)

		ctx.env = []string{"PATH=nonExistantPath:" + filepath.Dir(linkedLinkerPath)}
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand("./x86_64-cros-linux-gnu-clang", mainCc)))
		if err := verifyArgOrder(cmd, "-Ba/original/path"); err != nil {
			t.Error(err)
		}
	})
}

func TestClangFallbackLinkerPathRelativeToRootDir(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, mainCc)))
		if err := verifyArgOrder(cmd, "-Bbin"); err != nil {
			t.Error(err)
		}
	})
}

func TestClangLinkerPathRelativeToRootDir(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.rootRelPath = "somepath"
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, mainCc)))
		if err := verifyArgOrder(cmd, "-Bsomepath/bin"); err != nil {
			t.Error(err)
		}
	})
}
