// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"errors"
	"fmt"
	"io"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

func TestCallBisectDriver(t *testing.T) {
	withBisectTestContext(t, func(ctx *testContext) {
		ctx.env = []string{
			"BISECT_STAGE=someBisectStage",
			"BISECT_DIR=someBisectDir",
		}
		cmd := ctx.must(callCompiler(ctx, ctx.cfg, ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyPath(cmd, "/usr/bin/python2"); err != nil {
			t.Error(err)
		}
		if err := verifyArgOrder(cmd, "-c", regexp.QuoteMeta(bisectPythonCommand),
			"someBisectStage", "someBisectDir", filepath.Join(ctx.tempDir, gccX86_64+".real"), "--sysroot=.*", mainCc); err != nil {
			t.Error(err)
		}
	})
}

func TestCallBisectDriverWithCCache(t *testing.T) {
	withBisectTestContext(t, func(ctx *testContext) {
		ctx.cfg.useCCache = true
		cmd := ctx.must(callCompiler(ctx, ctx.cfg, ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyPath(cmd, "/usr/bin/python2"); err != nil {
			t.Error(err)
		}
		if err := verifyArgCount(cmd, 1, "/usr/bin/ccache"); err != nil {
			t.Error(err)
		}
		if err := verifyEnvUpdate(cmd, "CCACHE_DIR=.*"); err != nil {
			t.Error(err)
		}
	})
}

func TestDefaultBisectDir(t *testing.T) {
	withBisectTestContext(t, func(ctx *testContext) {
		ctx.env = []string{
			"BISECT_STAGE=someBisectStage",
		}
		cmd := ctx.must(callCompiler(ctx, ctx.cfg, ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyArgOrder(cmd, "-c", regexp.QuoteMeta(bisectPythonCommand),
			"someBisectStage", "/tmp/sysroot_bisect"); err != nil {
			t.Error(err)
		}
	})
}

func TestForwardStdOutAndStdErrAndExitCodeFromBisect(t *testing.T) {
	withBisectTestContext(t, func(ctx *testContext) {
		ctx.cmdMock = func(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
			fmt.Fprint(stdout, "somemessage")
			fmt.Fprint(stderr, "someerror")
			return newExitCodeError(23)
		}
		exitCode := callCompiler(ctx, ctx.cfg, ctx.newCommand(gccX86_64, mainCc))
		if exitCode != 23 {
			t.Errorf("unexpected exit code. Got: %d", exitCode)
		}
		if ctx.stdoutString() != "somemessage" {
			t.Errorf("stdout was not forwarded. Got: %s", ctx.stdoutString())
		}
		if ctx.stderrString() != "someerror" {
			t.Errorf("stderr was not forwarded. Got: %s", ctx.stderrString())
		}
	})
}

func TestForwardGeneralErrorFromBisect(t *testing.T) {
	withBisectTestContext(t, func(ctx *testContext) {
		ctx.cmdMock = func(cmd *command, stdin io.Reader, stdout io.Writer, stderr io.Writer) error {
			return errors.New("someerror")
		}
		stderr := ctx.mustFail(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(gccX86_64, mainCc)))
		if err := verifyInternalError(stderr); err != nil {
			t.Fatal(err)
		}
		if !strings.Contains(stderr, "someerror") {
			t.Errorf("unexpected error. Got: %s", stderr)
		}
	})
}

func withBisectTestContext(t *testing.T, work func(ctx *testContext)) {
	withTestContext(t, func(ctx *testContext) {
		// Disable comparing to the old wrapper as that calls the bisect_driver
		// directly from python, and the new wrapper calls it via a separate
		// sub command.
		ctx.cfg.oldWrapperPath = ""
		ctx.env = []string{"BISECT_STAGE=xyz"}
		work(ctx)
	})
}
