package main

import (
	"testing"
)

const oldNonHardenedWrapperPathForTest = "/usr/x86_64-pc-linux-gnu/arm-none-eabi/gcc-bin/4.9.x/sysroot_wrapper"
const crosNonHardenedGoldenFile = "testdata/cros_nonhardened_golden.json"

func TestCrosNonHardenedConfig(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		useCCache := true
		ctx.updateConfig(oldNonHardenedWrapperPathForTest, getCrosNonHardenedConfig(useCCache))

		runGoldenRecords(ctx, crosNonHardenedGoldenFile, createSyswrapperGoldenInputs(ctx))
	})
}
