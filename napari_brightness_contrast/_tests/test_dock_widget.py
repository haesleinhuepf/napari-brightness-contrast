from typing import Callable

import napari


def test_widget_added(make_napari_viewer: Callable[..., napari.Viewer]) -> None:
    viewer = make_napari_viewer()
    assert len(viewer.window._dock_widgets) == 0

    import numpy as np

    # Make a test image uint8, so we know the full range
    image = np.random.randint(256, size=(100, 100), dtype=np.uint8)

    viewer.add_image(image)

    num_dw = len(viewer.window._dock_widgets)

    from napari_brightness_contrast._dock_widget import BrightnessContrast

    bc = BrightnessContrast(viewer)
    viewer.window.add_dock_widget(bc)
    # Check widget was added
    assert len(viewer.window._dock_widgets) == num_dw + 1

    # Test the spinners: set values and then apply
    bc.spinner_lower_absolute.setValue(10)
    bc.spinner_upper_absolute.setValue(50)
    bc._set_absolutes()
    # Check that the contrast limits match the set values
    assert viewer.layers[-1].contrast_limits == [10, 50]

    #    bc._auto_percentiles()
    # Reset back to full range, which should be 0, 255 (image is uint8)
    bc._set_full_range()
    assert viewer.layers[-1].contrast_limits == [0, 255]
