package main

import (
	"testing"
)

func TestCallRealGcc(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		wrapperCmd := ctx.newCommand(gccX86_64, "-noccache", mainCc)
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg, wrapperCmd))
		if err := verifyPath(cmd, wrapperCmd.path+".real"); err != nil {
			t.Error(err)
		}
	})
}

func TestCallRealGPlusPlus(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		wrapperCmd := ctx.newCommand("./x86_64-cros-linux-gnu-g++", "-noccache", mainCc)
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg, wrapperCmd))
		if err := verifyPath(cmd, "\\./x86_64-cros-linux-gnu-g\\+\\+\\.real"); err != nil {
			t.Error(err)
		}
	})
}

func TestConvertClangToGccFlags(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		var tests = []struct {
			in  string
			out string
		}{
			{"-march=goldmont", "-march=silvermont"},
			{"-march=goldmont-plus", "-march=silvermont"},
			{"-march=skylake", "-march=corei7"},
		}

		for _, tt := range tests {
			cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
				ctx.newCommand(gccX86_64, tt.in, mainCc)))
			if err := verifyArgCount(cmd, 0, tt.in); err != nil {
				t.Error(err)
			}
			if err := verifyArgOrder(cmd, tt.out, mainCc); err != nil {
				t.Error(err)
			}
		}
	})
}

func TestFilterUnsupportedGccFlags(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, "-Xcompiler", mainCc)))
		if err := verifyArgCount(cmd, 0, "-Xcompiler"); err != nil {
			t.Error(err)
		}
	})
}
