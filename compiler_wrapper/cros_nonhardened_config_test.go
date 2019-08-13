// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"
)

const oldNonHardenedWrapperPathForTest = "/usr/x86_64-pc-linux-gnu/arm-none-eabi/gcc-bin/4.9.x/sysroot_wrapper"
const crosNonHardenedGoldenDir = "testdata/cros_nonhardened_golden"

func TestCrosNonHardenedConfig(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		useCCache := true
		ctx.updateConfig(oldNonHardenedWrapperPathForTest, getCrosNonHardenedConfig(useCCache))

		runGoldenRecords(ctx, crosNonHardenedGoldenDir, createSyswrapperGoldenInputs(ctx))
	})
}
