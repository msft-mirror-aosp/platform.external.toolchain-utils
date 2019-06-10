package main

func processPieFlags(builder *commandBuilder) {
	fpieMap := map[string]bool{"-D__KERNEL__": true, "-fPIC": true, "-fPIE": true, "-fno-PIC": true, "-fno-PIE": true,
		"-fno-pic": true, "-fno-pie": true, "-fpic": true, "-fpie": true, "-nopie": true,
		"-nostartfiles": true, "-nostdlib": true, "-pie": true, "-static": true}

	pieMap := map[string]bool{"-D__KERNEL__": true, "-A": true, "-fno-PIC": true, "-fno-PIE": true, "-fno-pic": true, "-fno-pie": true,
		"-nopie": true, "-nostartfiles": true, "-nostdlib": true, "-pie": true, "-r": true, "--shared": true,
		"-shared": true, "-static": true}

	pie := false
	fpie := false
	if builder.target.abi != "eabi" {
		for _, arg := range builder.args {
			if arg.FromUser {
				if fpieMap[arg.Value] {
					fpie = true
				}
				if pieMap[arg.Value] {
					pie = true
				}
			}
		}
	}
	builder.transformArgs(func(arg builderArg) string {
		// Remove -nopie as it is a non-standard flag.
		if arg.Value == "-nopie" {
			return ""
		}
		if fpie && !arg.FromUser && arg.Value == "-fPIE" {
			return ""
		}
		if pie && !arg.FromUser && arg.Value == "-pie" {
			return ""
		}
		return arg.Value
	})
}
