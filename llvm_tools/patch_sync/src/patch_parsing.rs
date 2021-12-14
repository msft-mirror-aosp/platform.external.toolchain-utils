use std::collections::{BTreeMap, BTreeSet};
use std::fs::{copy, File};
use std::io::{BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};

use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// JSON serde struct.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PatchDictSchema {
    pub rel_patch_path: String,
    pub start_version: Option<u64>,
    pub end_version: Option<u64>,
    pub platforms: BTreeSet<String>,
    pub metadata: Option<BTreeMap<String, serde_json::Value>>,
}

/// Struct to keep track of patches and their relative paths.
#[derive(Debug, Clone)]
pub struct PatchCollection {
    pub patches: Vec<PatchDictSchema>,
    pub workdir: PathBuf,
}

impl PatchCollection {
    /// Create a `PatchCollection` from a PATCHES.
    pub fn parse_from_file(json_file: &Path) -> Result<Self> {
        Ok(Self {
            patches: serde_json::from_reader(File::open(json_file)?)?,
            workdir: json_file
                .parent()
                .ok_or_else(|| anyhow!("failed to get json_file parent"))?
                .to_path_buf(),
        })
    }

    /// Create a `PatchCollection` from a string literal and a workdir.
    pub fn parse_from_str(workdir: PathBuf, contents: &str) -> Result<Self> {
        Ok(Self {
            patches: serde_json::from_str(contents)?,
            workdir,
        })
    }

    #[allow(dead_code)]
    /// Return true if the collection is tracking any patches.
    pub fn is_empty(&self) -> bool {
        self.patches.is_empty()
    }

    /// Compute the set-set subtraction, returning a new `PatchCollection` which
    /// keeps the minuend's wordir.
    pub fn subtract(&self, subtrahend: &Self) -> Result<Self> {
        let mut new_patches = Vec::new();
        // This is O(n^2) when it could be much faster, but n is always going to be less
        // than 1k and speed is not important here.
        for our_patch in &self.patches {
            let found_in_sub = subtrahend.patches.iter().any(|sub_patch| {
                let hash1 = subtrahend
                    .hash_from_rel_patch(sub_patch)
                    .expect("getting hash from subtrahend patch");
                let hash2 = self
                    .hash_from_rel_patch(our_patch)
                    .expect("getting hash from our patch");
                hash1 == hash2
            });
            if !found_in_sub {
                new_patches.push(our_patch.clone());
            }
        }
        Ok(Self {
            patches: new_patches,
            workdir: self.workdir.clone(),
        })
    }

    /// Copy all patches from this collection into another existing collection, and write that
    /// to the existing collection's file.
    pub fn transpose_write(&self, existing_collection: &mut Self) -> Result<()> {
        for p in &self.patches {
            let original_file_path = self.workdir.join(&p.rel_patch_path);
            let copy_file_path = existing_collection.workdir.join(&p.rel_patch_path);
            copy_create_parents(&original_file_path, &copy_file_path)?;
            existing_collection.patches.push(p.clone());
        }
        existing_collection.write_patches_json("PATCHES.json")
    }

    /// Write out the patch collection contents to a PATCHES.json file.
    fn write_patches_json(&self, filename: &str) -> Result<()> {
        let write_path = self.workdir.join(filename);
        let mut new_patches_file = File::create(&write_path)
            .with_context(|| format!("writing to {}", write_path.display()))?;

        let mut serialization_buffer = Vec::<u8>::new();
        // Four spaces to indent json serialization.
        let mut serializer = serde_json::Serializer::with_formatter(
            &mut serialization_buffer,
            serde_json::ser::PrettyFormatter::with_indent(b"    "),
        );
        self.patches
            .serialize(&mut serializer)
            .with_context(|| format!("Could not serialize JSON at {}", write_path.display()))?;
        // Append a newline at the end if not present. This is necessary to get
        // past some pre-upload hooks.
        if serialization_buffer.last() != Some(&b'\n') {
            serialization_buffer.push(b'\n');
        }
        new_patches_file.write_all(&serialization_buffer)?;
        Ok(())
    }

    fn hash_from_rel_patch(&self, patch: &PatchDictSchema) -> Result<String> {
        hash_from_patch_path(&self.workdir.join(&patch.rel_patch_path))
    }
}

/// Get the hash from the patch file contents.
///
/// Not every patch file actually contains its own hash,
/// we must compute the hash ourselves when it's not found.
fn hash_from_patch(patch_contents: impl Read) -> Result<String> {
    let mut reader = BufReader::new(patch_contents);
    let mut buf = String::new();
    reader.read_line(&mut buf)?;
    let mut first_line_iter = buf.trim().split(' ').fuse();
    let (fst_word, snd_word) = (first_line_iter.next(), first_line_iter.next());
    if let (Some("commit" | "From"), Some(hash_str)) = (fst_word, snd_word) {
        // If the first line starts with either "commit" or "From", the following
        // text is almost certainly a commit hash.
        Ok(hash_str.to_string())
    } else {
        // This is an annoying case where the patch isn't actually a commit.
        // So we'll hash the entire file, and hope that's sufficient.
        let mut hasher = Sha256::new();
        hasher.update(&buf); // Have to hash the first line.
        reader.read_to_string(&mut buf)?;
        hasher.update(buf); // Hash the rest of the file.
        let sha = hasher.finalize();
        Ok(format!("{:x}", &sha))
    }
}

fn hash_from_patch_path(patch: &Path) -> Result<String> {
    let f = File::open(patch)?;
    hash_from_patch(f)
}

/// Copy a file from one path to another, and create any parent
/// directories along the way.
fn copy_create_parents(from: &Path, to: &Path) -> Result<()> {
    let to_parent = to
        .parent()
        .with_context(|| format!("{} has no parent", to.display()))?;
    if !to_parent.exists() {
        std::fs::create_dir_all(to_parent)?;
    }

    copy(&from, &to).with_context(|| {
        format!(
            "tried to copy file from {} to {}",
            &from.display(),
            &to.display()
        )
    })?;
    Ok(())
}

#[cfg(test)]
mod test {
    use super::*;

    /// Test we can extract the hash from patch files.
    #[test]
    fn test_hash_from_patch() {
        // Example git patch from Gerrit
        let desired_hash = "004be4037e1e9c6092323c5c9268acb3ecf9176c";
        let test_file_contents = "commit 004be4037e1e9c6092323c5c9268acb3ecf9176c\n\
            Author: An Author <some_email>\n\
            Date:   Thu Aug 6 12:34:16 2020 -0700";
        assert_eq!(
            &hash_from_patch(test_file_contents.as_bytes()).unwrap(),
            desired_hash
        );

        // Example git patch from upstream
        let desired_hash = "6f85225ef3791357f9b1aa097b575b0a2b0dff48";
        let test_file_contents = "From 6f85225ef3791357f9b1aa097b575b0a2b0dff48\n\
            Mon Sep 17 00:00:00 2001\n\
            From: Another Author <another_email>\n\
            Date: Wed, 18 Aug 2021 15:03:03 -0700";
        assert_eq!(
            &hash_from_patch(test_file_contents.as_bytes()).unwrap(),
            desired_hash
        );
    }
}
