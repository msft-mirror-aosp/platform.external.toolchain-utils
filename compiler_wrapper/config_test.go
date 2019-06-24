package main

import (
	"path/filepath"
	"testing"
)

func TestFullHardeningConfigAndGcc(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		initFullHardeningConfig(ctx)
		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyPath(cmd, "/usr/bin/ccache"); err != nil {
			t.Error(err)
		}
		if err := verifyArgOrder(cmd, gccX86_64+".real", "--sysroot=/usr/x86_64-cros-linux-gnu", "-Wno-unused-local-typedefs",
			"-Wno-maybe-uninitialized", "-fno-reorder-blocks-and-partition", "-fPIE", "-D_FORTIFY_SOURCE=2", "-fstack-protector-strong",
			"-pie", "-fno-omit-frame-pointer", "main.cc", "-mno-movbe"); err != nil {
			t.Error(err)
		}
	})
}

func TestFullHardeningConfigAndClang(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		initFullHardeningConfig(ctx)
		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, mainCc)))
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
		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyPath(cmd, "/usr/bin/ccache"); err != nil {
			t.Error(err)
		}
		if err := verifyArgOrder(cmd, gccX86_64+".real", "--sysroot=/usr/x86_64-cros-linux-gnu",
			"-Wno-unused-local-typedefs", "-Wno-maybe-uninitialized", "-Wtrampolines",
			"-Wno-deprecated-declarations", "main.cc", "-mno-movbe"); err != nil {
			t.Error(err)
		}
	})
}

func TestNonHardeningConfigAndClang(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		initNonHardeningConfig(ctx)
		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, mainCc)))
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

func TestRealConfigWithUseCCacheFlag(t *testing.T) {
	resetGlobals()
	defer resetGlobals()
	ConfigName = "cros.hardened"

	UseCCache = "false"
	cfg, err := getRealConfig()
	if err != nil {
		t.Fatal(err)
	}
	if cfg.useCCache {
		t.Fatal("UseCCache: Expected false got true")
	}

	UseCCache = "true"
	cfg, err = getRealConfig()
	if err != nil {
		t.Fatal(err)
	}
	if !cfg.useCCache {
		t.Fatal("UseCCache: Expected true got false")
	}

	UseCCache = "invalid"
	_, err = getRealConfig()
	if err == nil {
		t.Fatalf("UseCCache: Expected an error, got none")
	}
}

func TestRealConfigWithConfigNameFlag(t *testing.T) {
	resetGlobals()
	defer resetGlobals()
	UseCCache = "false"

	ConfigName = "cros.hardened"
	cfg, err := getRealConfig()
	if err != nil {
		t.Fatal(err)
	}
	if !isHardened(cfg) {
		t.Fatal("ConfigName: Expected hardened config got non hardened")
	}

	ConfigName = "cros.nonhardened"
	cfg, err = getRealConfig()
	if err != nil {
		t.Fatal(err)
	}
	if isHardened(cfg) {
		t.Fatal("ConfigName: Expected non hardened config got hardened")
	}

	ConfigName = "invalid"
	_, err = getRealConfig()
	if err == nil {
		t.Fatalf("ConfigName: Expected an error, got none")
	}
}

func isHardened(cfg *config) bool {
	for _, arg := range cfg.commonFlags {
		if arg == "-pie" {
			return true
		}
	}
	return false
}

func initFullHardeningConfig(ctx *testContext) {
	useCCache := true
	ctx.updateConfig(oldHardenedWrapperPathForTest, getCrosHardenedConfig(useCCache))
	ctx.cfg.overwriteOldWrapperCfg = false
}

func initNonHardeningConfig(ctx *testContext) {
	useCCache := true
	ctx.updateConfig(oldNonHardenedWrapperPathForTest, getCrosNonHardenedConfig(useCCache))
	ctx.cfg.overwriteOldWrapperCfg = false
}

func resetGlobals() {
	// Set all global variables to a defined state.
	ConfigName = "unknown"
	UseCCache = "unknown"
}
