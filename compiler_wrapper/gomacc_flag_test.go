// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"os"
	"path"
	"testing"
)

func TestCallGomaccIfEnvIsGivenAndValid(t *testing.T) {
	withGomaccTestContext(t, func(ctx *testContext, gomaPath string) {
		ctx.env = []string{"GOMACC_PATH=" + gomaPath}
		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyPath(cmd, gomaPath); err != nil {
			t.Error(err)
		}
		if err := verifyArgOrder(cmd, gccX86_64+".real", mainCc); err != nil {
			t.Error(err)
		}
	})
}

func TestOmitGomaccIfEnvIsGivenButInvalid(t *testing.T) {
	withGomaccTestContext(t, func(ctx *testContext, gomaPath string) {
		if err := os.Remove(gomaPath); err != nil {
			t.Fatalf("failed removing fake goma file at %q: %v", gomaPath, err)
		}

		ctx.env = []string{"GOMACC_PATH=" + gomaPath}
		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyPath(cmd, gccX86_64+".real"); err != nil {
			t.Error(err)
		}
	})
}

func TestCallGomaccIfArgIsGivenAndValid(t *testing.T) {
	withGomaccTestContext(t, func(ctx *testContext, gomaPath string) {
		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc, "--gomacc-path", gomaPath)))
		if err := verifyPath(cmd, gomaPath); err != nil {
			t.Error(err)
		}
		if err := verifyArgCount(cmd, 0, "--gomacc-path"); err != nil {
			t.Error(err)
		}
		if err := verifyArgCount(cmd, 0, gomaPath); err != nil {
			t.Error(err)
		}
		if err := verifyArgOrder(cmd, gccX86_64+".real", mainCc); err != nil {
			t.Error(err)
		}
	})
}

func TestOmitGomaccIfArgIsGivenButInvalid(t *testing.T) {
	withGomaccTestContext(t, func(ctx *testContext, gomaPath string) {
		if err := os.Remove(gomaPath); err != nil {
			t.Fatalf("failed removing fake goma file at %q: %v", gomaPath, err)
		}

		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc, "--gomacc-path", gomaPath)))
		if err := verifyPath(cmd, gccX86_64+".real"); err != nil {
			t.Error(err)
		}
	})
}

func TestErrorOnGomaccArgWithoutValue(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		stderr := ctx.mustFail(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc, "--gomacc-path")))
		if err := verifyNonInternalError(stderr, "--gomacc-path given without value"); err != nil {
			t.Error(err)
		}
	})
}

func TestOmitGomaccByDefault(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyPath(cmd, gccX86_64+".real"); err != nil {
			t.Error(err)
		}
	})
}

func withGomaccTestContext(t *testing.T, f func(*testContext, string)) {
	withTestContext(t, func(ctx *testContext) {
		gomaPath := path.Join(ctx.tempDir, "gomacc")
		// Create a file so the gomacc path is valid.
		ctx.writeFile(gomaPath, "")
		f(ctx, gomaPath)
	})
}
