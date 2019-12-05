import pytest
import xarray as xr

from . import random_point_data, random_grid_data, make_linear_reg_pipeline

from xsd.pointwise_models import PointWiseDownscaler


@pytest.mark.parametrize(
    ("X", "y"),
    [
        # with numpy arrays
        (
            random_point_data(n_points=3, n_vars=3),
            random_point_data(n_points=3, n_vars=1)["a"],
        ),
        (
            random_grid_data(grid_shape=(2, 3), n_vars=3),
            random_grid_data(grid_shape=(2, 3), n_vars=1)["a"],
        ),
        (
            random_grid_data(grid_shape=(2, 3), n_vars=3),
            random_grid_data(grid_shape=(2, 3), n_vars=1)["a"],
        ),
        # with dask arrays
        (
            random_point_data(n_points=3, n_vars=3).chunk({"point": 1}),
            random_point_data(n_points=3, n_vars=1)["a"].chunk({"point": 1}),
        ),
        (
            random_grid_data(grid_shape=(2, 3), n_vars=3).chunk({"y": 1, "x": 1}),
            random_grid_data(grid_shape=(2, 3), n_vars=1)["a"].chunk({"y": 1, "x": 1}),
        ),
        (
            random_grid_data(grid_shape=(2, 3), n_vars=3).chunk({"y": 1, "x": 1}),
            random_grid_data(grid_shape=(2, 3), n_vars=1)["a"].chunk({"y": 1, "x": 1}),
        ),
    ],
)
def test_pointwise_model(X, y):
    pipeline = make_linear_reg_pipeline()
    model = PointWiseDownscaler(model=pipeline)
    model.fit(X, y)
    y_pred = model.predict(X)
    assert isinstance(y_pred, type(y))
    assert y_pred.sizes == y.sizes
    assert y.chunks == y_pred.chunks
