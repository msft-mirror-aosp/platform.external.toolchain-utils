package main

func processGccFlags(builder *commandBuilder) {
	// Flags not supported by GCC.
	unsupported := map[string]bool{"-Xcompiler": true}

	// Conversion for flags supported by clang but not gcc.
	clangToGcc := map[string]string{
		"-march=goldmont":      "-march=silvermont",
		"-march=goldmont-plus": "-march=silvermont",
		"-march=skylake":       "-march=corei7",
	}

	builder.transformArgs(func(arg builderArg) string {
		if unsupported[arg.value] {
			return ""
		}
		if mapped, ok := clangToGcc[arg.value]; ok {
			return mapped
		}
		return arg.value
	})

	builder.path += ".real"
}
