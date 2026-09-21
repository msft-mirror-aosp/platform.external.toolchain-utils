# LLVM Tools

## Overview

These scripts help automate tasks such as updating the LLVM next hash,
determining whether a new patch applies correctly, and patch management.

In addition, there are scripts that automate the process of retrieving the
git hash of LLVM from either google3, top of trunk, or for a specific SVN
version.

**NOTE: All scripts must be run outside the chroot**

**NOTE: sudo must be permissive (i.e. **`cros_sdk`** should NOT prompt for a
password)**

## update_packages_and_run_tests

### Usage

This script uploads CLs necessary to run LLVM testing at an arbitrary SHA, and
optionally kicks off a CQ run.

For example, to upload CLs for testing `llvm-next` and trigger CQ+1:

```
$ ./py/bin/llvm_tools/update_packages_and_run_tests \
  --sha llvm-next \
  --cq
```

Similarly, for updating to `google3` and testing with CQ+1:

```
$ ./py/bin/llvm_tools/update_packages_and_run_tests \
  --sha google3 \
  --cq
```

For help with the command line arguments of the script, run:

```
$ ./py/bin/llvm_tools/update_packages_and_run_tests --help
```

## patch_manager

### Usage

This script is used when all the command line arguments are known such as
testing a specific metadata file or a specific source tree.

For help with the command line arguments of the script, run:

```
$ ./py/bin/llvm_tools/patch_manager --help
```

For example, to see all the failed (if any) patches:

```
$ ./py/bin/llvm_tools/patch_manager \
  --svn_version 367622 \
  --patch_metadata_file /abs/path/to/patch/file \
  --src_path /abs/path/to/src/tree \
  --failure_mode continue
```

For example, to disable all patches that failed to apply:

```
$ ./py/bin/llvm_tools/patch_manager \
  --svn_version 367622 \
  --patch_metadata_file /abs/path/to/patch/file \
  --src_path /abs/path/to/src/tree \
  --failure_mode disable_patches
```

## Other Helpful Scripts

### `get_llvm_hash.py`

#### Usage

The script has a class that deals with retrieving either the top of trunk git
hash of LLVM, the git hash of google3, or a specific git hash of a SVN version.
It also has other functions when dealing with a git hash of LLVM.

In addition, it has a function to retrieve the latest google3 LLVM version.

For example, to retrieve the top of trunk git hash of LLVM:

```
from get_llvm_hash import LLVMHash

LLVMHash().GetTopOfTrunkGitHash()
```

For example, to retrieve the git hash of google3:

```
from get_llvm_hash import LLVMHash

LLVMHash().GetGoogle3LLVMHash()
```

For example, to retrieve the git hash of a specific SVN version:

```
from get_llvm_hash import LLVMHash

LLVMHash().GetLLVMHash(<svn_version>)
```

For example, to retrieve the latest google3 LLVM version:

```
from get_llvm_hash import GetGoogle3LLVMVersion

GetGoogle3LLVMVersion(stable=True)
```

### git_llvm_rev

This script is meant to synthesize LLVM revision numbers, and translate between
these synthesized numbers and git SHAs. Usage should be straightforward:

```
~> ./py/bin/llvm_tools/git_llvm_rev --llvm_dir llvm-project-copy/ --rev r380000
6f635f90929da9545dd696071a829a1a42f84b30
~> ./py/bin/llvm_tools/git_llvm_rev --llvm_dir llvm-project-copy/ --sha 6f635f90929da9545dd696071a829a1a42f84b30
r380000
~> ./py/bin/llvm_tools/git_llvm_rev --llvm_dir llvm-project-copy/ --sha origin/some-branch
r387778
```

**Tip**: if you put a symlink called `git-llvm-rev` to this script somewhere on
your `$PATH`, you can also use it as `git llvm-rev`.

### get_patch

#### Usage

This script updates the proper ChromeOS packages with LLVM patches of your
choosing, and copies the patches into patch folders of the packages. This tool
supports both git hashes of commits as well as GitHub pull requests.

Usage:

```
$ ./py/bin/llvm_tools/get_patch --start-ref="HEAD" 47413bb27 p:74791
```

It tries to autodetect a lot of things. For more information, please see the
`--help`. This only pulls down the patches into the current tree, commits and
uploads must be done manually.

### `revert_checker.py`

**This script is copied from upstream LLVM. Please prefer to make upstream edits,
rather than modifying this script. It's kept in a CrOS repo so we don't need an
LLVM tree to `import` this from scripts here.**

This script reports reverts which happen 'across' a certain LLVM commit.

To clarify the meaning of 'across' with an example, if we had the following
commit history (where `a -> b` notes that `b` is a direct child of `a`):

123abc -> 223abc -> 323abc -> 423abc -> 523abc

And where 423abc is a revert of 223abc, this revert is considered to be 'across'
323abc. More generally, a revert A of a parent commit B is considered to be
'across' a commit C if C is a parent of A and B is a parent of C.

Usage example:

```
./revert_checker.py -C llvm-project-copy 123abc 223abc 323abc
```

In the above example, the tool will scan all commits between 123abc and 223abc,
and all commits between 123abc and 323abc for reverts of commits which are
parents of 123abc.

### nightly_revert_checker

This is an automated wrapper around `revert_checker.py`. It checks to see if any
new reverts happened across toolchains that we're trying to ship since it was
last run. If so, it automatically cherry-picks the reverts or files a bug.

Usage example for cherry-picking:
```
$ ./py/bin/llvm_tools/nightly_revert_checker \
  --state_file state.json \
  --llvm_dir llvm-project-copy \
  --reviewers=chromium-os-mage@google.com \
  cherry-pick \
  chromeos \
  --chromeos_dir ../../../
```

### werror_logs

This tool exists to help devs reason about `-Werror` instances that _would_
break builds, were the `FORCE_DISABLE_WERROR` support in the compiler wrapper
not enabled.

Usage example:

```
$ ./py/bin/llvm_tools/werror_logs aggregate \
    --directory=${repo}/out/sdk/tmp/portage/dev-cpp/gtest-1.13.0-r12/cros-artifacts
```

## fetch_cq_size_diff

This script should be runnable both inside and outside of the chroot.

This script exists to help users fill in the llvm-next testing matrix. It's
capable of comparing the sizes of ChromeOS images, and the size of Chrome's
debuginfo. An example of this is:

```
$ ./py/bin/llvm_tools/fetch_cq_size_diff --image gs \
  gs://chromeos-image-archive/asurada-release/R122-15712.0.0/image.zip \
  gs://chromeos-image-archive/asurada-cq/R122-15712.0.0-92036-8761629109681962289/image.zip
```

For convenience, this script can also figure out what to compare from two CLs'
CQ runs, like so:

```
$ ./py/bin/llvm_tools/fetch_cq_size_diff --image cl \
  --baseline-cl https://chromium-review.googlesource.com/c/chromiumos/overlays/chromiumos-overlay/+/5126115/1 \
  --new-cl https://chromium-review.googlesource.com/c/chromiumos/overlays/board-overlays/+/5126116/3
```

In the above case, this script will find a completed CQ builder shared between
the given patchsets of `--baseline-cl` and `--new-cl`, and compare the
`image.zip` artifacts generated by those builds against each other. CQ attempts
don't have to be entirely green for this; as long as there's a shared green
board between the two runs, this script should be able to make a comparison.
