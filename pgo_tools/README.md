# pgo_tools

This directory contains scripts used to generate and vet PGO profiles for LLVM.

If you're a Mage who wants to generate a new PGO profile for the llvm-next
release, don't! There's a job on Chrotomation that does this automatically; the
Mage should just let that run in the background.

If you're a user who wants to generate a bespoke PGO profile for LLVM,
`py/bin/pgo_tools/generate_pgo_profile` is what you want. Run it **inside of a
chroot**, and it will generate a profile for you with a pretty comprehensive,
predefined workload (building absl's tests for arm32, arm64, and a few x86_64
configs).

If you want to compare the rough performance of PGO profiles,
`py/bin/pgo_tools/benchmark_pgo_profiles` may be useful.
