#!/usr/bin/env python3

from boututils.run_wrapper import shell, shell_safe
import argparse
import datetime
import glob
import numpy as np
import os
import pandas as pd
import shutil
import timeit


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
        configure_line = (
            "./configure -C "
            "CXXFLAGS='-std=c++11 -fdiagnostics-color=always' "
            "--with-netcdf --enable-optimize=3 --enable-checks=no "
            "--disable-backtrace"
        )

    print(configure_line)
    shell_safe(configure_line)


def build_bout(configure_line=None):
    """Build BOUT++
    """
    shell_safe("make -j8")


def runtest(nout, repeat=5, path=None, nprocs=4, model=None, log_dir=None):
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

    runtime = []

    for run_number in range(repeat):
        runtime.append(timeit.timeit(lambda: shell_safe(command), number=1))
        backup_log_file(log_dir, subdir="run{:02d}".format(run_number))

    return {"mean": np.mean(runtime), "std": np.std(runtime), "low": np.min(runtime)}


def git_info():
    """Return a dict of the commit hash and the date on which it was committed

    """
    _, git_commit = shell_safe("git rev-parse HEAD", pipe=True)
    _, commit_date = shell_safe("git --no-pager show -s --format=%ci", pipe=True)

    return {"commit": git_commit[:7], "date": commit_date.strip()}


def metric_is_good(good, bad, metric, metric_std=0.0, factor=0.5):
    """Return true if `metric` is closer to `good` than `bad`, assuming
    that the standard deviation is not too large

    Parameters
    ----------
    good : float
        The "good" value of the metric, should be less than bad
    bad : float
        The "bad" value of the metric, should be greater than good
    metric : float
        The metric to compare to good, bad
    metric_std : float, optional
        The standard deviation of the metric. If this is larger than
        `factor * (bad - good)`, the metric is consider "good"
    factor : float, optional
        How far between good and bad is still considered good. A
        factor of 0.5 means that if metric is less than `0.5*(bad -
        good)`, it is "good"

    """

    weighted_difference = factor * (bad - good)
    good_zone = good + weighted_difference

    print("metric is {}, max good value is {}".format(metric, good_zone))
    return (metric < good_zone) and (metric_std < weighted_difference)


def backup_log_file(directory=None, subdir=None):
    """Backup log files according to the commit

    """

    if directory is None:
        directory = "backup_logs_{:d}".format(int(datetime.datetime.now().timestamp()))

    if subdir is not None:
        new_log_directory = os.path.join(directory, subdir)
    else:
        new_log_directory = directory

    try:
        os.makedirs(new_log_directory)
    except FileExistsError:
        pass

    old_data_directory = "data"
    log_files = os.path.join(old_data_directory, "BOUT.log.*")
    logs = glob.glob(log_files)
    for log in logs:
        shutil.copy(src=log, dst=new_log_directory)


def _get_start_of_timings(logfile):
    """Return the line number of the start of the timings table
    """
    with open(logfile, "r") as f:
        for line_number, line in enumerate(f):
            if line.startswith("Sim Time"):
                return line_number


def read_timings_from_logfile(nout, directory="data", logfile="BOUT.log.0"):
    """Return a pandas dataframe of the timings table from logfile in directory

    """

    path_to_logfile = os.path.join(directory, logfile)

    start_of_timings = _get_start_of_timings(path_to_logfile)

    timing_table = pd.read_csv(
        path_to_logfile,
        sep=r"(?:\s+\|\s+|\s{2,})",
        skiprows=start_of_timings,
        nrows=nout + 2,
        engine="python",
        index_col="Sim Time",
    )

    columns = ["Calc", "Inv", "Comm", "I/O", "SOLVER"]

    for column in columns:
        timing_table[column + " (absolute)"] = timing_table["Wall Time"] * (
            timing_table[column] / 100
        )

    return timing_table


def total_rhs(timing_table):
    """Return the total number of rhs evals in timing_table
    """
    return timing_table["RHS evals"].sum()


def average_per_rhs(timing_table, column):
    """Return the average `timing_table[column]` per rhs eval
    """
    return timing_table[column].sum() / total_rhs(timing_table)


def time_per_rhs(timing_table):
    """Return the average wall time per rhs eval in timing_table
    """
    return average_per_rhs(timing_table, "Wall Time")


def average_and_std_per_rhs(timing_table, column):
    """Return the average `timing_table[column]` per rhs eval, and its
    standard deviation

    """

    value_per_rhs = timing_table[column] / timing_table["RHS evals"]
    return {"mean": value_per_rhs.mean(), "std": value_per_rhs.std()}


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
    parser.add_argument("--path", default=MODEL_PATH, help="Path to model")
    parser.add_argument("--log-dir", default="logs", help="Backup log file directory")

    # How to keep in sync with dict `metrics` below?
    metric_choices = ["runtime-low", "runtime-mean", "inv_per_rhs", "time_per_rhs"]
    parser.add_argument(
        "--metric",
        choices=metric_choices,
        default="runtime-low",
        help="What metric to use",
    )

    args = parser.parse_args()

    if (args.good is None) ^ (args.bad is None):
        raise RuntimeError("You must supply either both of good and bad, or neither")

    if args.just_run:
        args.clean = args.configure = args.make = args.write = False

    git = git_info()

    log_dir = os.path.join(args.log_dir, git["commit"])

    try:
        if args.clean:
            cleanup()

        if args.configure:
            configure_bout()

        if args.make:
            build_bout()

        runtime = runtest(args.nout, repeat=args.repeat, log_dir=log_dir)
    except RuntimeError:
        exit(GIT_SKIP_COMMIT_EXIT_CODE)

    timings = "{commit}, {date}, {mean}, {std}, {low}, {dir}\n".format(
        **git, **runtime, dir=log_dir
    )

    print(timings)

    if args.write:
        with open("bisect_timings", "a") as f:
            f.write(timings)

    if args.good is not None:
        invs_per_rhs = 0.0
        times_per_rhs = 0.0

        if not args.metric.startswith("runtime"):
            runs = [
                os.path.join(log_dir, "run{:02d}".format(run))
                for run in range(args.repeat)
            ]
            dfs = {
                run: read_timings_from_logfile(args.nout, directory=run) for run in runs
            }

            invs_per_rhs = [
                average_per_rhs(df, "Inv (absolute)") for df in dfs.values()
            ]
            times_per_rhs = [time_per_rhs(df) for df in dfs.values()]

        metrics = {
            "runtime-low": {"metric": runtime["low"], "std": runtime["std"]},
            "runtime-mean": {"metric": runtime["mean"], "std": runtime["std"]},
            "inv_per_rhs": {
                "metric": np.min(invs_per_rhs),
                "std": np.std(invs_per_rhs),
            },
            "time_per_rhs": {
                "metric": np.min(times_per_rhs),
                "std": np.std(times_per_rhs),
            },
        }

        if metric_is_good(
            good=float(args.good),
            bad=float(args.bad),
            metric=metrics[args.metric]["metric"],
            metric_std=metrics[args.metric]["std"],
        ):
            exit(0)
        else:
            exit(1)
