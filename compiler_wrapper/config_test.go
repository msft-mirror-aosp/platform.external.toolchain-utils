// Copyright 2019 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"testing"
)

func TestRealConfigWithUseCCacheFlag(t *testing.T) {
	resetGlobals()
	defer resetGlobals()
	ConfigName = "cros.hardened"

	UseCCache = "false"
	cfg, err := getRealConfig()
	if err != nil {
		t.Fatal(err)
	}
	if cfg.useCCache {
		t.Fatal("UseCCache: Expected false got true")
	}

	UseCCache = "true"
	cfg, err = getRealConfig()
	if err != nil {
		t.Fatal(err)
	}
	if !cfg.useCCache {
		t.Fatal("UseCCache: Expected true got false")
	}

	UseCCache = "invalid"
	_, err = getRealConfig()
	if err == nil {
		t.Fatalf("UseCCache: Expected an error, got none")
	}
}

func TestRealConfigWithConfigNameFlag(t *testing.T) {
	resetGlobals()
	defer resetGlobals()
	UseCCache = "false"

	ConfigName = "cros.hardened"
	cfg, err := getRealConfig()
	if err != nil {
		t.Fatal(err)
	}
	if !isSysrootHardened(cfg) || cfg.isHostWrapper {
		t.Fatalf("ConfigName: Expected sysroot hardened config. Got: %#v", cfg)
	}

	ConfigName = "cros.nonhardened"
	cfg, err = getRealConfig()
	if err != nil {
		t.Fatal(err)
	}
	if isSysrootHardened(cfg) || cfg.isHostWrapper {
		t.Fatalf("ConfigName: Expected sysroot non hardened config. Got: %#v", cfg)
	}

	ConfigName = "cros.host"
	cfg, err = getRealConfig()
	if err != nil {
		t.Fatal(err)
	}
	if !cfg.isHostWrapper {
		t.Fatalf("ConfigName: Expected clang host config. Got: %#v", cfg)
	}

	ConfigName = "invalid"
	_, err = getRealConfig()
	if err == nil {
		t.Fatalf("ConfigName: Expected an error, got none")
	}
}

func TestRealConfigWithOldWrapperPath(t *testing.T) {
	resetGlobals()
	defer resetGlobals()
	UseCCache = "false"
	ConfigName = "cros.hardened"

	OldWrapperPath = "somepath"

	cfg, err := getRealConfig()
	if err != nil {
		t.Fatal(err)
	}
	if cfg.oldWrapperPath != "somepath" {
		t.Fatalf("OldWrapperPath: Expected somepath, got %s", cfg.oldWrapperPath)
	}
}

func isSysrootHardened(cfg *config) bool {
	for _, arg := range cfg.commonFlags {
		if arg == "-pie" {
			return true
		}
	}
	return false
}

func resetGlobals() {
	// Set all global variables to a defined state.
	OldWrapperPath = ""
	ConfigName = "unknown"
	UseCCache = "unknown"
}
