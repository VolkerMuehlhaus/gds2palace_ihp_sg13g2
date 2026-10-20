# Installing Palace as an Apptainer container

[Palace](https://github.com/awslabs/palace) is the EM solver that runs the models created by
gds2palace. This guide shows how to get Palace as a **container image**: one single file
that holds Palace together with all the libraries it needs.

There are two ways:

- **Download a ready-made image.** This takes a few minutes. It is the right choice for most
  users.
- **Build the image yourself.** This takes one to three hours. You need it only for a Palace
  version or setting that is not available as a download.

## A few words about the tools

**Container image.** Palace needs about 70 other software libraries to run. A container
image packs Palace and all these libraries into one file, ending in `.sif`. You can copy
this file to another computer and run it there. Nothing else needs to be installed, except
Apptainer.

**Apptainer.** This is the program that runs container images (and builds them). Its older
name is Singularity. It runs on Linux. On Windows, it runs in WSL2, a Linux system that runs
inside Windows.

**Spack.** This is a tool that downloads and compiles scientific software, here Palace and
all its libraries. You only need Spack if you build the image yourself.

## Before you start

### Windows only: install WSL2

Palace and Apptainer run on Linux only. On Windows:

1. Open the Microsoft Store and install "Ubuntu 24.04 LTS".
2. Start the Ubuntu app (or type `wsl` in a command window).
3. Do all following steps in this Ubuntu window.

### Install Apptainer

On Ubuntu, type:

```bash
sudo add-apt-repository -y ppa:apptainer/ppa
sudo apt update
sudo apt install -y apptainer
apptainer --version
```

The last command prints the installed version. For other Linux systems, see the
[Apptainer installation guide](https://apptainer.org/docs/admin/main/installation.html).

## The easy way: download the ready-made image

```bash
apptainer pull ~/palace_0181.sif oras://ghcr.io/volkermuehlhaus/palace_0181:latest
```

This downloads Palace 0.18.1 (about 310 MB) into your home folder. The image runs on all
Intel processors since 2013 (Haswell) and all AMD processors since 2017 (Zen). Continue with
[Test the image](#test-the-image) and then
[Use the image with gds2palace](#use-the-image-with-gds2palace).

## Build the image yourself

### Why your own build needs extra care

A compiler can make a program faster by using special instructions of the processor it
runs on. Newer processors have more of these instructions. Spack uses this by default: it
compiles for the exact processor of the computer that does the build.

That is fine as long as the image runs on the same computer. On another computer with an
older or different processor, the program stops with the error `Illegal instruction`. The
recipe below avoids this. It tells Spack to compile for a common level that all processors
since 2013 understand. This level is called `x86_64_v3`.

### What you need

- Linux, or WSL2 on Windows, with Apptainer installed (see above).
- One to three hours of build time. More processor cores make it faster.
- Several GB of free disk space for temporary build files.
- An internet connection. The build downloads the source code of all libraries.

### Install Spack

Spack writes the build file for Apptainer. The compiling itself happens later inside
Apptainer.

```bash
git clone --depth 1 https://github.com/spack/spack.git ~/spack
source ~/spack/share/spack/setup-env.sh
spack --version
```

The `source` line makes the `spack` command available in this terminal window. To have it
in every new window, add that line to the end of the file `~/.bashrc`.

### Step 1: Create a folder for the build

```bash
mkdir -p ~/palace-build
cd ~/palace-build
```

This folder holds only a few small text files. Run all following steps in this folder.

### Step 2: Write the recipe

The recipe is a file named `spack.yaml`. It tells Spack what to build. Copy this whole block
into the terminal:

```bash
cat > spack.yaml <<'EOF'
spack:
  concretizer:
    unify: true
  packages:
    all:
      require:
      - "target=x86_64_v3"
  container:
    format: singularity
    images:
      os: "ubuntu:24.04"
      spack: "1.2"
  specs:
    - palace@0.18.1
EOF
```

What the lines mean:

- `palace@0.18.1`: the Palace version to build.
- `target=x86_64_v3`: compile for the common processor level, so that the image runs on
  other computers too.
- `os: "ubuntu:24.04"`: the Linux system inside the image.
- `spack: "1.2"`: the Spack version that does the build inside the image.

### Step 3: Create the build file and add two fixes

First, Spack turns the recipe into a build file for Apptainer, named `palace.def`:

```bash
spack -e . containerize > palace.def
```

The build file needs two fixes before you can use it:

1. **Newer package list.** Spack keeps a list of all software it can build. The list inside
   Spack 1.2 is older than Palace 0.18.1. The first fix loads a newer list.
2. **libCEED.** libCEED is one of the libraries Palace uses. Its build always compiles for
   the processor of the build computer, even when the recipe says otherwise. Without this
   fix, the image crashes on many other computers. The second fix corrects this.

Copy this whole block into the terminal. It writes the fixes into a file and adds them to
`palace.def` at the right place:

```bash
cat > palace-fixes.sh <<'EOF'
  # Fix 1: use a newer list of Spack packages that includes Palace 0.18.1
  BUILTIN_REPO=$(find /root/.spack/package_repos -maxdepth 5 -type d -name builtin | head -1)
  (cd "$BUILTIN_REPO" && \
    git fetch --depth 1 origin 51d819e6a45961329b49cf5cb8ef1e170980b5ed && \
    git reset --hard FETCH_HEAD)
  # Fix 2: stop libCEED from compiling for the build machine's CPU only
  LIBCEED_PKG=$(find "$BUILTIN_REPO" -path '*/packages/libceed/package.py' | head -1)
  sed -i 's/"OPT=%s $(MARCHFLAG)/"MARCHFLAG=", &/' "$LIBCEED_PKG"
  grep -q '"MARCHFLAG=", "OPT=%s $(MARCHFLAG)' "$LIBCEED_PKG" || \
    { echo "ERROR: the libCEED fix did not apply"; exit 1; }
EOF
sed -i '/^  \. \/opt\/spack\/share\/spack\/setup-env\.sh$/r palace-fixes.sh' palace.def
grep -c "Fix 1" palace.def
```

The last command must print `1`. If it prints `0`, the fixes were not added. See
[For AI agents](#for-ai-agents-technical-notes) for where they belong.

### Step 4: Build the image

```bash
apptainer build ~/palace_0181.sif palace.def
```

This is the long step. Apptainer downloads a small Linux system, then compiles Palace and all
its libraries inside it. At the end, it copies only the finished programs into the image
file `~/palace_0181.sif`.

If the build stops with an error about missing permissions, try again with:

```bash
apptainer build --fakeroot ~/palace_0181.sif palace.def
```

If that fails too, use `sudo apptainer build ...` as a last resort.

## Test the image

The commands below use `~/palace_0181.sif`. If your image file has a different name, use
that name instead.

**1. Check the version:**

```bash
apptainer exec ~/palace_0181.sif palace --version
```

This prints `Palace version: 0dc74cd`. The code `0dc74cd` stands for version 0.18.1.

**2. Only for images you built yourself, check the processor level:**

```bash
apptainer exec ~/palace_0181.sif sh -c 'ls /opt/software; zcat /opt/software/linux-*/libceed-*/.spack/spack-build-out.txt.gz | grep -m1 "^CFLAGS"'
```

The first line of the output must be `linux-x86_64_v3`. The line starting with `CFLAGS` must
not contain `-march=native`. If it does, fix 2 from Step 3 is missing, and the image will
crash on other computers.

**3. Run a small example.** Palace comes with example models. This downloads the `rings`
example and runs it:

```bash
mkdir -p ~/palace-test/mesh && cd ~/palace-test
curl -fsSL -o rings.json \
  "https://raw.githubusercontent.com/awslabs/palace/v0.18.1/examples/rings/rings.json"
curl -fsSL -o mesh/rings.msh \
  "https://raw.githubusercontent.com/awslabs/palace/v0.18.1/examples/rings/mesh/rings.msh"
apptainer exec ~/palace_0181.sif palace rings.json
```

The run takes a few seconds. At the end, Palace prints an "Elapsed Time Report". The result
is in the file `postpro/terminal-M.csv`.

**4. Run the example on 2 processor cores:**

```bash
apptainer exec ~/palace_0181.sif palace -np 2 rings.json
```

Palace now prints `Running with 2 MPI processes` near the start. The result must be the same
as before.

## Use the image with gds2palace

gds2palace creates the model files. Palace in the container then solves them. The
gds2palace repository has a small script for this, [`scripts/run_palace`](../scripts/run_palace).
Change it so that it uses your image file:

```bash
#!/bin/bash
apptainer -q exec ~/palace_0181.sif palace -np 8 $1
```

- `-np 8` is the number of processor cores Palace uses. Set it to the number of cores you
  want to use.
- `-q` (quiet) hides Apptainer's own info messages, such as the note that `gocryptfs` is not
  installed. This note is harmless.

The other scripts, such as `combine_snp` for the conversion to Touchstone files, are
described in [`scripts/README.md`](../scripts/README.md).

## Build another Palace version

- **Newer version:** change `palace@0.18.1` in Step 2 to the new version. Check first if
  Spack knows it, see [For AI agents](#for-ai-agents-technical-notes). Fix 1 in Step 3 may
  need a newer package list, or may not be needed at all. Keep fix 2.
- **Palace 0.17.0:** use `palace@git.v0.17.0=0.17.0` in Step 2. This tells Spack to take the
  version directly from Palace's source code on GitHub. Fix 1 is not needed, fix 2 is.
- **Only for your own computer:** if the image only ever runs on the computer that builds it,
  remove the four `packages:` lines from Step 2 and skip fix 2. The image is then a bit
  faster on this computer, but crashes on many others.

## Problems and solutions

| Problem | Solution |
|---|---|
| `Illegal instruction` (or `signal 4`) when Palace starts solving | The image was compiled for a newer processor. Use the downloaded image, or build again with `target=x86_64_v3` and fix 2. |
| `INFO: gocryptfs not found` | Harmless. Hide it with `apptainer -q`. |
| The build stops with a permission error | Use `apptainer build --fakeroot ...`. |
| The build says the image file already exists | Delete the old `.sif` file, or use another file name. |
| Palace stops with an MPI error when you use `mpirun` | Don't put `mpirun` in front of `palace`. Use `palace -np 4` instead: `palace` already starts `mpirun` itself. |
| An example from the Palace website gives configuration errors | Take the example from the same version as your image (`v0.18.1` in the download links above). Newer examples may use options that older versions don't know. |

## For AI agents: technical notes

This section is for AI coding agents that build or debug the image for a user. It records
the facts behind the steps above.

**Verified state (2026-10-20).** Palace 0.18.1, git commit `0dc74cd`, built with the recipe
and fixes above on an AMD Ryzen AI MAX+ PRO 395 (Spack target `zen4`). The image is 311 MB.
It is published as `oras://ghcr.io/volkermuehlhaus/palace_0181:latest`, and the published
file was checked by SHA-256 against the local build. `rings` gives the same
`postpro/terminal-M.csv` with 1 and 2 MPI processes, both with the `palace` wrapper and with
`mpirun -n 2 palace-x86_64.bin`.

**Fix 1, package repo.** The `spack/ubuntu-noble:1.2` base image comes with
spack-packages' `releases/v2026.06` branch. It has no `palace@0.18.x` and lacks the MFEM pin
and METIS/ParMETIS variants it needs (spack-packages #4000, #4447). The fix checks out
`51d819e6a45961329b49cf5cb8ef1e170980b5ed`, the merge commit of #4447 ("palace: add v0.18.1
and update dependencies"), to keep the build reproducible. `git fetch --depth 1 origin
develop` gives the newest packages instead. The fix must run inside the build stage's
`%post`, before `spack -e . concretize`. `spack containerize` on the host only writes the
template and does not concretize. Check whether a version is known with
`spack versions --safe palace` against an up-to-date package repo, or by reading
`repos/spack_repo/builtin/packages/palace/package.py` on spack-packages' `develop` branch.

**Fix 2, libCEED.** For libCEED 0.13 and newer, Spack's `libceed` recipe passes
`OPT=-O3 $(MARCHFLAG) ...` to make, and libCEED's Makefile sets `MARCHFLAG` to
`-march=native` on x86. This flag comes after the `-march=x86-64-v3` that Spack's compiler
wrapper injects, so it wins. The fix adds `MARCHFLAG=` (empty) to the make command line,
which overrides the Makefile's `:=` assignments. It also removes `-march=native` from
`CEED_CPU_JIT_OPT`. Without the fix, `libceed.so` had 2130 AVX-512 (`zmm`) instructions,
and Palace crashed with `signal 4 (Illegal instruction)` on a Ryzen 9 without AVX-512 as
soon as the solve started (the libCEED backend is `/cpu/self/xsmm/blocked`). With the fix,
libCEED's `CFLAGS` are `-O3 -g -ffp-contract=fast -fopenmp-simd ...`, with no `-march`.
The `grep` in the fix stops the build if the recipe changes and the `sed` no longer matches.

**`target=` alone is not proof.** `/opt/software/linux-x86_64_v3` only shows the target
Spack requested, not flags that a package's own build system adds. To verify a build, copy
the ELF files out of the image (`apptainer exec IMG cat FILE > out`) and scan them on the host
with `objdump -d --no-show-raw-insn FILE | grep -c '%zmm'`. The image has no `objdump`.
Expected result for the verified image (406 ELF files): `zmm` only in OpenSSL `libcrypto`,
`libgfortran`, OpenMPI `libmpi` and zlib-ng `libz`. All four select those code paths by
runtime CPU detection. Palace, MFEM, libCEED, Hypre and PETSc use AVX2 (`ymm`) and no AVX-512.
OpenBLAS is built with `dynamic_dispatch` (the default) and selects its kernels at runtime.
Also grep every `/opt/software/*/*/.spack/spack-build-out.txt.gz` for `march=native`,
`mtune=native` and `-mavx512` to find other packages with the same problem.

**Early check during the build (optional).** Insert this after `spack -e . concretize` in
`%post` to stop within minutes if a package was concretized for the build machine. Use an
explicit `exit 1`: `%post` runs with `set -e`, which ignores a pipeline negated with `!`.

```bash
  spack -e . find -c --format '{target}' | sort | uniq -c
  if spack -e . find -c --format '{target}' | grep -qiE 'zen|skylake|icelake|sapphire|haswell|broadwell|cascade|x86_64_v4'; then
    echo "ERROR: host-specific CPU target in concretization"; exit 1
  fi
```

**Other practical points:**

- The build takes 1 to 3 hours. Run it in the background with the output in a log file:
  `apptainer build IMG palace.def > build.log 2>&1`.
- `apptainer build` asks before it overwrites an existing image, which hangs an unattended
  run. Build to a new file name.
- The `rings` example files come from the Palace tag that matches the image, e.g. with
  `git -C /path/to/palace show v0.18.1:examples/rings/rings.json` from a local checkout.
- Don't nest MPI: the `palace` wrapper runs `mpirun` itself. Use `palace -np N`, or call
  `mpirun -n N palace-x86_64.bin` directly.
- `target=x86_64` instead of `x86_64_v3` gives an image for any 64-bit x86 processor, with
  somewhat slower solver kernels. It has not been tested.
- The fixed image was also tested on 2026-10-20 with a gds2palace model on the AMD Ryzen 9
  without AVX-512 where the unfixed image had crashed.
- Publishing to GHCR: `gh auth refresh -h github.com -s write:packages`, then
  `gh auth token | apptainer registry login --username USER --password-stdin oras://ghcr.io`,
  then `apptainer push IMG oras://ghcr.io/USER/NAME:TAG`. New packages are private: make them
  public in the package settings on GitHub.
