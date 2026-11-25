"""Boundary/layout regressions; no SEACOFS files or external ESP required."""
import argparse
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd
from PIL import Image

MODULE = Path(__file__).resolve().parents[1] / "notebooks/daily_snapshots/render_frames.py"
spec = importlib.util.spec_from_file_location("render_frames", MODULE)
frames = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frames)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        x, y = np.linspace(0, 100, 21), np.linspace(0, 160, 33)
        xx, yy = np.meshgrid(x, y, indexing="ij")
        grid = SimpleNamespace(x_grid=x, y_grid=y, X_grid=xx, Y_grid=yy,
                               lon_rho=149 + xx / 8, lat_rho=-41 + yy / 10)
        args = argparse.Namespace(dpi=40, speed_vmax=1.377, no_quiver=False,
                                  quiver_step=4, quiver_scale=13.2, no_labels=False)
        self.renderer = frames.FrameRenderer(grid, args)
        self.u, self.v = np.full(xx.shape, .5), np.zeros(xx.shape)
        self.rows = pd.DataFrame([dict(Eddy=999999, Cyc="CE", xc=99., yc=80.,
                                       q11=1., q12=.3, q22=2., Rc=30.)])
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(self.renderer.close)

    def render(self, rows, number):
        path = Path(self.temporary.name) / f"{number}.png"
        self.renderer.render(self.u, self.v, rows, 2437, pd.Timestamp("1996-09-03"),
                             path, "regression-test")
        return path

    def test_boundary_and_empty_days_keep_layout_and_size(self):
        positions = [ax.get_position().bounds for ax in self.renderer.fig.axes]
        for number, rows in enumerate([self.rows, self.rows.iloc[:0], self.rows]):
            path = self.render(rows, number)
            np.testing.assert_allclose(
                [ax.get_position().bounds for ax in self.renderer.fig.axes],
                positions, rtol=0, atol=1e-14,
            )
            with Image.open(path) as image:
                self.assertEqual(image.size, (360, 400))
                self.assertEqual(image.info["render_signature"], "regression-test")

    def test_edge_label_and_ellipse_do_not_paint_outside_map(self):
        self.render(self.rows, 0)
        renderer = self.renderer
        renderer.fig.canvas.draw()
        visible = np.asarray(renderer.fig.canvas.buffer_rgba()).copy()
        renderer.labels[0].set_visible(False)
        renderer.ellipses.set_visible(False)
        renderer.fig.canvas.draw()
        hidden = np.asarray(renderer.fig.canvas.buffer_rgba()).copy()
        changed = np.any(visible != hidden, axis=2)
        ys, xs = np.where(changed)
        self.assertGreater(len(xs), 0)
        bounds = renderer.ax.get_window_extent()
        height = changed.shape[0]
        self.assertGreaterEqual(xs.min(), int(np.floor(bounds.xmin)))
        self.assertLessEqual(xs.max(), int(np.ceil(bounds.xmax)))
        self.assertGreaterEqual(ys.min(), int(np.floor(height - bounds.ymax)))
        self.assertLessEqual(ys.max(), int(np.ceil(height - bounds.ymin)))

    def test_ellipse_preserves_notebook_contour_definition(self):
        row = next(self.rows.itertuples(index=False))
        vertices = frames.ellipse_vertices(row, self.renderer.unit_circle)
        delta = vertices - [row.xc, row.yc]
        rho2 = np.einsum("ni,ij,nj->n", delta, [[1, .3], [.3, 2]], delta)
        np.testing.assert_allclose(rho2, row.Rc**2 / 2, rtol=1e-12)
        self.assertGreater(vertices[:, 0].max(), self.renderer.grid.x_grid.max())
        row = self.rows.assign(q22=-1).iloc[0]
        self.assertIsNone(frames.ellipse_vertices(row, self.renderer.unit_circle))


if __name__ == "__main__":
    unittest.main()
