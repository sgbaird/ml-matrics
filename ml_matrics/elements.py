from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.figure_factory as ff
from matplotlib.axes import Axes
from matplotlib.cm import get_cmap
from matplotlib.colors import LogNorm, Normalize
from matplotlib.patches import Rectangle
from pandas.api.types import is_numeric_dtype, is_string_dtype
from plotly.graph_objects import Figure
from pymatgen.core import Composition

from ml_matrics.utils import ROOT, annotate_bar_heights


if TYPE_CHECKING:
    from typing import TypeAlias

    ElemValues: TypeAlias = dict[str, int | float] | pd.Series | Sequence[str]

df_ptable = pd.read_csv(f"{ROOT}/ml_matrics/elements.csv").set_index("symbol")


def count_elements(elem_values: ElemValues) -> pd.Series:
    """Processes elemental heatmap data. If passed a list of strings, assume they are
    compositions and count the occurrences of each chemical element. Else ensure the
    data is a pd.Series filled with zero values for missing element symbols.

    Args:
        elem_values (dict[str, int | float] | pd.Series | list[str]): Map from element
            symbols to heatmap values or iterable of composition strings/objects.

    Returns:
        pd.Series: Map element symbols to heatmap values.
    """
    # ensure elem_values is Series if we got dict/list/tuple
    srs = pd.Series(elem_values)

    if is_numeric_dtype(srs):
        pass
    elif is_string_dtype(srs):
        # assume all items in elem_values are composition strings
        formula2dict = lambda str: pd.Series(
            Composition(str).fractional_composition.as_dict()
        )
        # sum up element occurrences
        srs = srs.apply(formula2dict).sum()
    else:
        raise ValueError(
            "Expected elem_values to be map from element symbols to heatmap values or "
            f"list of compositions (strings or Pymatgen objects), got {elem_values}"
        )

    if srs.index.dtype == int or srs.index.str.isdigit().all():
        # if index is all integers or digit strings, assume they represent atomic
        # numbers and map them to element symbols (H: 1, He: 2, ...)
        srs.index = srs.index.astype(int).map(
            df_ptable.reset_index().set_index("atomic_number").symbol
        )

    # ensure all elements are present in returned Series (with value zero if they
    # weren't in elem_values before)
    srs = srs.reindex(df_ptable.index, fill_value=0).rename("count")
    return srs


