// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"path/filepath"
	"testing"
)

const oldAndroidPathForTest = "$ANDROID_PREBUILTS/clang/host/linux-x86/clang-r353983c/bin/clang"
const androidGoldenDir = "testdata/android_golden"

func TestAndroidConfig(t *testing.T) {
	withTestContext(t, func(ctx *testContext) {
		useLlvmNext := false
		useCCache := false
		cfg, err := getConfig("android", useCCache, useLlvmNext, oldAndroidPathForTest, "123")
		if err != nil {
			t.Fatal(err)
		}
		ctx.updateConfig(cfg)

		runGoldenRecords(ctx, androidGoldenDir, []goldenFile{
			createAndroidClangPathGoldenInputs(ctx),
		})
	})
}

func createAndroidClangPathGoldenInputs(ctx *testContext) goldenFile {
	deepPath := "a/b/c/d/e/f/g/clang"
	linkedDeepPath := "symlinked/clang_other"
	ctx.writeFile(filepath.Join(ctx.tempDir, "/pathenv/clang"), "")
	ctx.symlink(deepPath, linkedDeepPath)
	return goldenFile{
		Name: "clang_path.json",
		Records: []goldenRecord{
			{
				WrapperCmd: newGoldenCmd(filepath.Join(ctx.tempDir, "clang"), mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(filepath.Join(ctx.tempDir, "clang"), mainCc),
				Cmds:       errorResults,
			},
			{
				WrapperCmd: newGoldenCmd(filepath.Join(ctx.tempDir, "clang++"), mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(deepPath, mainCc),
				Cmds:       okResults,
			},
			{
				WrapperCmd: newGoldenCmd(linkedDeepPath, mainCc),
				Cmds:       okResults,
			},
			{
				Env:        []string{"PATH=" + filepath.Join(ctx.tempDir, "/pathenv")},
				WrapperCmd: newGoldenCmd("clang", mainCc),
				Cmds:       okResults,
			},
		},
	}
}
