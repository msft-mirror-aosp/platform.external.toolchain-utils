// +build cros,nonhardened

package main

func getRealConfig() *config {
	return &crosNonHardenedConfig
}
