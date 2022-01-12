use std::path::Path;
use std::process::Command;

use anyhow::{bail, ensure, Result};

/// Return the Android checkout's current llvm version.
///
/// This uses android_version.get_svn_revision_number, a python function
/// that can't be executed directly. We spawn a Python3 program
/// to run it and get the result from that.
pub fn get_android_llvm_version(android_checkout: &Path) -> Result<String> {
    let mut command = Command::new("python3");
    let llvm_android_dir = android_checkout.join("toolchain/llvm_android");
    ensure!(
        llvm_android_dir.is_dir(),
        "can't get android llvm version; {} is not a directory",
        llvm_android_dir.display()
    );
    command.current_dir(llvm_android_dir);
    command.args([
        "-c",
        "import android_version; print(android_version.get_svn_revision_number(), end='')",
    ]);
    let output = command.output()?;
    if !output.status.success() {
        bail!(
            "could not get android llvm version: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }
    let out_string = String::from_utf8(output.stdout)?.trim().to_string();
    Ok(out_string)
}
