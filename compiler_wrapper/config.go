package main

import (
	"strconv"
)

type config struct {
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
	// Whether to overwrite the config in the old wrapper.
	overwriteOldWrapperCfg bool
	// Directory to store errors that were prevented with -Wno-error.
	newWarningsDir string
}

// UseCCache can be set via a linker flag.
// Value will be passed to strconv.ParseBool.
// E.g. go build -ldflags '-X config.UseCCache=true'.
var UseCCache = "unknown"

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
	config, err := getConfig(useCCache, ConfigName)
	if err != nil {
		return nil, err
	}
	return config, nil
}

func getConfig(useCCache bool, configName string) (*config, error) {
	switch configName {
	case "cros.hardened":
		return getCrosHardenedConfig(useCCache), nil
	case "cros.nonhardened":
		return getCrosNonHardenedConfig(useCCache), nil
	default:
		return nil, newErrorwithSourceLocf("unknown config name: %s", configName)
	}
}

// Full hardening.
func getCrosHardenedConfig(useCCache bool) *config {
	// Temporarily disable function splitting because of chromium:434751.
	return &config{
		useCCache:      useCCache,
		rootRelPath:    "../../../../..",
		oldWrapperPath: "./sysroot_wrapper.hardened.old",
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
		},
		newWarningsDir: "/tmp/fatal_clang_warnings",
	}
}

// Flags to be added to non-hardened toolchain.
func getCrosNonHardenedConfig(useCCache bool) *config {
	return &config{
		useCCache:      useCCache,
		rootRelPath:    "../../../../..",
		oldWrapperPath: "./sysroot_wrapper.old",
		commonFlags:    []string{},
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
		},
		newWarningsDir: "/tmp/fatal_clang_warnings",
	}
}