def ptable_heatmap(
    elem_values: ElemValues,
    log: bool = False,
    ax: Axes = None,
    cbar_title: str = "Element Count",
    cbar_max: float | int | None = None,
    cmap: str = "summer_r",
    zero_color: str = "#DDD",  # light gray
    infty_color: str = "lightskyblue",
    na_color: str = "white",
    heat_labels: Literal["value", "fraction", "percent", None] = "value",
    precision: str = None,
    text_color: str | tuple[str, str] = "auto",
) -> Axes:
    """Plot a heatmap across the periodic table of elements.

    Args:
        elem_values (dict[str, int | float] | pd.Series | list[str]): Map from element
            symbols to heatmap values or iterable of composition strings/objects.
        log (bool, optional): Whether color map scale is log or linear.
        ax (Axes, optional): matplotlib Axes on which to plot. Defaults to None.
        cbar_title (str, optional): Title for colorbar. Defaults to "Element Count".
        cbar_max (float, optional): Maximum value of the colorbar range. Will be ignored
            if smaller than the largest plotted value. For creating multiple plots with
            identical color bars for visual comparison. Defaults to 0.
        cmap (str, optional): Matplotlib colormap name to use. Defaults to "YlGn".
        zero_color (str): Color to use for elements with value zero. Defaults to "#DDD"
            (light gray).
        infty_color: Color to use for elements with value infinity. Defaults to
            "lightskyblue".
        na_color: Color to use for elements with value infinity. Defaults to "white".
        heat_labels ("value" | "fraction" | "percent" | None): Whether to display heat
            values as is, normalized as a fraction of the total, as percentages
            or not at all (None). Defaults to "value".
            "fraction" and "percent" can be used to make the colors in different heatmap
            (and ratio) plots comparable.
        precision (str): f-string format option for heat labels. Defaults to None in
            which case we fall back on ".1%" (1 decimal place) if heat_labels="percent"
            else ".3g".
        text_color (str | tuple[str, str]): What color to use for element symbols and
            heat labels. Must be a valid color name, or a 2-tuple of names, one to use
            for the upper half of the color scale, one for the lower half. The special
            value 'auto' applies 'black' on the lower and 'white' on the upper half of
            the color scale. Defaults to "auto".

    Returns:
        ax: matplotlib Axes with the heatmap.
    """
    if log and heat_labels in ("fraction", "percent"):
        raise ValueError(
            "Combining log color scale and heat_labels='fraction'/'percent' unsupported"
        )

    elem_values = count_elements(elem_values)

    # replace positive and negative infinities with NaN values, then drop all NaNs
    clean_vals = elem_values.replace([np.inf, -np.inf], np.nan).dropna()

    if heat_labels in ("fraction", "percent"):
        # ignore inf values in sum() else all would be set to 0 by normalizing
        elem_values /= clean_vals.sum()
        clean_vals /= clean_vals.sum()  # normalize as well for norm.autoscale() below

    color_map = get_cmap(cmap)

    n_rows = df_ptable.row.max()
    n_columns = df_ptable.column.max()

    # TODO can we pass as a kwarg and still ensure aspect ratio respected?
    fig = plt.figure(figsize=(0.75 * n_columns, 0.7 * n_rows))

    if ax is None:
        ax = plt.gca()

    rw = rh = 0.9  # rectangle width/height

    norm = LogNorm() if log else Normalize()

    norm.autoscale(clean_vals.to_numpy())
    if cbar_max is not None:
        norm.vmax = cbar_max

    text_style = dict(horizontalalignment="center", fontsize=16, fontweight="semibold")

    for symbol, row, column, *_ in df_ptable.itertuples():

        row = n_rows - row  # makes periodic table right side up
        heat_val = elem_values[symbol]

        # inf (float/0) or NaN (0/0) are expected when passing in elem_values from
        # ptable_heatmap_ratio
        if heat_val == np.inf:
            color = infty_color  # not in denominator
            label = r"$\infty$"
        elif pd.isna(heat_val):
            color = na_color  # neither numerator nor denominator
            label = r"$0\,/\,0$"
        else:
            color = color_map(norm(heat_val)) if heat_val > 0 else zero_color

            if heat_labels == "percent":
                label = f"{heat_val:{precision or '.1%'}}"
            else:
                label = f"{heat_val:{precision or '.3g'}}"
            # replace shortens scientific notation 1e+01 to 1e1 so it fits inside cells
            label = label.replace("e+0", "e")
        if row < 3:  # vertical offset for lanthanide + actinide series
            row += 0.5
        rect = Rectangle((column, row), rw, rh, edgecolor="gray", facecolor=color)

        if heat_labels is None:
            # no value to display below in colored rectangle so center element symbol
            text_style["verticalalignment"] = "center"

        if text_color == "auto":
            text_clr = "white" if norm(heat_val) > 0.5 else "black"
        elif isinstance(text_color, (tuple, list)):
            text_clr = text_color[0] if norm(heat_val) > 0.5 else text_color[1]
        else:
            text_clr = text_color

        plt.text(
            column + 0.5 * rw, row + 0.5 * rh, symbol, color=text_clr, **text_style
        )

        if heat_labels is not None:
            plt.text(
                column + 0.5 * rw,
                row + 0.1 * rh,
                label,
                fontsize=12,
                horizontalalignment="center",
                color=text_clr,
            )

        ax.add_patch(rect)

    if heat_labels is not None:

        # colorbar position and size: [bar_xpos, bar_ypos, bar_width, bar_height]
        # anchored at lower left corner
        cb_ax = ax.inset_axes([0.18, 0.8, 0.42, 0.05], transform=ax.transAxes)
        # format major and minor ticks
        cb_ax.tick_params(which="both", labelsize=14, width=1)

        mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)

        def tick_fmt(val: float, pos: int) -> str:
            # val: value at color axis tick (e.g. 10.0, 20.0, ...)
            # pos: zero-based tick counter (e.g. 0, 1, 2, ...)
            if heat_labels == "percent":
                # display color bar values as percentages
                return f"{val:.0%}"
            if val < 1e4:
                return f"{val:.0f}"
            return f"{val:.2g}"

        cbar = fig.colorbar(
            mappable, cax=cb_ax, orientation="horizontal", format=tick_fmt
        )

        cbar.outline.set_linewidth(1)
        cb_ax.set_title(cbar_title, pad=10, **text_style)

    plt.ylim(0.3, n_rows + 0.1)
    plt.xlim(0.9, n_columns + 1)

    plt.axis("off")
    return ax


