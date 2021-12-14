mod patch_parsing;
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
    let cros_patches_path = ctx.cros_patches_path();
    let android_patches_path = ctx.android_patches_path();

    // Chromium OS Patches ----------------------------------------------------
    let mut cur_cros_collection =
        patch_parsing::PatchCollection::parse_from_file(&cros_patches_path)
            .context("parsing cros PATCHES.json")?;
    let new_cros_patches: patch_parsing::PatchCollection = {
        let cros_old_patches_json = ctx.old_cros_patch_contents(&args.old_cros_ref)?;
        let old_cros_collection = patch_parsing::PatchCollection::parse_from_str(
            cros_patches_path.parent().unwrap().to_path_buf(),
            &cros_old_patches_json,
        )?;
        cur_cros_collection.subtract(&old_cros_collection)?
    };

    // Android Patches -------------------------------------------------------
    let mut cur_android_collection =
        patch_parsing::PatchCollection::parse_from_file(&android_patches_path)
            .context("parsing android PATCHES.json")?;
    let new_android_patches: patch_parsing::PatchCollection = {
        let android_old_patches_json = ctx.old_android_patch_contents(&args.old_android_ref)?;
        let old_android_collection = patch_parsing::PatchCollection::parse_from_str(
            android_patches_path.parent().unwrap().to_path_buf(),
            &android_old_patches_json,
        )?;
        cur_android_collection.subtract(&old_android_collection)?
    };

    // Transpose Patches -----------------------------------------------------
    new_cros_patches.transpose_write(&mut cur_cros_collection)?;
    new_android_patches.transpose_write(&mut cur_android_collection)?;

    if !args.no_commit {
        return Ok(());
    }
    // Commit and upload for review ------------------------------------------
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
        /// Path to the ChromiumOS source repo checkout.
        #[structopt(long = "cros-checkout", parse(from_os_str))]
        cros_checkout_path: PathBuf,

        /// Git ref (e.g. hash) for the ChromiumOS overlay to use as the base.
        #[structopt(long = "overlay-base-ref")]
        old_cros_ref: String,

        /// Path to the Android Open Source Project source repo checkout.
        #[structopt(long = "aosp-checkout", parse(from_os_str))]
        android_checkout_path: PathBuf,

        /// Git ref (e.g. hash) for the llvm_android repo to use as the base.
        #[structopt(long = "aosp-base-ref")]
        old_android_ref: String,

        /// Print information to stdout
        #[structopt(short, long)]
        verbose: bool,

        /// Do not change any files. Useful in combination with `--verbose`
        /// Implies `--no-commit` and `--no-upload`.
        #[structopt(long)]
        dry_run: bool,

        /// Do not commit any changes made.
        /// Implies `--no-upload`.
        #[structopt(long)]
        no_commit: bool,
    },
}
