package main

import (
	"path"
	"testing"
)

func TestCallGomaccIfEnvIsGivenAndValid(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		gomaPath := path.Join(ctx.tempDir, "gomacc")
		// Create a file so the gomacc path is valid.
		ctx.writeFile(gomaPath, "")
		ctx.env = []string{"GOMACC_PATH=" + gomaPath}
		wrapperCmd := ctx.newCommand(gccX86_64, mainCc)
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg, wrapperCmd))
		if err := verifyPath(cmd, gomaPath); err != nil {
			t.Error(err)
		}
		if err := verifyArgOrder(cmd, wrapperCmd.path+".real", mainCc); err != nil {
			t.Error(err)
		}
	})
}

func TestOmitGomaccIfEnvIsGivenButInvalid(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		// Note: This path does not point to a valid file.
		gomaPath := path.Join(ctx.tempDir, "gomacc")
		ctx.env = []string{"GOMACC_PATH=" + gomaPath}
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyPath(cmd, "/usr/bin/ccache"); err != nil {
			t.Error(err)
		}
	})
}

func TestOmitGomaccByDefault(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(calcCompilerCommandAndCompareToOld(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyPath(cmd, "/usr/bin/ccache"); err != nil {
			t.Error(err)
		}
	})
}
