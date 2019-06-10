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
		if unsupported[arg.Value] {
			return ""
		}
		if mapped, ok := clangToGcc[arg.Value]; ok {
			return mapped
		}
		return arg.Value
	})

	builder.path += ".real"
}
