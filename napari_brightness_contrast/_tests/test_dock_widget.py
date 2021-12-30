import napari_brightness_contrast
import pytest


def test_something_with_viewer(make_napari_viewer):
    viewer = make_napari_viewer()

    import numpy as np
    image = np.random.random((100, 100))

    viewer.add_image(image)

    num_dw = len(viewer.window._dock_widgets)

    from napari_brightness_contrast._dock_widget import BrightnessContrast
    bc = BrightnessContrast(viewer)
    viewer.window.add_dock_widget(bc)
    assert len(viewer.window._dock_widgets) == num_dw + 1

    bc._set_absolutes()
    bc._auto_percentiles()
    bc._set_full_range()
