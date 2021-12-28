mod patch_parsing;
mod version_control;

use anyhow::{Context, Result};
use std::path::PathBuf;
use structopt::StructOpt;

fn main() -> Result<()> {
    match Opt::from_args() {
        Opt::Show {
            cros_checkout_path,
            android_checkout_path,
            sync,
        } => show_subcmd(cros_checkout_path, android_checkout_path, sync),
        Opt::Transpose {
            cros_checkout_path,
            old_cros_ref,
            android_checkout_path,
            old_android_ref,
            sync,
            verbose,
            dry_run,
            no_commit,
        } => transpose_subcmd(TransposeOpt {
            cros_checkout_path,
            old_cros_ref,
            android_checkout_path,
            old_android_ref,
            sync,
            verbose,
            dry_run,
            no_commit,
        }),
    }
}

fn show_subcmd(
    cros_checkout_path: PathBuf,
    android_checkout_path: PathBuf,
    sync: bool,
) -> Result<()> {
    let ctx = version_control::RepoSetupContext {
        cros_checkout: cros_checkout_path,
        android_checkout: android_checkout_path,
        sync_before: sync,
    };
    ctx.setup()?;
    let cros_patches_path = ctx.cros_patches_path();
    let android_patches_path = ctx.android_patches_path();
    let cur_cros_collection = patch_parsing::PatchCollection::parse_from_file(&cros_patches_path)
        .context("could not parse cros PATCHES.json")?;
    let cur_android_collection =
        patch_parsing::PatchCollection::parse_from_file(&android_patches_path)
            .context("could not parse android PATCHES.json")?;
    let merged = cur_cros_collection.union(&cur_android_collection)?;
    println!("{}", merged.serialize_patches()?);
    Ok(())
}

#[allow(dead_code)]
struct TransposeOpt {
    cros_checkout_path: PathBuf,
    old_cros_ref: String,
    android_checkout_path: PathBuf,
    old_android_ref: String,
    sync: bool,
    verbose: bool,
    dry_run: bool,
    no_commit: bool,
}

fn transpose_subcmd(args: TransposeOpt) -> Result<()> {
    let ctx = version_control::RepoSetupContext {
        cros_checkout: args.cros_checkout_path,
        android_checkout: args.android_checkout_path,
        sync_before: args.sync,
    };
    ctx.setup()?;
    let cros_patches_path = ctx.cros_patches_path();
    let android_patches_path = ctx.android_patches_path();

    // Chromium OS Patches ----------------------------------------------------
    let mut cur_cros_collection =
        patch_parsing::PatchCollection::parse_from_file(&cros_patches_path)
            .context("parsing cros PATCHES.json")?
            .filter_patches(|p| p.platforms.contains("chromiumos"));
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
            .context("parsing android PATCHES.json")?
            .filter_patches(|p| p.platforms.contains("android"));
    let new_android_patches: patch_parsing::PatchCollection = {
        let android_old_patches_json = ctx.old_android_patch_contents(&args.old_android_ref)?;
        let old_android_collection = patch_parsing::PatchCollection::parse_from_str(
            android_patches_path.parent().unwrap().to_path_buf(),
            &android_old_patches_json,
        )?;
        cur_android_collection.subtract(&old_android_collection)?
    };

    if args.dry_run {
        println!("--dry-run specified; skipping modifications");
        return Ok(());
    }

    // Transpose Patches -----------------------------------------------------
    if !new_cros_patches.is_empty() {
        new_cros_patches.transpose_write(&mut cur_android_collection)?;
    }
    if !new_android_patches.is_empty() {
        new_android_patches.transpose_write(&mut cur_cros_collection)?;
    }

    if args.no_commit {
        println!("--no-commit specified; not committing or uploading");
        return Ok(());
    }
    // Commit and upload for review ------------------------------------------
    // Note we want to check if the android patches are empty for CrOS, and
    // vice versa. This is a little counterintuitive.
    if !new_android_patches.is_empty() {
        ctx.cros_repo_upload()
            .context("uploading chromiumos changes")?;
    }
    if !new_cros_patches.is_empty() {
        ctx.android_repo_upload()
            .context("uploading android changes")?;
    }
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
        #[structopt(short, long)]
        sync: bool,
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

        /// Run repo sync before transposing.
        #[structopt(short, long)]
        sync: bool,

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
