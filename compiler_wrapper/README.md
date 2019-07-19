# Compiler wrapper

See the comments on the top of main.go.
Build is split into 2 steps via separate commands:
- bundle: copies the sources and the `build.py` file into
  a folder.
- build: builds the actual go binary, assuming it is executed
  from the folder created by `bundle.py`.

This allows to copy the sources to a ChromeOS / Android
package, including the build script, and then
build from there without a dependency on toolchain-utils
itself.
