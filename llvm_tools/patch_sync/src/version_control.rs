use anyhow::{anyhow, bail, ensure, Context, Result};
use regex::Regex;
use std::ffi::OsStr;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

const CHROMIUMOS_OVERLAY_REL_PATH: &str = "src/third_party/chromiumos-overlay";
const ANDROID_LLVM_REL_PATH: &str = "toolchain/llvm_android";

/// Context struct to keep track of both Chromium OS and Android checkouts.
#[derive(Debug)]
pub struct RepoSetupContext {
    pub cros_checkout: PathBuf,
    pub android_checkout: PathBuf,
    /// Run `repo sync` before doing any comparisons.
    pub sync_before: bool,
}

impl RepoSetupContext {
    pub fn setup(&self) -> Result<()> {
        if self.sync_before {
            repo_cd_cmd(&self.cros_checkout, &["sync", CHROMIUMOS_OVERLAY_REL_PATH])?;
            repo_cd_cmd(&self.android_checkout, &["sync", ANDROID_LLVM_REL_PATH])?;
        }
        Ok(())
    }

    pub fn cros_repo_upload(&self) -> Result<()> {
        let llvm_dir = self
            .cros_checkout
            .join(&CHROMIUMOS_OVERLAY_REL_PATH)
            .join("sys-devel/llvm");
        ensure!(
            llvm_dir.is_dir(),
            "CrOS LLVM dir {} is not a directory",
            llvm_dir.display()
        );
        Self::rev_bump_llvm(&llvm_dir)?;
        Self::repo_upload(
            &self.cros_checkout,
            CHROMIUMOS_OVERLAY_REL_PATH,
            &Self::build_commit_msg("android", "chromiumos", "BUG=None\nTEST=CQ"),
        )
    }

    pub fn android_repo_upload(&self) -> Result<()> {
        Self::repo_upload(
            &self.android_checkout,
            ANDROID_LLVM_REL_PATH,
            &Self::build_commit_msg("chromiumos", "android", "Test: N/A"),
        )
    }

    fn repo_upload(path: &Path, git_wd: &str, commit_msg: &str) -> Result<()> {
        // TODO(ajordanr): Need to clean up if there's any failures during upload.
        let git_path = &path.join(&git_wd);
        ensure!(
            git_path.is_dir(),
            "git_path {} is not a directory",
            git_path.display()
        );
        repo_cd_cmd(path, &["start", "patch_sync_branch", git_wd])?;
        git_cd_cmd(git_path, &["add", "."])?;
        git_cd_cmd(git_path, &["commit", "-m", commit_msg])?;
        repo_cd_cmd(path, &["upload", "-y", "--verify", git_wd])?;
        Ok(())
    }

    pub fn android_patches_path(&self) -> PathBuf {
        self.android_checkout
            .join(&ANDROID_LLVM_REL_PATH)
            .join("patches/PATCHES.json")
    }

    pub fn cros_patches_path(&self) -> PathBuf {
        self.cros_checkout
            .join(&CHROMIUMOS_OVERLAY_REL_PATH)
            .join("sys-devel/llvm/files/PATCHES.json")
    }

    /// Increment LLVM's revision number
    fn rev_bump_llvm(llvm_dir: &Path) -> Result<PathBuf> {
        let ebuild = find_ebuild(llvm_dir)
            .with_context(|| format!("finding ebuild in {} to rev bump", llvm_dir.display()))?;
        let ebuild_dir = ebuild.parent().unwrap();
        let suffix_matcher = Regex::new(r"-r([0-9]+)\.ebuild").unwrap();
        let ebuild_name = ebuild
            .file_name()
            .unwrap()
            .to_str()
            .ok_or_else(|| anyhow!("converting ebuild filename to utf-8"))?;
        let new_path = if let Some(captures) = suffix_matcher.captures(ebuild_name) {
            let full_suffix = captures.get(0).unwrap().as_str();
            let cur_version = captures.get(1).unwrap().as_str().parse::<u32>().unwrap();
            let new_filename =
                ebuild_name.replace(full_suffix, &format!("-r{}.ebuild", cur_version + 1_u32));
            let new_path = ebuild_dir.join(new_filename);
            fs::rename(&ebuild, &new_path)?;
            new_path
        } else {
            // File did not end in a revision. We should append -r1 to the end.
            let new_filename = ebuild.file_stem().unwrap().to_string_lossy() + "-r1.ebuild";
            let new_path = ebuild_dir.join(new_filename.as_ref());
            fs::rename(&ebuild, &new_path)?;
            new_path
        };
        Ok(new_path)
    }

