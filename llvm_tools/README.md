# LLVM Tools

## Overview

These scripts helps automate tasks such as updating the LLVM next hash,
determing whether a new patch applies correctly, and patch management.

In addition, there are scripts that automate the process of retrieving the
git hash of LLVM from either google3, top of trunk, or for a specific SVN
version.

**NOTE: All scripts must must be run outside the chroot**

**NOTE: sudo must be permissive (i.e. **`cros_sdk`** should NOT prompt for a
password)**

## `update_packages_and_run_tryjobs.py`

### Usage

This script is used for updating a package's `LLVM_NEXT_HASH` (sys-devel/llvm,
sys-libs/compiler-rt, sys-libs/libcxx, sys-libs/libcxxabi, and
sys-libs/llvm-libunwind) and then run tryjobs after updating the git hash.

An example when this script should be run is when certain boards would like
to be tested with the updated `LLVM_NEXT_HASH`.

For example:

```
python update_packages_and_run_tryjobs.py --llvm_version tot --options
nochromesdk --builders kevin-release-tryjob nocturne-release-tryjob
```

The above example would update the packages' `LLVM_NEXT_HASH` to the top of
trunk's git hash and would submit tryjobs for kevin and nocturne boards.

For help with the command line arguments of the script, run:

```
python update_packages_and_run_tryjobs.py --help
```

## `update_chromeos_llvm_next_hash.py`

### Usage

This script is used for updating a package's/packages' `LLVM_NEXT_HASH` and
creating a change list of those changes which will uploaded for review. For
example, some changes that would be included in the change list are
the updated ebuilds, changes made to the patches of the updated packages such
as being removed or an updated patch metadata file. These changes are determined
by the `--failure_mode` option.

An example where this script would be used is when multiple packages need to
have their `LLVM_NEXT_HASH` updated.

For example:

```
python update_chromeos_llvm_next_hash.py --update_packages sys-devel/llvm
sys-libs/compiler-rt --llvm_version google3 --failure_mode disable_patches
```

The example above would update sys-devel/llvm and sys-libs/compiler-rt
`LLVM_NEXT_HASH` to the latest google3's git hash of LLVM. And the change list
may include patches that were disabled for either sys-devel/llvm or
sys-libs/compiler-rt.

For help with the command line arguments of the script, run:

```
python update_chromeos_llvm_next.py --help
```

## `llvm_patch_management.py`

### Usage

This script is used to test whether a newly added patch in a package's patch
metadata file would apply successfully. The script is also used to make sure
the patches of a package applied successfully, failed, etc., depending on the
failure mode specified.

An example of using this script is when multiple packages would like to be
tested when a new patch was added to their patch metadata file.

For example:

```
python llvm_patch_management.py --packages sys-devel/llvm sys-libs/compiler-rt
--failure_mode continue
```

The above example tests sys-devel/llvm and sys-libs/compiler-rt patch metadata
file with the failure mode `continue`.

For help with the command line arguments of the script, run:

```
python llvm_patch_management.py --help
```

## `patch_manager.py`

### Usage

This script is used when when all the command line arguments are known such as
testing a specific metadata file or a specific source tree.

For help with the command line arguments of the script, run:

```
python patch_manager.py --help
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

For example, to retrieve the commit message of a git hash of LLVM:

```
from get_llvm_hash import LLVMHash

LLVMHash.GetCommitMessageForHash(<git_hash>)
```

For example, to retrieve the latest google3 LLVM version:

```
from get_llvm_hash import GetGoogle3LLVMVersion

GetGoogle3LLVMVersion()
```
