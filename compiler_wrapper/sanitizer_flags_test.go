package main

import (
	"testing"
)

func TestFilterUnsupportedSanitizerFlagsIfSanitizeGiven(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, "-fsanitize=kernel-address", "-Wl,--no-undefined", mainCc)))
		if err := verifyArgCount(cmd, 0, "-Wl,--no-undefined"); err != nil {
			t.Error(err)
		}

		cmd = ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, "-fsanitize=kernel-address", "-Wl,-z,defs", mainCc)))
		if err := verifyArgCount(cmd, 0, "-Wl,-z,defs"); err != nil {
			t.Error(err)
		}

		cmd = ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, "-fsanitize=kernel-address", "-D_FORTIFY_SOURCE=1", mainCc)))
		if err := verifyArgCount(cmd, 0, "-D_FORTIFY_SOURCE=1"); err != nil {
			t.Error(err)
		}

		cmd = ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, "-fsanitize=kernel-address", "-D_FORTIFY_SOURCE=2", mainCc)))
		if err := verifyArgCount(cmd, 0, "-D_FORTIFY_SOURCE=2"); err != nil {
			t.Error(err)
		}
	})
}

func TestKeepSanitizerFlagsIfNoSanitizeGiven(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, "-Wl,--no-undefined", mainCc)))
		if err := verifyArgCount(cmd, 1, "-Wl,--no-undefined"); err != nil {
			t.Error(err)
		}

		cmd = ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, "-Wl,-z,defs", mainCc)))
		if err := verifyArgCount(cmd, 1, "-Wl,-z,defs"); err != nil {
			t.Error(err)
		}

		cmd = ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, "-D_FORTIFY_SOURCE=1", mainCc)))
		if err := verifyArgCount(cmd, 1, "-D_FORTIFY_SOURCE=1"); err != nil {
			t.Error(err)
		}

		cmd = ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, "-D_FORTIFY_SOURCE=2", mainCc)))
		if err := verifyArgCount(cmd, 1, "-D_FORTIFY_SOURCE=2"); err != nil {
			t.Error(err)
		}
	})
}

func TestKeepSanitizerFlagsIfSanitizeGivenInCommonFlags(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.commonFlags = []string{"-fsanitize=kernel-address"}
		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, "-Wl,--no-undefined", mainCc)))
		if err := verifyArgCount(cmd, 1, "-Wl,--no-undefined"); err != nil {
			t.Error(err)
		}
	})
}
