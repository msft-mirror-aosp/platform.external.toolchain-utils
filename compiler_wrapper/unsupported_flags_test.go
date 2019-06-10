package main

import (
	"testing"
)

func TestErrorOnFstatCheckFlag(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		_, err := calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, "-fstack-check", mainCc))
		if err == nil || err.Error() != `option "-fstack-check" is not supported; crbug/485492` {
			t.Errorf("Expected error not found. Got: %s", err)
		}
	})
}
