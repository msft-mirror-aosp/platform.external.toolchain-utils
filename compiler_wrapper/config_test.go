package main

import (
	"path/filepath"
	"testing"
)

func TestFullHardeningConfigAndGcc(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		initFullHardeningConfig(ctx)
		wrapperCmd := ctx.newCommand(gccX86_64, mainCc)
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg, wrapperCmd))
		if err := verifyPath(cmd, "/usr/bin/ccache"); err != nil {
			t.Error(err)
		}
		if err := verifyArgOrder(cmd, wrapperCmd.path+".real", "--sysroot=/usr/x86_64-cros-linux-gnu", "-Wno-unused-local-typedefs",
			"-Wno-maybe-uninitialized", "-fno-reorder-blocks-and-partition", "-fPIE", "-D_FORTIFY_SOURCE=2", "-fstack-protector-strong",
			"-pie", "-fno-omit-frame-pointer", "main.cc", "-mno-movbe"); err != nil {
			t.Error(err)
		}
	})
}

func TestFullHardeningConfigAndClang(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		initFullHardeningConfig(ctx)
		wrapperCmd := ctx.newCommand(clangX86_64, mainCc)
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg, wrapperCmd))
		if err := verifyPath(cmd, "/usr/bin/ccache"); err != nil {
			t.Error(err)
		}
		clangPath, err := filepath.Rel(ctx.tempDir, "/usr/bin/clang")
		if err != nil {
			t.Error(err)
		}
		binPath, err := filepath.Rel(ctx.tempDir, "/bin")
		if err := verifyArgOrder(cmd, clangPath, "--sysroot=/usr/x86_64-cros-linux-gnu", "-Wno-tautological-unsigned-enum-zero-compare",
			"-Qunused-arguments", "-grecord-gcc-switches", "-Wno-section", "-Wno-unknown-warning-option", "-fno-addrsig",
			"-Wno-tautological-constant-compare", "-fPIE", "-D_FORTIFY_SOURCE=2", "-fstack-protector-strong", "-pie",
			"-fno-omit-frame-pointer", "main.cc", "-B"+binPath, "-target", "x86_64-cros-linux-gnu"); err != nil {
			t.Error(err)
		}
	})
}

func TestNonHardeningConfigAndGcc(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		initNonHardeningConfig(ctx)
		wrapperCmd := ctx.newCommand(gccX86_64, mainCc)
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg, wrapperCmd))
		if err := verifyPath(cmd, "/usr/bin/ccache"); err != nil {
			t.Error(err)
		}
		if err := verifyArgOrder(cmd, wrapperCmd.path+".real", "--sysroot=/usr/x86_64-cros-linux-gnu",
			"-Wno-unused-local-typedefs", "-Wno-maybe-uninitialized", "-Wtrampolines",
			"-Wno-deprecated-declarations", "main.cc", "-mno-movbe"); err != nil {
			t.Error(err)
		}
	})
}

func TestNonHardeningConfigAndClang(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		initNonHardeningConfig(ctx)
		wrapperCmd := ctx.newCommand(clangX86_64, mainCc)
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg, wrapperCmd))
		if err := verifyPath(cmd, "/usr/bin/ccache"); err != nil {
			t.Error(err)
		}
		clangPath, err := filepath.Rel(ctx.tempDir, "/usr/bin/clang")
		if err != nil {
			t.Error(err)
		}
		binPath, err := filepath.Rel(ctx.tempDir, "/bin")
		if err := verifyArgOrder(cmd, clangPath, "--sysroot=/usr/x86_64-cros-linux-gnu", "-Wno-unknown-warning-option",
			"-Qunused-arguments", "-Wno-section", "-Wno-tautological-unsigned-enum-zero-compare",
			"-Wno-tautological-constant-compare", "main.cc", "-B"+binPath, "-target", "x86_64-cros-linux-gnu"); err != nil {
			t.Error(err)
		}
	})
}

func initFullHardeningConfig(ctx *testContext) {
	*ctx.cfg = crosHardenedConfig
	ctx.setOldWrapperPath(oldHardenedWrapperPathForTest)
}

func initNonHardeningConfig(ctx *testContext) {
	*ctx.cfg = crosNonHardenedConfig
	ctx.setOldWrapperPath(oldNonHardenedWrapperPathForTest)
}
