package main

import (
	"strings"
	"testing"
)

func TestRemovePrintConfigArg(t *testing.T) {
	withPrintConfigTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(callCompiler(ctx, ctx.cfg, ctx.newCommand(gccX86_64, "-print-config", mainCc)))
		if err := verifyArgCount(cmd, 0, "-print-config"); err != nil {
			t.Error(err)
		}
	})
}

func TestPrintConfig(t *testing.T) {
	withPrintConfigTestContext(t, func(ctx *testContext) {
		ctx.must(callCompiler(ctx, ctx.cfg, ctx.newCommand(gccX86_64, "-print-config", mainCc)))
		if !strings.Contains(ctx.stderrString(), "wrapper config: main.config{useCCache:false") {
			t.Errorf("config not printed to stderr. Got: %s", ctx.stderrString())
		}
	})
}

func withPrintConfigTestContext(t *testing.T, work func(ctx *testContext)) {
	withTestContext(t, func(ctx *testContext) {
		// Not comparing to old wrapper as the old wrapper doesn't have a print-config command.
		ctx.cfg.oldWrapperPath = ""
		work(ctx)
	})
}
