// Copyright 2020 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"
)

func TestAddSlsFlagOnAarch64(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		cmd := ctx.must(callCompiler(ctx, ctx.cfg,
			ctx.newCommand(clangAarch64, mainCc)))
		if err := verifyArgOrder(cmd, "-mharden-sls=all", mainCc); err != nil {
			t.Error(err)
		}
	})
}
