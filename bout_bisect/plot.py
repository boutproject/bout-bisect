from . import bout_bisect

import matplotlib.pyplot as plt
import numpy as np


def make_bar_plot(tables, legend=None, columns=None):
    """Make a bar plot, including error bars, for the given timing tables

    Parameters
    ----------
    tables
        List of timing tables from bout_bisect.read_timings_from_logfile
    legend : List[str], optional
        List of alternative labels for legend
    columns : List[str], optional
        List of column names to plot. By default, plots the usual
        BOUT++ timing columns

    Returns
    -------
    fig
        The matplotlib figure handle
    ax
        The axis handle
    timings
        The computed means and standard deviations for each column for
        each table

    """

    if columns is None:
        columns = [
            "Inv (absolute)",
            "Comm (absolute)",
            "SOLVER (absolute)",
            "Calc (absolute)",
            "Wall Time",
        ]
    column_position = np.arange(len(columns))

    def get_all_timings(table, columns):
        return {
            column: bout_bisect.average_and_std_per_rhs(table, column)
            for column in columns
        }

    all_timings = {table.name: get_all_timings(table, columns) for table in tables}
    items = len(tables)
    width = (1.0 - 1.0 / (items + 1)) / items
    offsets = width * (np.arange(items) - (items - 1) / 2)

    fig, ax = plt.subplots()

    def get_item(table, item, columns):
        return [all_timings[table.name][column][item] for column in columns]

    for table, offset in zip(tables, offsets):
        # Plot all the columns for one table at a time
        bars = ax.bar(
            column_position + offset,
            get_item(table, "mean", columns),
            width,
            yerr=get_item(table, "std", columns),
            label=table.name,
            error_kw=dict(capsize=3),
        )
        # Attach a text label above each bar, displaying its height
        _, _, barlinecols = bars.errorbar
        for err_segment, bar in zip(barlinecols[0].get_segments(), bars):
            position = err_segment[1][1]
            height = bar.get_height()
            ax.annotate(
                "{:05.3f}".format(height),
                xy=(bar.get_x() + bar.get_width() / 2, position),
                xytext=(0, 3),  # 3 points vertical offset
                textcoords="offset points",
                ha="center",
                va="bottom",
            )

    # The "(absolute)" in the column names makes for too long a label
    columns_renamed = [key.replace(" (absolute)", "") for key in columns]

    ax.set_ylabel("Time (seconds)")
    ax.set_xticks(column_position)
    ax.set_xticklabels(columns_renamed)
    ax.set_title("Average time per rhs")

    # If no legend passed, we can just use the labels
    if legend is None:
        ax.legend()
    else:
        ax.legend(legend)

    # Make sure we start at 0.0 in y
    fig.tight_layout()
    axis = list(ax.axis())
    axis[2] = 0.0
    ax.axis(axis)

    return fig, ax, all_timings
