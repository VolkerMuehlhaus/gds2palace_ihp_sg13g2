# Installing Palace directly on your computer with Spack

[Palace](https://github.com/awslabs/palace) is the EM solver that runs the models created by
gds2palace. This guide shows how to install Palace directly on a Linux computer, so that you
can start it with the command `palace`, like any other program.

Installing takes one to three hours, because Palace and all its libraries are compiled from
source code.

**Is this the right guide for you?** There is a simpler alternative: a ready-made container
image, which you only download. See [building-palace-apptainer.md](building-palace-apptainer.md).

| | Direct install (this guide) | Container image |
|---|---|---|
| Time to set up | 1 to 3 hours | a few minutes (download) |
| Speed | fastest on this computer | can be a little slower on new processors |
| Copy to other computers | no | yes, one file |
| Extra program needed | no | Apptainer |

## A few words about the tools

**Spack.** Palace needs about 70 other software libraries. Spack is a tool that downloads
and compiles Palace and all these libraries, in the right versions and in the right order.

**Package list.** Spack keeps a list of all software it can build, with all known versions.
When Palace releases a new version, the list gets an update a few days or weeks later.

**Environment.** A Spack environment is a folder with a recipe file named `spack.yaml`. The
recipe says what to install. You can keep it and use it again later, e.g. for the next
Palace version.

**View.** Spack installs each program in a folder with a long, unreadable name, for example
`~/spack/opt/spack/linux-zen4/palace-0.18.1-yzannz2n3633nninwhv6kuug6pjqybpk/bin/palace`.
A view is a folder with a short name, e.g. `~/palace-current`, that always points to the
current installation. You then use `~/palace-current/bin/palace` instead of the long path.

**Processor.** Spack compiles for the exact processor of your computer. This makes Palace as
fast as possible on it. It also means that you can't copy the installation to a computer
with a different processor: it may stop there with the error `Illegal instruction`. For
other computers, use the container image.

## Before you start

You need:

- Linux. On Windows: WSL2 (install "Ubuntu 24.04 LTS" from the Microsoft Store and work in
  the Ubuntu window).
- One to three hours of build time. More processor cores make it faster.
- Several GB of free disk space.
- An internet connection.

### Install Spack

```bash
git clone --depth 1 https://github.com/spack/spack.git ~/spack
source ~/spack/share/spack/setup-env.sh
spack --version
```

The `source` line makes the `spack` command available in this terminal window. To have it
in every new window, add that line to the end of the file `~/.bashrc`.

## Step 1: Update the package list and check the Palace version

```bash
spack repo update
spack versions --safe palace
```

The first command updates Spack's package list. The second shows the Palace versions that
Spack knows. Look for `0.18.1` in the list.

If `0.18.1` is missing, switch the package list to the newest state and check again:

```bash
spack repo update --branch develop builtin
spack versions --safe palace
```

## Step 2: Create a folder for the environment

```bash
mkdir -p ~/palace-native
cd ~/palace-native
```

Run all following steps in this folder.

## Step 3: Write the recipe

Copy this whole block into the terminal:

```bash
cat > spack.yaml <<'EOF'
spack:
  concretizer:
    unify: true
  specs:
    - palace@0.18.1
  view: ~/palace-current
EOF
```

What the lines mean:

- `palace@0.18.1`: the Palace version to install.
- `view: ~/palace-current`: the short folder name that points to the installation.

## Step 4: Install

```bash
spack -e . concretize
spack -e . install
```

- `concretize` plans the installation: it chooses all libraries and their versions and
  prints the list. Packages marked `[+]` are already installed and are used again.
- `install` downloads and compiles everything that is missing. This is the long step. If
  you installed Palace with Spack before, it can be much faster.

## Step 5: Make the `palace` command available

```bash
echo 'export PATH="$HOME/palace-current/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
palace --version
```

The first line adds the view's `bin` folder to your `PATH`, the list of folders where Linux
looks for programs. The last line prints `Palace version: 0dc74cd`. The code `0dc74cd`
stands for version 0.18.1.

## Step 6: Test with a small example

Palace comes with example models. This downloads the `rings` example and runs it:

```bash
mkdir -p ~/palace-test/mesh && cd ~/palace-test
curl -fsSL -o rings.json \
  "https://raw.githubusercontent.com/awslabs/palace/v0.18.1/examples/rings/rings.json"
curl -fsSL -o mesh/rings.msh \
  "https://raw.githubusercontent.com/awslabs/palace/v0.18.1/examples/rings/mesh/rings.msh"
palace rings.json
```

The run takes a few seconds. At the end, Palace prints an "Elapsed Time Report". The result
is in the file `postpro/terminal-M.csv`.

Now run it on 2 processor cores:

```bash
palace -np 2 rings.json
```

Palace now prints `Running with 2 MPI processes` near the start. The result must be the same
as before.

## Use Palace with gds2palace

gds2palace creates the model files, and Palace solves them. The gds2palace repository has a
small script for this, [`scripts/run_palace`](../scripts/run_palace). Change it so that it
uses your installation:

```bash
#!/bin/bash
palace -np 8 $1
```

`-np 8` is the number of processor cores Palace uses. Set it to the number of cores you want
to use. The other scripts, such as `combine_snp` for the conversion to Touchstone files, are
described in [`scripts/README.md`](../scripts/README.md).

## Install another Palace version

Change `palace@0.18.1` in Step 3 to the version you want, and repeat Steps 4 to 6. The view
`~/palace-current` then points to the new version.

- If Spack doesn't know the version yet (Step 1), you can take it directly from Palace's
  source code on GitHub. For example, for 0.17.0: `palace@git.v0.17.0=0.17.0`.
- To keep several versions side by side, give each one its own environment folder and its
  own view, e.g. `view: ~/palace-0.17.0`.

## Problems and solutions

| Problem | Solution |
|---|---|
| Spack doesn't know `0.18.1` | Update the package list, see Step 1. |
| `Could not locate MPI launcher` | Palace can't find `mpirun`. Use Palace from the view (Step 5). If the error stays, install OpenMPI: `sudo apt install openmpi-bin libopenmpi-dev`. |
| Palace stops with an MPI error when you use `mpirun` | Don't put `mpirun` in front of `palace`. Use `palace -np 4` instead: `palace` already starts `mpirun` itself. |
| `Illegal instruction` on another computer | A direct install only runs on computers with the same kind of processor. Use the container image there. |
| An example from the Palace website gives configuration errors | Take the example from the same version as your installation (`v0.18.1` in the links above). Newer examples may use options that older versions don't know. |

## If you installed Palace without a view

If you installed Palace with a plain `spack install palace@0.18.1`, without an environment,
there is no `~/palace-current` folder. There are two ways to use it anyway.

**For the current terminal window only:**

```bash
spack load palace@0.18.1
```

This only works if you ran the `source ~/spack/share/spack/setup-env.sh` line in that
window. If you see an error about "shell support", that line is missing.

**Permanently, with your own links:**

```bash
PALACE_PREFIX=$(spack location -i palace@0.18.1)
mkdir -p ~/bin
ln -sf "$PALACE_PREFIX/bin/palace" ~/bin/palace
ln -sf "$PALACE_PREFIX/bin/palace-x86_64.bin" ~/bin/palace-x86_64.bin
palace --version
```

Palace consists of two files that belong together: the `palace` command, and the program
`palace-x86_64.bin` that it starts. Both need a link. If `palace --version` doesn't work,
`~/bin` is not in your `PATH` yet: add it with
`echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc`, then `source ~/.bashrc`. These links
don't update themselves: after a new installation, create them again.

## For AI agents: technical notes

This section is for AI coding agents that install Palace or debug an installation for a
user. It records the facts behind the steps above.

**Status (2026-10-20).** Palace 0.18.1 has been in spack-packages since PR #4447 ("palace:
add v0.18.1 and update dependencies", merged 2026-10-13, merge commit `51d819e`). The tag
`v0.18.1` is commit `0dc74cdf8c36c58b69b21c4a06e816048ec0b83f`, and `palace --version` prints
its short hash. This native install has not been tested end-to-end with 0.18.1. The same
package recipe has built and run in the Apptainer image, see
[building-palace-apptainer.md](building-palace-apptainer.md#for-ai-agents-technical-notes).

**Package repo.** Spack 1.x keeps the builtin package repo as a separate git clone under
`~/.spack/package_repos/<hash>/`. `spack repo list` shows the path, and
`spack config blame repos` shows which branch is configured (e.g. `branch: develop` in
`~/.spack/repos.yaml`). Depending on that configuration, `spack repo update` may stay on a
release branch that predates 0.18.1. `spack repo update --branch develop builtin` switches
to `develop` and writes that to the config; `--commit 51d819e6a45961329b49cf5cb8ef1e170980b5ed`
pins the verified state instead. Whether plain `spack repo update` is enough was not tested.
`spack versions --safe palace` lists only versions in the local package recipe;
`spack versions palace` also lists remote tags, which says nothing about whether the recipe
can build them. Before you change a user's package repo, tell them: it affects all their
Spack builds.

**Older or unknown versions.** `palace@git.vX.Y.Z=X.Y.Z` builds a git tag that has no
`version()` entry. This worked for 0.17.0. 0.18.0 and newer need the newer MFEM and
METIS/ParMETIS recipes from spack-packages #4000 and #4447, so update the package repo
for those rather than use the git-tag form.

**Processor target.** A native install compiles for the host (e.g. `linux-zen4`), and
libCEED adds `-march=native` itself. That is intended here. Never copy a native install to
another machine, and never build a container from it: use the Apptainer guide, which pins
`target=x86_64_v3` and patches libCEED.

**MPI.** The `palace` script is a wrapper that runs `mpirun -n N palace-<arch>.bin`.
`palace -np N` sets the number of processes. Wrapping `palace` in an outer `mpirun` nests
MPI and aborts. The `Could not locate MPI launcher` error means the wrapper finds no
`mpirun` in `PATH`. Spack's OpenMPI is in the view's `bin`, so this usually means Palace
runs from outside the view.

**Practical points.** Run `spack -e . install` in the background with a log file; it takes
1 to 3 hours from scratch. Take the `rings` example from the Palace tag that matches the
installed version (`git -C /path/to/palace show v0.18.1:examples/rings/rings.json` from a
local checkout works too). `palace_summary.py` in [`scripts/`](../scripts/README.md)
summarizes Palace runs of gds2palace models.
