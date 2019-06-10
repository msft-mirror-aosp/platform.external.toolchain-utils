package main

import (
	"testing"
)

func TestAddCommonFlags(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.commonFlags = []string{"-someflag"}
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyArgOrder(cmd, "-someflag", mainCc); err != nil {
			t.Error(err)
		}
	})
}

func TestAddGccConfigFlags(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.gccFlags = []string{"-someflag"}
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyArgOrder(cmd, "-someflag", mainCc); err != nil {
			t.Error(err)
		}
	})
}

func TestAddClangConfigFlags(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		ctx.cfg.clangFlags = []string{"-someflag"}
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(clangX86_64, mainCc)))
		if err := verifyArgOrder(cmd, "-someflag", mainCc); err != nil {
			t.Error(err)
		}
	})
}

func TestShouldForwardToOldWrapperBecauseOfArgs(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		testdata := []struct {
			arg           string
			shouldForward bool
		}{
			{"abc", false},
			{"-Xclang-path=abc", true},
			{"-clang-syntax", true},
			{"-clang-syntaxabc", false},
		}
		for _, tt := range testdata {
			if actual := shouldForwardToOldWrapper(ctx, ctx.newCommand(clangX86_64, tt.arg)); actual != tt.shouldForward {
				t.Fatalf("Forward to old wrapper incorrect for arg %s. Expected %t but was %t.", tt.arg, tt.shouldForward, actual)
			}
		}
	})
}

func TestShouldForwardToOldWrapperBecauseOfEnv(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		testdata := []struct {
			env           string
			shouldForward bool
		}{
			{"PATH=abc", false},
			{"WITH_TIDY=abc", true},
			{"FORCE_DISABLE_WERROR=abc", true},
			{"GETRUSAGE=abc", true},
			{"BISECT_STAGE=abc", true},
		}
		for _, tt := range testdata {
			ctx.env = []string{tt.env}
			if actual := shouldForwardToOldWrapper(ctx, ctx.newCommand(clangX86_64)); actual != tt.shouldForward {
				t.Fatalf("Forward to old wrapper incorrect for env %s. Expected %t but was %t.", tt.env, tt.shouldForward, actual)
			}
		}
	})
}
