// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"os"
)

func processGomaCccFlags(builder *commandBuilder) (gomaUsed bool) {
	if gomaPath := builder.env.getenv("GOMACC_PATH"); gomaPath != "" {
		if _, err := os.Lstat(gomaPath); err == nil {
			builder.wrapPath(gomaPath)
			return true
		}
	}
	return false
}
