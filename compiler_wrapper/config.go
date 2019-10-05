// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"strconv"
)

type config struct {
	// TODO: Refactor this flag into more generic configuration properties.
	isHostWrapper    bool
	isAndroidWrapper bool
	// Whether to use ccache.
	useCCache bool
	// Flags to add to gcc and clang.
	commonFlags []string
	// Flags to add to gcc only.
	gccFlags []string
	// Flags to add to clang only.
	clangFlags []string
	// Toolchain root path relative to the wrapper binary.
	rootRelPath string
	// Path of the old wrapper using the toolchain root.
	oldWrapperPath string
	// Whether to mock out the calls that the old wrapper does.
	mockOldWrapperCmds bool
	// Directory to store errors that were prevented with -Wno-error.
	newWarningsDir string
	// Version. Only used for printing via -print-cmd.
	version string
}

// Version can be set via a linker flag.
// Values fills config.version.
var Version = ""

// UseCCache can be set via a linker flag.
// Value will be passed to strconv.ParseBool.
// E.g. go build -ldflags '-X config.UseCCache=true'.
var UseCCache = "unknown"

// UseLlvmNext can be set via a linker flag.
// Value will be passed to strconv.ParseBool.
// E.g. go build -ldflags '-X config.UseLlvmNext=true'.
var UseLlvmNext = "unknown"

// ConfigName can be set via a linker flag.
// Value has to be one of:
// - "cros.hardened"
// - "cros.nonhardened"
var ConfigName = "unknown"

// Returns the configuration matching the UseCCache and ConfigName.
func getRealConfig() (*config, error) {
	useCCache, err := strconv.ParseBool(UseCCache)
	if err != nil {
		return nil, wrapErrorwithSourceLocf(err, "invalid format for UseCCache")
	}
	useLlvmNext, err := strconv.ParseBool(UseLlvmNext)
	if err != nil {
		return nil, wrapErrorwithSourceLocf(err, "invalid format for UseLLvmNext")
	}
	// FIXME: Remove comparison to old wrapper once the new wrapper has landed.
	oldWrapperPath := ""
	config, err := getConfig(ConfigName, useCCache, useLlvmNext, oldWrapperPath, Version)
	if err != nil {
		return nil, err
	}
	return config, nil
}

func getConfig(configName string, useCCache bool, useLlvmNext bool, oldWrapperPath string, version string) (*config, error) {
	cfg := config{}
	switch configName {
	case "cros.hardened":
		cfg = *crosHardenedConfig
	case "cros.nonhardened":
		cfg = *crosNonHardenedConfig
	case "cros.host":
		cfg = *crosHostConfig
	case "android":
		cfg = *androidConfig
	default:
		return nil, newErrorwithSourceLocf("unknown config name: %s", configName)
	}
	cfg.useCCache = useCCache
	if useLlvmNext {
		cfg.clangFlags = append(cfg.clangFlags, llvmNextFlags...)
	}
	cfg.oldWrapperPath = oldWrapperPath
	cfg.version = version
	return &cfg, nil
}

var llvmNextFlags = []string{
	"-Wno-reorder-init-list",
	"-Wno-final-dtor-non-final-class",
	"-Wno-implicit-int-float-conversion",
	"-Wno-return-stack-address",
}

// Full hardening.
// Temporarily disable function splitting because of chromium:434751.
var crosHardenedConfig = &config{
	rootRelPath: "../../../../..",
	commonFlags: []string{
		"-fstack-protector-strong",
		"-fPIE",
		"-pie",
		"-D_FORTIFY_SOURCE=2",
		"-fno-omit-frame-pointer",
	},
	gccFlags: []string{
		"-fno-reorder-blocks-and-partition",
		"-Wno-unused-local-typedefs",
		"-Wno-maybe-uninitialized",
	},
	// Temporarily disable tautological-*-compare chromium:778316.
	// Temporarily add no-unknown-warning-option to deal with old clang versions.
	// Temporarily disable Wsection since kernel gets a bunch of these. chromium:778867
	// Disable "-faddrsig" since it produces object files that strip doesn't understand, chromium:915742.
	clangFlags: []string{
		"-Qunused-arguments",
		"-grecord-gcc-switches",
		"-fno-addrsig",
		"-Wno-tautological-constant-compare",
		"-Wno-tautological-unsigned-enum-zero-compare",
		"-Wno-unknown-warning-option",
		"-Wno-section",
		"-static-libgcc",
		"-fuse-ld=lld",
	},
	newWarningsDir: "/tmp/fatal_clang_warnings",
}

// Flags to be added to non-hardened toolchain.
var crosNonHardenedConfig = &config{
	rootRelPath: "../../../../..",
	commonFlags: []string{},
	gccFlags: []string{
		"-Wno-maybe-uninitialized",
		"-Wno-unused-local-typedefs",
		"-Wno-deprecated-declarations",
		"-Wtrampolines",
	},
	// Temporarily disable tautological-*-compare chromium:778316.
	// Temporarily add no-unknown-warning-option to deal with old clang versions.
	// Temporarily disable Wsection since kernel gets a bunch of these. chromium:778867
	clangFlags: []string{
		"-Qunused-arguments",
		"-Wno-tautological-constant-compare",
		"-Wno-tautological-unsigned-enum-zero-compare",
		"-Wno-unknown-warning-option",
		"-Wno-section",
		"-static-libgcc",
	},
	newWarningsDir: "/tmp/fatal_clang_warnings",
}

// Flags to be added to host toolchain.
var crosHostConfig = &config{
	isHostWrapper: true,
	rootRelPath:   "../..",
	commonFlags:   []string{},
	gccFlags: []string{
		"-Wno-maybe-uninitialized",
		"-Wno-unused-local-typedefs",
		"-Wno-deprecated-declarations",
	},
	// Temporarily disable tautological-*-compare chromium:778316.
	// Temporarily add no-unknown-warning-option to deal with old clang versions.
	clangFlags: []string{
		"-Qunused-arguments",
		"-grecord-gcc-switches",
		"-fno-addrsig",
		"-fuse-ld=lld",
		"-Wno-unused-local-typedefs",
		"-Wno-deprecated-declarations",
		"-Wno-tautological-constant-compare",
		"-Wno-tautological-unsigned-enum-zero-compare",
		"-Wno-unknown-warning-option",
	},
	newWarningsDir: "/tmp/fatal_clang_warnings",
}

var androidConfig = &config{
	isHostWrapper:    false,
	isAndroidWrapper: true,
	rootRelPath:      "./",
	commonFlags:      []string{},
	gccFlags:         []string{},
	clangFlags:       []string{},
	newWarningsDir:   "/tmp/fatal_clang_warnings",
}
