# BOUT++ bisect helper

This is a somewhat hacky helper for bisecting BOUT++ problems,
especially performance regressions, as well as some useful
post-processing utilities to help with the above.

`bout_bisect` takes care of cleaning, configuring, and building
BOUT++, as well as running a model and determining if a commit is
"good" or "bad", based on one of several metrics (min runtime, mean
runtime, average time per rhs, average inversion time per rhs) or
another script. It also keeps copies of the log files for each build
and run for further analysis, as well as making a log of each build.

## Installation

Either clone this repo and:

```
pip install .
```
or install straight from GitHub:
```
pip install git+https://github.com/boutproject/bout-bisect.git
```

You may wish to use `--user -e` if you're going to modify this script.

## Requirements

`bout_bisect` works with Python >= 3.5 and requires the following
Python libraries:

- numpy
- pandas
- boututils

## Usage

Basic usage is as follows:

1. Start `git bisect`
2. Mark which commits are "good" or "bad"
3. Tell `git` to use `bout_bisect`
4. Wait!

### A brief `git bisect` primer

A `git bisect` session looks like this:

```
git bisect start
git bisect good <good-commit>
git bisect bad <bad-commit>
...
```

After specifying at least one good and one bad commit, `git` will
automatically checkout a commit in the middle of this range.

Note: See
[here](https://blog.smart.ly/2015/02/03/git-bisect-debugging-with-feature-branches/)
for how to limit `git bisect` to only merges.

We can now tell `git` to use `bout_bisect` to determine if a commit is
good or bad:

```
git bisect run bout_bisect --path=/path/to/model/directory \
                           --model=model_exe \
                           <other-arguments>
```

See the next section for more on the arguments.

`git` will now automatically bisect BOUT++, running `bout_bisect` on
each checked out commit, until it determines which is the first bad
commit. This isn't foolproof, unfortunately, so if it goes wrong, you
may want to backup the bisect log:

```
git bisect log > bisect.log
```

You can then edit this log file, for example, removing some commits
that were erroneously marked good/bad, and then reset your session and
replay your modified version:

```
git bisect replay bisect.log
```

To finish a bisect session:

```
git bisect reset
```

This will checkout the commit you were on before you started the
session.

### Using `bout_bisect`

We can now tell `git` to use `bout_bisect` to determine if a commit is
good or bad:

```
git bisect run bout_bisect --path=/path/to/model/directory \
                           --model=model_exe <arguments>
```

Any path-like arguments (e.g. `--model`, `--script`) are relative to
the `--path` argument, as `bout_bisect` will change directory to
there.

Some examples:

```
git bisect run bout_bisect --path $model_path \
                           --model $model_exe \
                           --script growth_rate.py
```

This will run `growth_rate.py` on every commit, and mark that commit
as bad if it exists with a non-zero status.

```
git bisect run bout_bisect --path $model_path \
                           --model $model_exe \
                           --metric runtime-low \
                           --good 39 \
                           --bad 44 \
                           --factor 0.2 \
                           --repeat 3
```

This will mark a commit as bad if the lowest runtime out of 3 repeats.

You can also just run `bout_bisect` by itself to see what the metric
looks like for the current commit:

```
git bisect run bout_bisect --path $model_path \
                           --model $model_exe \
                           --metric runtime-low \
                           --good 39 \
                           --bad 44 \
                           --factor 0.2 \
                           --repeat 3 \
                           --just-run
```

`--just-run` is a synonym for `--no-clean --no-configure --no-make
--no-write`: don't cleanup, configure or build BOUT++, and don't write
to the `bout_bisect` log file.
