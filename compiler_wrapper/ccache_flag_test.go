package main

import (
	"testing"
)

func TestCallCCache(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		wrapperCmd := ctx.newCommand(gccX86_64, mainCc)
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg, wrapperCmd))
		if err := verifyPath(cmd, "/usr/bin/ccache"); err != nil {
			t.Error(err)
		}
		if err := verifyArgOrder(cmd, wrapperCmd.path+".real", mainCc); err != nil {
			t.Error(err)
		}
	})
}

func TestNotCallCCacheIfNoCCacheArgGiven(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		wrapperCmd := ctx.newCommand(gccX86_64, "-noccache", mainCc)
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg, wrapperCmd))
		if err := verifyPath(cmd, wrapperCmd.path+".real"); err != nil {
			t.Error(err)
		}
		if err := verifyArgCount(cmd, 0, "-noccache"); err != nil {
			t.Error(err)
		}
	})
}

func TestSetCacheDir(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyEnvUpdate(cmd, "CCACHE_DIR=/var/cache/distfiles/ccache"); err != nil {
			t.Error(err)
		}
	})
}

func TestSetCacheBaseDirToSysroot(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyEnvUpdate(cmd,
			"CCACHE_BASEDIR="+ctx.tempDir+"/usr/x86_64-cros-linux-gnu"); err != nil {
			t.Error(err)
		}
	})
}

func TestSetCacheUmask(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyEnvUpdate(cmd, "CCACHE_UMASK=002"); err != nil {
			t.Error(err)
		}
	})
}

func TestUpdateSandboxRewrite(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyNoEnvUpdate(cmd, "SANDBOX_WRITE"); err != nil {
			t.Error(err)
		}

		ctx.env = []string{"SANDBOX_WRITE=xyz"}
		cmd = ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyEnvUpdate(cmd,
			"SANDBOX_WRITE=xyz:/var/cache/distfiles/ccache"); err != nil {
			t.Error(err)
		}
	})
}

func TestClearCacheDisable(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyNoEnvUpdate(cmd, "SANDBOX_WRITE"); err != nil {
			t.Error(err)
		}

		ctx.env = []string{"CCACHE_DISABLE=true"}
		cmd = ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyEnvUpdate(cmd, "CCACHE_DISABLE="); err != nil {
			t.Error(err)
		}
	})
}

func TestAddCCacheCpp2FlagForClang(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, mainCc)))
		if err := verifyEnvUpdate(cmd, "CCACHE_CPP2=yes"); err != nil {
			t.Error(err)
		}
	})
}

func TestOmitCCacheCpp2FlagForGcc(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyNoEnvUpdate(cmd, "CCACHE_CPP2"); err != nil {
			t.Error(err)
		}
	})
}
