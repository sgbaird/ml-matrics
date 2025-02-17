from __future__ import annotations

from os.path import abspath, dirname
from typing import Any, Sequence, Union

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.gridspec import GridSpec
from matplotlib.offsetbox import AnchoredText
from numpy.typing import NDArray
from sklearn.metrics import r2_score


ROOT = dirname(dirname(abspath(__file__)))

NumArray = NDArray[Union[np.float64, np.int_]]


def with_hist(
    xs: NDArray[np.float64],
    ys: NDArray[np.float64],
    cell: GridSpec = None,
    bins: int = 100,
) -> Axes:
    """Call before creating a plot and use the returned `ax_main` for all
    subsequent plotting ops to create a grid of plots with the main plot in
    the lower left and narrow histograms along its x- and/or y-axes displayed
    above and near the right edge.

    Args:
        xs (array): x values.
        ys (array): y values.
        cell (GridSpec, optional): Cell of a plt GridSpec at which to add the
            grid of plots. Defaults to None.
        bins (int, optional): Resolution/bin count of the histograms. Defaults to 100.

    Returns:
        ax: The matplotlib Axes to be used for the main plot.
    """
    fig = plt.gcf()

    gs = (cell.subgridspec if cell else fig.add_gridspec)(
        2, 2, width_ratios=(6, 1), height_ratios=(1, 5), wspace=0, hspace=0
    )

    ax_main = fig.add_subplot(gs[1, 0])
    ax_histx = fig.add_subplot(gs[0, 0], sharex=ax_main)
    ax_histy = fig.add_subplot(gs[1, 1], sharey=ax_main)

    # x_hist
    ax_histx.hist(xs, bins=bins, rwidth=0.8)
    ax_histx.axis("off")

    # y_hist
    ax_histy.hist(ys, bins=bins, rwidth=0.8, orientation="horizontal")
    ax_histy.axis("off")

    return ax_main


def annotate_bar_heights(
    ax: Axes = None,
    voffset: int = 10,
    hoffset: int = 0,
    labels: Sequence[str | int | float] = None,
    fontsize: int = 14,
) -> None:
    """Annotate histograms with a label indicating the height/count of each bar.

    Args:
        ax (matplotlib.axes.Axes): The axes to annotate.
        voffset (int): Vertical offset between the labels and the bars.
        hoffset (int): Horizontal offset between the labels and the bars.
        labels (list[str]): Labels used for annotating bars. Falls back to the
            y-value of each bar if None.
        fontsize (int): Annotated text size in pts. Defaults to 14.
    """
    if ax is None:
        ax = plt.gca()

    if labels is None:
        labels = [int(patch.get_height()) for patch in ax.patches]

    for rect, label in zip(ax.patches, labels):

        y_pos = rect.get_height()
        x_pos = rect.get_x() + rect.get_width() / 2 + hoffset

        if ax.get_yscale() == "log":
            y_pos = y_pos + np.log(voffset)
        else:
            y_pos = y_pos + voffset

        # place label at end of the bar and center horizontally
        ax.annotate(label, (x_pos, y_pos), ha="center", fontsize=fontsize)
        # ensure enough vertical space to display label above highest bar
        ax.margins(y=0.1)


def add_mae_r2_box(
    xs: NDArray[np.float64],
    ys: NDArray[np.float64],
    ax: Axes = None,
    loc: str = "lower right",
    prefix: str = "",
    suffix: str = "",
    prec: int = 3,
    **kwargs: Any,
) -> AnchoredText:
    """Provide a set of x and y values of equal length and an optional Axes object
    on which to print the values' mean absolute error and R^2 coefficient of
    determination.

    Args:
        xs (array, optional): x values.
        ys (array, optional): y values.
        ax (Axes, optional): matplotlib Axes on which to add the box. Defaults to None.
        loc (str, optional): Where on the plot to place the AnchoredText object.
            Defaults to "lower right".
        prec (int, optional): # of decimal places in printed metrics. Defaults to 3.
        prefix (str, optional): Title or other string to prepend to metrics.
            Defaults to "".
        suffix (str, optional): Text to append after metrics. Defaults to "".

    Returns:
        AnchoredText: Instance containing the metrics.
    """
    if ax is None:
        ax = plt.gca()

    mask = ~np.isnan(xs) & ~np.isnan(ys)
    xs, ys = xs[mask], ys[mask]

    text = f"{prefix}$\\mathrm{{MAE}} = {np.abs(xs - ys).mean():.{prec}f}$"
    text += f"\n$R^2 = {r2_score(xs, ys):.{prec}f}${suffix}"

    frameon: bool = kwargs.pop("frameon", False)
    text_box = AnchoredText(text, loc=loc, frameon=frameon, **kwargs)
    ax.add_artist(text_box)

    return text_box


def get_crystal_sys(spg: int) -> str:
    """Get the crystal system for an international space group number."""
    # not using isinstance(n, int) to allow 0-decimal floats
    if not (spg == int(spg) and 0 < spg < 231):
        raise ValueError(f"Received invalid space group {spg}")

    if 0 < spg < 3:
        return "triclinic"
    if spg < 16:
        return "monoclinic"
    if spg < 75:
        return "orthorhombic"
    if spg < 143:
        return "tetragonal"
    if spg < 168:
        return "trigonal"
    if spg < 195:
        return "hexagonal"
    return "cubic"
