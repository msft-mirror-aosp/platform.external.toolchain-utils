package main

func processStackProtectorFlags(builder *commandBuilder) {
	fstackMap := map[string]bool{"-D__KERNEL__": true, "-fno-stack-protector": true, "-nodefaultlibs": true,
		"-nostdlib": true}

	fstack := false
	if builder.target.abi != "eabi" {
		for _, arg := range builder.args {
			if arg.FromUser && fstackMap[arg.Value] {
				fstack = true
				break
			}
		}
	}
	if fstack {
		builder.addPreUserArgs("-fno-stack-protector")
		builder.transformArgs(func(arg builderArg) string {
			if !arg.FromUser && arg.Value == "-fstack-protector-strong" {
				return ""
			}
			return arg.Value
		})
	}
}