    /// Return the contents of the old PATCHES.json from Chromium OS
    #[allow(dead_code)]
    pub fn old_cros_patch_contents(&self, hash: &str) -> Result<String> {
        Self::old_file_contents(
            hash,
            &self.cros_checkout.join(CHROMIUMOS_OVERLAY_REL_PATH),
            Path::new("sys-devel/llvm/files/PATCHES.json"),
        )
    }

    /// Return the contents of the old PATCHES.json from android
    #[allow(dead_code)]
    pub fn old_android_patch_contents(&self, hash: &str) -> Result<String> {
        Self::old_file_contents(
            hash,
            &self.android_checkout.join(ANDROID_LLVM_REL_PATH),
            Path::new("patches/PATCHES.json"),
        )
    }

    /// Return the contents of an old file in git
    #[allow(dead_code)]
    fn old_file_contents(hash: &str, pwd: &Path, file: &Path) -> Result<String> {
        let git_ref = format!(
            "{}:{}",
            hash,
            file.to_str()
                .ok_or_else(|| anyhow!("failed to convert filepath to str"))?
        );
        let output = git_cd_cmd(pwd, &["show", &git_ref])?;
        if !output.status.success() {
            bail!("could not get old file contents for {}", &git_ref)
        }
        String::from_utf8(output.stdout)
            .with_context(|| format!("converting {} file contents to UTF-8", &git_ref))
    }

    /// Create the commit message
    fn build_commit_msg(from: &str, to: &str, footer: &str) -> String {
        format!(
            "[patch_sync] Synchronize patches from {}\n\n\
        Copies new PATCHES.json changes from {} to {}\n\n{}",
            from, from, to, footer
        )
    }
}

/// Return the path of an ebuild located within the given directory.
fn find_ebuild(dir: &Path) -> Result<PathBuf> {
    // TODO(ajordanr): Maybe use OnceCell for this regex?
    let ebuild_matcher = Regex::new(r"(-r[0-9]+)?\.ebuild").unwrap();
    for entry in fs::read_dir(dir)? {
        let path = entry?.path();
        if let Some(name) = path.file_name() {
            if ebuild_matcher.is_match(
                name.to_str()
                    .ok_or_else(|| anyhow!("converting filepath to UTF-8"))?,
            ) {
                return Ok(path);
            }
        }
    }
    bail!("could not find ebuild")
}

/// Run a given git command from inside a specified git dir.
pub fn git_cd_cmd<I, S>(pwd: &Path, args: I) -> Result<Output>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let output = Command::new("git").current_dir(&pwd).args(args).output()?;
    if !output.status.success() {
        bail!("git command failed")
    }
    Ok(output)
}

pub fn repo_cd_cmd<I, S>(pwd: &Path, args: I) -> Result<()>
where
    I: IntoIterator<Item = S>,
    S: AsRef<OsStr>,
{
    let status = Command::new("repo").current_dir(&pwd).args(args).status()?;
    if !status.success() {
        bail!("repo command failed")
    }
    Ok(())
}

#[cfg(test)]
mod test {
    use super::*;
    use rand::prelude::Rng;
    use std::env;
    use std::fs::File;

    #[test]
    fn test_revbump_ebuild() {
        // Random number to append at the end of the test folder to prevent conflicts.
        let rng: u32 = rand::thread_rng().gen();
        let llvm_dir = env::temp_dir().join(format!("patch_sync_test_{}", rng));
        fs::create_dir(&llvm_dir).expect("creating llvm dir in temp directory");

        {
            // With revision
            let ebuild_name = "llvm-13.0_pre433403_p20211019-r10.ebuild";
            let ebuild_path = llvm_dir.join(ebuild_name);
            File::create(&ebuild_path).expect("creating test ebuild file");
            let new_ebuild_path =
                RepoSetupContext::rev_bump_llvm(&llvm_dir).expect("rev bumping the ebuild");
            assert!(new_ebuild_path.ends_with("llvm-13.0_pre433403_p20211019-r11.ebuild"));
            fs::remove_file(new_ebuild_path).expect("removing renamed ebuild file");
        }
        {
            // Without revision
            let ebuild_name = "llvm-13.0_pre433403_p20211019.ebuild";
            let ebuild_path = llvm_dir.join(ebuild_name);
            File::create(&ebuild_path).expect("creating test ebuild file");
            let new_ebuild_path =
                RepoSetupContext::rev_bump_llvm(&llvm_dir).expect("rev bumping the ebuild");
            assert!(new_ebuild_path.ends_with("llvm-13.0_pre433403_p20211019-r1.ebuild"));
            fs::remove_file(new_ebuild_path).expect("removing renamed ebuild file");
        }

        fs::remove_dir(&llvm_dir).expect("removing temp test dir");
    }
}
