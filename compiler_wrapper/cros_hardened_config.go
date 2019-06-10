// +build cros,hardened

package main

func getRealConfig() *config {
	return &crosHardenedConfig
}
