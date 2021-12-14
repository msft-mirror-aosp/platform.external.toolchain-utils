mod version_control;

use anyhow::{Context, Result};
use std::path::PathBuf;
use structopt::StructOpt;

fn main() -> Result<()> {
    match Opt::from_args() {
        Opt::Show { .. } => todo!("Opt show is not implemented yet"),
        Opt::Transpose {
            cros_checkout_path,
            old_cros_ref,
            android_checkout_path,
            old_android_ref,
            verbose,
            dry_run,
            no_commit,
        } => transpose_subcmd(TransposeOpt {
            cros_checkout_path,
            old_cros_ref,
            android_checkout_path,
            old_android_ref,
            verbose,
            dry_run,
            no_commit,
        }),
    }
}

#[allow(dead_code)]
struct TransposeOpt {
    cros_checkout_path: PathBuf,
    old_cros_ref: String,
    android_checkout_path: PathBuf,
    old_android_ref: String,
    verbose: bool,
    dry_run: bool,
    no_commit: bool,
}

fn transpose_subcmd(args: TransposeOpt) -> Result<()> {
    let ctx = version_control::RepoSetupContext {
        cros_checkout: args.cros_checkout_path,
        android_checkout: args.android_checkout_path,
        sync_before: false,
    };
    ctx.setup()?;
    let _cros_patches_path = ctx.cros_patches_path();
    let _android_patches_path = ctx.android_patches_path();

    if !args.no_commit {
        return Ok(());
    }
    // Commit and upload for review.
    ctx.cros_repo_upload()
        .context("uploading chromiumos changes")?;
    ctx.android_repo_upload()
        .context("uploading android changes")?;
    Ok(())
}

#[derive(Debug, structopt::StructOpt)]
#[structopt(name = "patch_sync", about = "A pipeline for syncing the patch code")]
enum Opt {
    /// Show a combined view of the PATCHES.json file, without making any changes.
    #[allow(dead_code)]
    Show {
        #[structopt(parse(from_os_str))]
        cros_checkout_path: PathBuf,
        #[structopt(parse(from_os_str))]
        android_checkout_path: PathBuf,
    },
    /// Transpose patches from two PATCHES.json files
    /// to each other.
    Transpose {
        #[structopt(long = "cros-checkout", parse(from_os_str))]
        /// Path to the ChromiumOS source repo checkout.
        cros_checkout_path: PathBuf,

        #[structopt(long = "overlay-base-ref")]
        /// Git ref (e.g. hash) for the ChromiumOS overlay to use as the base.
        old_cros_ref: String,

        #[structopt(long = "aosp-checkout", parse(from_os_str))]
        /// Path to the Android Open Source Project source repo checkout.
        android_checkout_path: PathBuf,

        #[structopt(long = "aosp-base-ref")]
        /// Git ref (e.g. hash) for the llvm_android repo to use as the base.
        old_android_ref: String,

        #[structopt(short, long)]
        /// Print information to stdout
        verbose: bool,

        #[structopt(long)]
        /// Do not change any files. Useful in combination with `--verbose`
        /// Implies `--no-commit` and `--no-upload`.
        dry_run: bool,

        #[structopt(long)]
        /// Do not commit any changes made.
        /// Implies `--no-upload`.
        no_commit: bool,
    },
}
