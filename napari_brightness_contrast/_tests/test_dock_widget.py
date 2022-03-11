from napari_brightness_contrast._dock_widget import BrightnessContrast
from typing import Callable

import napari
import numpy as np


def test_widget_added(make_napari_viewer: Callable[..., napari.Viewer]) -> None:
    # Make a viewer
    viewer = make_napari_viewer()
    assert len(viewer.window._dock_widgets) == 0

    # Make a test image uint8, so we know the full range
    image = np.random.randint(256, size=(100, 100), dtype=np.uint8)

    viewer.add_image(image)

    num_dw = len(viewer.window._dock_widgets)

    bc = BrightnessContrast(viewer)
    viewer.window.add_dock_widget(bc)
    # Check widget was added
    assert len(viewer.window._dock_widgets) == num_dw + 1


def test_spinners(make_napari_viewer: Callable[..., napari.Viewer]) -> None:
    # Make a viewer, etc. as before
    viewer = make_napari_viewer()
    image = np.random.randint(256, size=(100, 100), dtype=np.uint8)
    viewer.add_image(image)
    bc = BrightnessContrast(viewer)
    viewer.window.add_dock_widget(bc)

    # Test the spinners: set values and then apply
    bc.spinner_lower_absolute.setValue(10)
    bc.spinner_upper_absolute.setValue(50)
    bc._set_absolutes()
    # Check that the contrast limits match the set values
    assert viewer.layers[-1].contrast_limits == [10, 50]

    # Reset back to full range, which should be 0, 255 (image is uint8)
    bc._set_full_range()
    assert viewer.layers[-1].contrast_limits == [0, 255]


def test_nonimage(make_napari_viewer: Callable[..., napari.Viewer]) -> None:
    # Make a viewer, etc. as before
    viewer = make_napari_viewer()
    image = np.random.randint(256, size=(100, 100), dtype=np.uint8)
    viewer.add_image(image, name="img")
    bc = BrightnessContrast(viewer)
    viewer.window.add_dock_widget(bc)

    # Set values and then apply
    bc.spinner_lower_absolute.setValue(10)
    bc.spinner_upper_absolute.setValue(50)
    bc._set_absolutes()
    # Check that the contrast limits match the set values
    assert viewer.layers["img"].contrast_limits == [10, 50]

    # add Shape layer
    viewer.add_shapes(None, name="shape")

    # Try to set contrasts
    bc._set_absolutes()
    # Check that they were not changed
    assert viewer.layers["img"].contrast_limits == [10, 50]

    # Select the image layer and change settings
    viewer.layers.selection.active = viewer.layers["img"]
    bc.spinner_lower_absolute.setValue(20)
    bc.spinner_upper_absolute.setValue(70)
    bc._set_absolutes()

    # Check that the contrast limits match the new set values
    assert viewer.layers["img"].contrast_limits == [20, 70]
