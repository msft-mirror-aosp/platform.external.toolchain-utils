// Copyright 2026 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

func warningSuppressionsForLLVM_r596125(packageNameAndCategory string) []string {
	switch packageNameAndCategory {
	// Observed and suppressed on 64 builders during testing.
	// e.g., amd64-generic-cq: https://ci.chromium.org/b/8672511972670170385.
	case "app-accessibility/brltty":
		return []string{"-Wno-incompatible-pointer-types"}
	// Observed and suppressed on 64 builders during testing.
	// e.g., amd64-generic-cq: https://ci.chromium.org/b/8672511972670170385.
	case "app-misc/utouch-evemu":
		return []string{"-Wno-incompatible-pointer-types"}
	// Observed and suppressed on 64 builders during testing.
	// e.g., amd64-generic-cq: https://ci.chromium.org/b/8672511972670170385.
	case "dev-cpp/benchmark":
		return []string{"-Wno-c2y-extensions"}
	// Observed and suppressed on 64 builders during testing.
	// e.g., amd64-generic-cq: https://ci.chromium.org/b/8672511972670170385.
	case "media-libs/libvmaf":
		return []string{"-Wno-incompatible-pointer-types"}
	// Observed and suppressed on 42 builders during testing.
	// e.g., amd64-generic-cq: https://ci.chromium.org/b/8672511972670170385.
	case "net-dialup/ppp":
		return []string{"-Wno-incompatible-pointer-types"}
	// Observed and suppressed on 1 builder during testing.
	// e.g., fizz-labstation-cq: https://ci.chromium.org/b/8672511967538293217.
	case "net-misc/taylor-uucp":
		return []string{"-Wno-incompatible-pointer-types"}
	// Observed and suppressed on 44 builders during testing.
	// e.g., asurada-cq: https://ci.chromium.org/b/8672511964500014257.
	case "net-print/brother_ql820nwb":
		return []string{"-Wno-incompatible-pointer-types"}
	// Observed and suppressed on 62 builders during testing.
	// e.g., amd64-generic-cq: https://ci.chromium.org/b/8672511972670170385.
	case "net-print/custom-cupsdrv":
		return []string{"-Wno-incompatible-pointer-types"}
	// Observed and suppressed on 67 builders during testing.
	// e.g., amd64-generic-cq: https://ci.chromium.org/b/8672511972670170385.
	case "net-wireless/bluez":
		return []string{"-Wno-incompatible-pointer-types"}
	// Observed and suppressed on 30 builders during testing.
	// e.g., amd64-generic-cq: https://ci.chromium.org/b/8672511972670170385.
	case "sys-devel/llvm":
		return []string{"-Wno-c2y-extensions"}
	// Observed and suppressed on 2 builders during testing.
	// e.g., hana-cq: https://ci.chromium.org/b/8672511967827906257.
	case "sys-devel/llvm-img":
		return []string{"-Wno-c2y-extensions"}
	// Observed and suppressed on 5 builders during testing.
	// e.g., arm-generic-cq: https://ci.chromium.org/b/8672511961157057569.
	case "sys-fs/ecryptfs-utils":
		return []string{"-Wno-incompatible-pointer-types"}
	default:
		return nil
	}
}