def ptable_heatmap_ratio(
    elem_values_num: ElemValues,
    elem_values_denom: ElemValues,
    normalize: bool = False,
    cbar_title: str = "Element Ratio",
    not_in_numerator: tuple[str, str] = ("#DDD", "gray: not in 1st list"),
    not_in_denominator: tuple[str, str] = ("lightskyblue", "blue: not in 2nd list"),
    not_in_either: tuple[str, str] = ("white", "white: not in either"),
    **kwargs: Any,
) -> Axes:
    """Display the ratio of two maps from element symbols to heat values or of two sets
    of compositions.

    Args:
        elem_values_num (dict[str, int | float] | pd.Series | list[str]): Map from
            element symbols to heatmap values or iterable of composition strings/objects
            in the numerator.
        elem_values_denom (dict[str, int | float] | pd.Series | list[str]): Map from
            element symbols to heatmap values or iterable of composition strings/objects
            in the denominator.
        normalize (bool): Whether to normalize heatmap values so they sum to 1. Makes
            different ptable_heatmap_ratio plots comparable. Defaults to False.
        cbar_title (str): Title for the color bar. Defaults to "Element Ratio".
        not_in_numerator (tuple[str, str]): Color and legend description used for
            elements missing from numerator.
        not_in_denominator (tuple[str, str]): See not_in_numerator.
        not_in_either (tuple[str, str]): See not_in_numerator.
        kwargs (Any, optional): kwargs passed to ptable_heatmap.

    Returns:
        ax: The plot's matplotlib Axes.
    """
    elem_values_num = count_elements(elem_values_num)

    elem_values_denom = count_elements(elem_values_denom)

    elem_values = elem_values_num / elem_values_denom

    if normalize:
        elem_values /= elem_values.sum()

    kwargs["zero_color"] = not_in_numerator[0]
    kwargs["infty_color"] = not_in_denominator[0]
    kwargs["na_color"] = not_in_either[0]

    ax = ptable_heatmap(elem_values, cbar_title=cbar_title, precision=".1f", **kwargs)

    # add legend handles
    for y_pos, color, txt in (
        (1.8, *not_in_numerator),
        (1.1, *not_in_denominator),
        (0.4, *not_in_either),
    ):
        bbox = dict(facecolor=color, edgecolor="gray")
        plt.text(0.8, y_pos, txt, fontsize=12, bbox=bbox)

    return ax


def hist_elemental_prevalence(
    formulas: ElemValues,
    log: bool = False,
    keep_top: int = None,
    ax: Axes = None,
    bar_values: Literal["percent", "count", None] = "percent",
    **kwargs: Any,
) -> Axes:
    """Plots a histogram of the prevalence of each element in a materials dataset.

    Adapted from https://github.com/kaaiian/ML_figures (https://git.io/JmbaI).

    Args:
        formulas (list[str]): compositional strings, e.g. ["Fe2O3", "Bi2Te3"].
        log (bool, optional): Whether y-axis is log or linear. Defaults to False.
        keep_top (int | None): Display only the top n elements by prevalence.
        ax (Axes): matplotlib Axes on which to plot. Defaults to None.
        bar_values ('percent'|'count'|None): 'percent' (default) annotates bars with the
            percentage each element makes up in the total element count. 'count'
            displays count itself. None removes bar labels.
        **kwargs (int): Keyword arguments passed to annotate_bar_heights.
    """
    if ax is None:
        ax = plt.gca()

    elem_counts = count_elements(formulas)
    non_zero = elem_counts[elem_counts > 0].sort_values(ascending=False)
    if keep_top is not None:
        non_zero = non_zero.head(keep_top)
        plt.title(f"Top {keep_top} Elements")

    non_zero.plot.bar(width=0.7, edgecolor="black")

    plt.ylabel("log(Element Count)" if log else "Element Count")

    if log:
        plt.yscale("log")

    if bar_values is not None:
        if bar_values == "percent":
            sum_elements = non_zero.sum()
            labels = [f"{el / sum_elements:.1%}" for el in non_zero.values]
        else:
            labels = non_zero.astype(int).to_list()
        annotate_bar_heights(ax, labels=labels, **kwargs)

    return ax


