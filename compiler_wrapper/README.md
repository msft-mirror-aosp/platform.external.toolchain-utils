# Compiler wrapper

See the comments on the top of main.go.
Build is split into 2 steps via separate commands:
- bundle: copies the sources and the `build.py` file into
  a folder.
- build: builds the actual go binary, assuming it is executed
  from the folder created by `bundle.py`.

This allows to copy the sources to a Chrome OS / Android
package, including the build script, and then
build from there without a dependency on toolchain-utils
itself.

## Update source files

Copy over sources and `build.py` to Chrome OS:
```
(chroot) /mnt/host/source/src/third_party/chromiumos-overlay/sys-devel/llvm/files/update\_compiler\_wrapper.sh
```

`build.py` is called by these ebuilds:

- third_party/chromiumos-overlay/sys-devel/llvm/llvm-11.0\_pre394483\_p20200618-r3.ebuild
- third_party/chromiumos-overlay/sys-devel/gcc/gcc-\*.ebuild

## Update compiler wrappers
```
(chroot) /mnt/host/source/src/third|_party/toolchain-utils/compiler\_wrapper/install\_compiler\_wrapper.sh
```
Generated wrappers are stored here:

- Sysroot wrapper with ccache:
  `/usr/x86_64-pc-linux-gnu/<arch>/gcc-bin/4.9.x/sysroot\_wrapper.hardened.ccache`
- Sysroot wrapper without ccache:
  `/usr/x86_64-pc-linux-gnu/<arch>/gcc-bin/4.9.x/sysroot\_wrapper.hardened.noccache`
- Clang host wrapper:
  `/usr/bin/clang\_host\_wrapper`
- Gcc host wrapper:
  `/usr/x86_64-pc-linux-gnu/gcc-bin/4.9.x/host\_wrapper`


