#!/usr/bin/env python3

import argparse
from boututils.run_wrapper import shell, shell_safe
import os
import timeit
import numpy as np
import shutil


# Exit code to use to indicate to git bisect to skip this commit
GIT_SKIP_COMMIT_EXIT_CODE = 125

# Default path to model
MODEL_PATH = "./work_models/elm_pb"


def cleanup():
    """Make sure BOUT++ directory is clean and submodules correct

    """
    shell("make distclean")
    shell_safe(r'find src -type f -name "*\.o" -delete')

    shutil.rmtree("googletest", ignore_errors=True)
    shutil.rmtree("externalpackages/googletest", ignore_errors=True)
    shutil.rmtree("externalpackages/mpark.variant", ignore_errors=True)
    shell_safe("git submodule update --init --recursive")


def configure_bout(configure_line=None):
    """Configure BOUT++

    """

    if configure_line is None:
        configure_line = "./configure -C"
        "CXXFLAGS='-std=c++11 -fdiagnostics-color=always' "
        "--with-netcdf --enable-optimize=3 --enable-checks=no"
        "--disable-backtrace"

    shell_safe(configure_line)


def build_bout(configure_line=None):
    """Build BOUT++
    """
    shell_safe("make -j8")


def runtest(nout, repeat=5, path=None, nprocs=4, model=None):
    """Run `model` in `path` `repeat` times, returning the mean runtime
    and its standard deviation

    """
    if path is None:
        path = MODEL_PATH
    if model is None:
        model = "elm_pb"
    os.chdir(path)

    shell_safe("make")

    command = "mpirun -n {nprocs} ./{model} NOUT={nout} >/dev/null".format(
        model=model, nout=nout, nprocs=nprocs
    )

    runtime = timeit.repeat(lambda: shell_safe(command), number=1, repeat=repeat)

    return {"mean": np.mean(runtime), "std": np.std(runtime), "low": np.min(runtime)}


def git_info():
    """Return a dict of the commit hash and the date on which it was committed

    """
    _, git_commit = shell_safe("git rev-parse HEAD", pipe=True)
    _, commit_date = shell_safe("git --no-pager show -s --format=%ci", pipe=True)

    return {"commit": git_commit[:7], "date": commit_date.strip()}


def timing_is_good(good, bad, timing):
    """Return true if timing is closer to the good timing than the bad timing

    timing should be a dict containing "mean" and "std"

    """

    # Runtime halfway between the good and bad timings
    half_difference = (bad - good) / 2.0
    half_mark = good + half_difference

    return (timing["low"] < half_mark) and (timing["std"] < half_difference)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="git bisect script for performance regression"
    )
    parser.add_argument("--nout", type=int, default=100, help="Number of timesteps")
    parser.add_argument(
        "--no-clean", action="store_false", dest="clean", help="Don't clean library"
    )
    parser.add_argument(
        "--no-configure",
        action="store_false",
        dest="configure",
        help="Don't configure library",
    )
    parser.add_argument(
        "--no-make", action="store_false", dest="make", help="Don't build library"
    )
    parser.add_argument(
        "--no-write", action="store_false", dest="write", help="Don't write to file"
    )
    parser.add_argument(
        "--just-run", action="store_true", help="Don't cleanup/configure/build/write"
    )
    parser.add_argument("--repeat", type=int, default=5, help="Number of repeat runs")
    parser.add_argument("--good", default=None, help="Time for 'good' run")
    parser.add_argument("--bad", default=None, help="Time for 'bad' run")
    parser.add_argument("--path", default=None, help="Path to model")

    args = parser.parse_args()

    if (args.good is None) ^ (args.bad is None):
        raise RuntimeError("You must supply either both of good and bad, or neither")

    if args.just_run:
        args.clean = args.configure = args.make = args.write = False

    try:
        if args.clean:
            cleanup()

        if args.configure:
            configure_bout()

        if args.make:
            build_bout()

        runtime = runtest(args.nout, repeat=args.repeat)
    except RuntimeError:
        exit(GIT_SKIP_COMMIT_EXIT_CODE)

    git = git_info()

    timings = "{commit}, {date}, {mean}, {std}, {low},\n".format(**git, **runtime)

    print(timings)

    if args.write:
        with open("bisect_timings", "a") as f:
            f.write(timings)

    if args.good is not None:
        if timing_is_good(good=float(args.good), bad=float(args.bad), timing=runtime):
            exit(0)
        else:
            exit(1)
