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
	if !isHardened(cfg) {
		t.Fatal("ConfigName: Expected hardened config got non hardened")
	}

	ConfigName = "cros.nonhardened"
	cfg, err = getRealConfig()
	if err != nil {
		t.Fatal(err)
	}
	if isHardened(cfg) {
		t.Fatal("ConfigName: Expected non hardened config got hardened")
	}

	ConfigName = "invalid"
	_, err = getRealConfig()
	if err == nil {
		t.Fatalf("ConfigName: Expected an error, got none")
	}
}

func isHardened(cfg *config) bool {
	for _, arg := range cfg.commonFlags {
		if arg == "-pie" {
			return true
		}
	}
	return false
}

func resetGlobals() {
	// Set all global variables to a defined state.
	ConfigName = "unknown"
	UseCCache = "unknown"
}
