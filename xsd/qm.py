import numpy as np
import xarray as xr


"""
Basic univariate quantile mapping post-processing algorithms.

"""


def train(x, y, nq, group, kind="+"):
    """Compute quantile bias-adjustment factors.

    Parameters
    ----------
    x : xr.DataArray
      Training data, usually a model output whose biases are to be corrected.
    y : xr.DataArray
      Training target, usually an observed at-site time-series.
    nq : int
      Number of quantiles.
    group : {'time.season', 'time.month', 'time.dayofyear'}
      Grouping criterion.
    kind : {'+', '*'}
      The transfer operation, + for additive and * for multiplicative.

    Returns
    -------
    xr.DataArray
      Delta factor computed over time grouping and quantile bins.
    """
    # Define nodes. Here n equally spaced points within [0, 1]
    # E.g. for nq=4 :  0---x------x------x------x---1
    dq = 1 / nq / 2
    q = np.linspace(dq, 1 - dq, nq)

    # Group values by time, then compute quantiles. The resulting array will have new time and quantile dimensions.
    xg = x.groupby(group).quantile(q)
    yg = y.groupby(group).quantile(q)

    # Compute the correction factor
    if kind == "+":
        out = yg - xg
    elif kind == "*":
        out = yg / xg
    else:
        raise ValueError("kind must be + or *.")

    # Save input parameters as attributes of output DataArray.
    out.attrs["kind"] = kind
    out.attrs["group"] = group

    return out


def predict(x, qmf, interp=False):
    """Apply quantile mapping delta to an array.

    Parameters
    ----------
    x : xr.DataArray
      Data to predict on.
    qmf : xr.DataArray
      Quantile mapping factors computed by the `train` function.
    interp : bool
      Whether to interpolate between the groupings.

    Returns
    -------
    xr.DataArray
      Input array with delta applied.
    """

    if "time" not in qmf.group:
        raise NotImplementedError

    if "season" in qmf.group and interp:
        raise NotImplementedError

    # Find the group indexes
    ind, att = qmf.group.split(".")

    time = x.coords["time"]
    gc = qmf.coords[att]

    # Add cyclical values to the scaling factors for interpolation
    if interp:
        qmf = add_cyclic(qmf, att)
        qmf = add_q_bounds(qmf)

    # Compute the percentile time series of the input array
    q = x.groupby(qmf.group).apply(xr.DataArray.rank, pct=True, dim=ind)
    iq = xr.DataArray(q, dims="time", coords={"time": time}, name="quantile index")

    # Create DataArrays for indexing
    # TODO: Adjust for different calendars if necessary.

    if interp:
        time = q.indexes["time"]
        if att == "month":
            x = time.month - 0.5 + time.day / time.daysinmonth
        elif att == "dayofyear":
            x = time.dayofyear
        else:
            raise NotImplementedError

    else:
        x = getattr(q.indexes[ind], att)

    it = xr.DataArray(x, dims="time", coords={"time": time}, name="time group index")

    # Extract the correct quantile for each time step.

    if interp:  # Interpolate both the time group and the quantile.
        factor = qmf.interp({att: it, "quantile": iq})
    else:  # Find quantile for nearest time group and quantile.
        factor = qmf.sel({att: it, "quantile": iq}, method="nearest")

    # Apply the correction factors
    out = x.copy()
    if qmf.kind == "+":
        out += factor
    elif qmf.kind == "*":
        out *= factor

    out.attrs["bias_corrected"] = True

    # Remove time grouping and quantile coordinates
    return out.drop(["quantile", att])


def add_cyclic(qmf, att):
    """Reindex the scaling factors to include the last time grouping
    at the beginning and the first at the end.

    This is done to allow interpolation near the end-points.
    """
    gc = qmf.coords[att]
    i = np.concatenate(([-1], range(len(gc)), [0]))
    qmf = qmf.reindex({att: gc[i]})
    qmf.coords[att] = range(len(qmf))
    return qmf


def add_q_bounds(qmf):
    """Reindex the scaling factors to set the quantile at 0 and 1 to the first and last quantile respectively.

    This is a naive approach that won't work well for extremes.
    """
    att = "quantile"
    q = qmf.coords[att]
    i = np.concatenate(([0], range(len(q)), [-1]))
    qmf = qmf.reindex({att: q[i]})
    qmf.coords[att] = np.concatenate(([0], q, [1]))
    return qmf