def ptable_heatmap_plotly(
    elem_values: ElemValues,
    colorscale: Sequence[tuple[float, str]] = None,
    showscale: bool = True,
    heat_labels: Literal["value", "fraction", "percent", None] = "value",
    precision: str = None,
    hover_cols: Sequence[str] | dict[str, str] | None = None,
    hover_data: dict[str, str | int | float] | pd.Series | None = None,
    font_colors: Sequence[str] = ["black"],
    gap: float = 5,
    font_size: int = None,
    bg_color: str = "rgba(0, 0, 0, 0)",
    color_bar: dict[str, Any] = {},
) -> Figure:
    """Plot the periodic table as an interactive heatmap.

    Args:
        elem_values (dict[str, int | float] | pd.Series | list[str]): Map from element
            symbols to heatmap values or iterable of composition strings/objects.
        colorscale (list[tuple[float, str]]): Color scale for heatmap. Defaults to
            [(0.0, "teal"), (1.0, "darkgreen")].
        showscale (bool): Whether to show a bar for the color scale. Defaults to True.
        heat_labels ("value" | "fraction" | "percent" | None): Whether to display heat
            values as is (value), normalized as a fraction of the total, as percentages
            or not at all (None). Defaults to "value".
            "fraction" and "percent" can be used to make the colors in different heatmap
            (and ratio) plots comparable.
        precision (str): f-string format option for heat labels. Defaults to None in
            which case we fall back on ".1%" (1 decimal place) if heat_labels="percent"
            else ".3g".
        hover_cols (list[str] | dict[str, str]): Elemental properties to display in the
            hover tooltip. Can be a list of names or a dict mapping names to what they
            should display as. E.g. {"n_valence": "# of valence electrons"} will
            display as "# of valence electrons = {x}". Defaults to None. Available
            properties are: symbol, row, column, name, atomic_number, atomic_mass,
            n_neutrons, n_protons, n_electrons, period, group, phase, radioactive,
            natural, metal, nonmetal, metalloid, type, atomic_radius, electronegativity,
            first_ionization, density, melting_point, boiling_point, number_of_isotopes,
            discoverer, year, specific_heat, n_shells, n_valence.
        hover_data (dict[str, str | int | float] | pd.Series): Map from element symbols
            to additional data to display in the hover tooltip. Defaults to None.
        font_colors (list[str]): One or two color strings [min_color, max_color].
            min_color is applied to annotations for heatmap values
            < (max_val - min_val) / 2. Defaults to ["white"].
        gap (float): Gap between tiles of the periodic table. Defaults to 5.
        font_size (int): Element symbol and heat label text size. Defaults to None
            meaning automatic font size based on plot size.
        bg_color (str): Plot background color. Defaults to "rgba(0, 0, 0, 0)".
        color_bar (dict[str, Any]): Plotly color bar properties documented at
            https://plotly.com/python/reference#heatmap-colorbar. Defaults to None.

    Returns:
        Figure: Plotly Figure object.
    """
    elem_values = count_elements(elem_values)

    if heat_labels in ("fraction", "percent"):
        # normalize heat values
        clean_vals = elem_values.replace([np.inf, -np.inf], np.nan).dropna()
        # ignore inf values in sum() else all would be set to 0 by normalizing
        label_vals = elem_values / clean_vals.sum()
    else:
        label_vals = elem_values

    n_rows, n_columns = 10, 18
    tile_texts, hover_texts = np.full([2, n_rows, n_columns], "", dtype=object)
    heat_vals = -np.ones([n_rows, n_columns])

    for (symbol, period, group, name, *_) in df_ptable.itertuples():
        # build table from bottom up so that period 1 becomes top row
        row = n_rows - period
        col = group - 1

        heat_label = label_vals[symbol]
        if heat_labels == "percent":
            label = f"{heat_label:{precision or '.1%'}}"
        else:
            label = f"{heat_label:{precision or '.3g'}}"

        tile_text = f"<b>{symbol}</b>"
        if heat_labels is not None:
            tile_text += f"<br>{label}"
        tile_texts[row][col] = tile_text

        hover_text = name

        if hover_data is not None:
            hover_text += f"<br>{hover_data[symbol]}"

        if hover_cols is not None:
            df_row = df_ptable.loc[symbol]
            if isinstance(hover_cols, dict):
                for col_name, col_label in hover_cols.items():
                    hover_text += f"<br>{col_label} = {df_row[col_name]}"
            else:
                col_data_str = "<br>".join(f"{x} = {df_row[x]}" for x in hover_cols)
            hover_text += f"<br>{col_data_str}"

        hover_texts[row][col] = hover_text

        color_val = elem_values[symbol]
        heat_vals[row][col] = color_val + 1e-6

    if isinstance(colorscale, (list, tuple)) and isinstance(
        colorscale[0], (list, tuple)
    ):
        colorscale = [(0, "rgba(0, 0, 0, 0)"), *map(list, colorscale)]  # type: ignore
        colorscale[1][0] = 1e-6  # type: ignore
    elif colorscale is None:
        colorscale = [(0, "rgba(0, 0, 0, 0)"), (1e-6, "teal"), (1, "darkgreen")]
    else:
        raise NotImplementedError(
            "passing in string names as colorscale not currently supported"
        )
    # requires https://github.com/plotly/plotly.js/issues/975 so we no longer need
    # to modify colorscale as above to handle empty tiles

    fig = ff.create_annotated_heatmap(
        heat_vals,
        annotation_text=tile_texts,
        text=hover_texts,
        showscale=showscale,
        colorscale=colorscale or None,
        font_colors=font_colors,
        hoverinfo="text",
        xgap=gap,
        ygap=gap,
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10, pad=10),
        paper_bgcolor=bg_color,
        plot_bgcolor="rgba(0, 0, 0, 0)",
        xaxis=dict(zeroline=False, showgrid=False),
        yaxis=dict(zeroline=False, showgrid=False, scaleanchor="x"),
        font=dict(size=font_size),
    )
    fig.update_traces(
        colorbar=dict(lenmode="fraction", len=0.87, thickness=15, **color_bar)
    )
    return fig
