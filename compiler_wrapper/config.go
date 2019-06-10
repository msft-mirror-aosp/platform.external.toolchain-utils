package main

type config struct {
	// Flags to add to gcc and clang.
	commonFlags []string
	// Flags to add to gcc only.
	gccFlags []string
	// Flags to add to clang only.
	clangFlags []string
	// Toolchain root path relative to the wrapper binary.
	rootRelPath string
	// Path of the old wrapper using the toolchain root.
	oldWrapperPath           string
	overrideOldWrapperConfig bool
}

// Full hardening.
// Temporarily disable function splitting because of chromium:434751.
var crosHardenedConfig = config{
	rootRelPath:    "../../../../..",
	oldWrapperPath: "./sysroot_wrapper.hardened.old",
	commonFlags: []string{
		"-fPIE",
		"-D_FORTIFY_SOURCE=2",
		"-fstack-protector-strong",
		"-pie",
		"-fno-omit-frame-pointer",
	},
	gccFlags: []string{
		"-Wno-unused-local-typedefs",
		"-Wno-maybe-uninitialized",
		"-fno-reorder-blocks-and-partition",
	},
	// Temporarily disable tautological-*-compare chromium:778316.
	// Temporarily add no-unknown-warning-option to deal with old clang versions.
	// Temporarily disable Wsection since kernel gets a bunch of these. chromium:778867
	// Disable "-faddrsig" since it produces object files that strip doesn't understand, chromium:915742.
	clangFlags: []string{
		"-Wno-tautological-unsigned-enum-zero-compare",
		"-Qunused-arguments",
		"-grecord-gcc-switches",
		"-Wno-section",
		"-Wno-unknown-warning-option",
		"-fno-addrsig",
		"-Wno-tautological-constant-compare",
	},
}

// Flags to be added to non-hardened toolchain.
var crosNonHardenedConfig = config{
	rootRelPath:    "../../../../..",
	oldWrapperPath: "./sysroot_wrapper.old",
	commonFlags:    []string{},
	gccFlags: []string{
		"-Wno-unused-local-typedefs",
		"-Wno-maybe-uninitialized",
		"-Wtrampolines",
		"-Wno-deprecated-declarations",
	},
	// Temporarily disable tautological-*-compare chromium:778316.
	// Temporarily add no-unknown-warning-option to deal with old clang versions.
	// Temporarily disable Wsection since kernel gets a bunch of these. chromium:778867
	clangFlags: []string{
		"-Wno-unknown-warning-option",
		"-Qunused-arguments",
		"-Wno-section",
		"-Wno-tautological-unsigned-enum-zero-compare",
		"-Wno-tautological-constant-compare",
	},
}
