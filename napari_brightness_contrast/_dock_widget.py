from qtpy.QtWidgets import QSpacerItem, QSizePolicy
from napari_plugin_engine import napari_hook_implementation
from qtpy.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QSpinBox,
)
from qtpy.QtCore import Qt
from superqt import QRangeSlider

import pyqtgraph as pg
import numpy as np
import napari
from napari_tools_menu import register_dock_widget


@register_dock_widget(menu="Visualization > Brightness / Contrast")
class BrightnessContrast(QWidget):
    """
    A user interface for showing a histogram of currently selected image layers in napari and min/max contrast limits
    sliders.
    """

    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer
        napari_viewer.layers.selection.events.changed.connect(self._on_selection)

        # This container will contain the histogram plot
        graph_container = QWidget()

        # histogram view
        self.graphics_widget = pg.GraphicsLayoutWidget()
        self.graphics_widget.setBackground(None)
        graph_container.setMaximumHeight(100)
        graph_container.setLayout(QHBoxLayout())
        graph_container.layout().addWidget(self.graphics_widget)

        # min / max of all
        self.label_minimum = QLabel()
        self.label_maximum = QLabel()
        self.label_maximum.setAlignment(Qt.AlignRight)
        min_max_widget = QWidget()
        min_max_widget.setLayout(QHBoxLayout())
        min_max_widget.layout().addWidget(self.label_minimum)
        min_max_widget.layout().addWidget(self.label_maximum)

        # individual layers: min/max sliders
        self.sliders = QWidget()
        self.sliders.setLayout(QVBoxLayout())
        self.sliders.layout().setSpacing(0)

        # set contrast limits to absolute values
        absoluter = QWidget()
        absoluter.setLayout(QHBoxLayout())

        # very small and very large numbers used as min/max for the spinners
        min_float = -2147483648
        max_float = 2147483647

        # Allow user to set min/max of all layers to absolute values
        lbl = QLabel("Absolute")
        lower = QSpinBox()
        lower.setMinimum(min_float)
        lower.setMaximum(max_float)
        lower.setValue(0)
        upper = QSpinBox()
        upper.setMinimum(min_float)
        upper.setMaximum(max_float)
        upper.setValue(255)
        btn = QPushButton("Set")
        btn.clicked.connect(self._set_absolutes)
        absoluter.layout().addWidget(lbl)
        absoluter.layout().addWidget(lower)
        absoluter.layout().addWidget(upper)
        absoluter.layout().addWidget(btn)
        self.spinner_lower_absolute = lower
        self.spinner_upper_absolute = upper

        # allow user to use auto-contrast using percentiles
        percentiler = QWidget()
        percentiler.setLayout(QHBoxLayout())
        lbl = QLabel("Percentiles")
        lower = QSpinBox()
        lower.setMinimum(0)
        lower.setMaximum(100)
        lower.setValue(10)
        upper = QSpinBox()
        upper.setMinimum(0)
        upper.setMaximum(100)
        upper.setValue(90)
        btn = QPushButton("Set")
        btn.clicked.connect(self._auto_percentiles)
        percentiler.layout().addWidget(lbl)
        percentiler.layout().addWidget(lower)
        percentiler.layout().addWidget(upper)
        percentiler.layout().addWidget(btn)
        self.spinner_lower_percentile = lower
        self.spinner_upper_percentile = upper

        # allow user to reset all to full range
        btn_full_range = QPushButton("Set full range")
        btn_full_range.clicked.connect(self._set_full_range)

        # setup layout of the whole dialog
        self.setLayout(QVBoxLayout())

        self.layout().addWidget(graph_container)
        self.layout().addWidget(min_max_widget)
        self.layout().addWidget(self.sliders)
        self.layout().addWidget(absoluter)
        self.layout().addWidget(percentiler)
        self.layout().addWidget(btn_full_range)

        verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.layout().addItem(verticalSpacer)
        self.layout().setSpacing(0)

        self.redraw()

    def _on_selection(self, event):
        # redraw when layer selection has changed
        self.redraw()

    def redraw(self, rebuild_gui=True):
        # add a new plot to the graphics_widget or empty the old plot
        if not hasattr(self, "plot"):
            self.plot = self.graphics_widget.addPlot()
        else:
            self.plot.clear()

        # determine min/max intensity of all shown layers
        all_minimum = None
        all_maximum = None
        for layer in self.selected_image_layers():
            minimum, maximum = min_max(layer.data)
            if all_minimum is None or all_minimum > minimum:
                all_minimum = minimum
            if all_maximum is None or all_maximum < maximum:
                all_maximum = maximum
        all_minimum = np.floor(all_minimum) if all_minimum is not None else 0
        all_maximum = (
            np.ceil(all_maximum) if all_maximum is not None else all_minimum + 1
        )

        self.label_minimum.setText(str(all_minimum))
        self.label_maximum.setText(str(all_maximum))

        # visualize histograms
        num_bins = 50
        colors = []
        for layer in self.selected_image_layers():
            # plot histogram
            hist = histogram(
                layer, num_bins=num_bins, minimum=all_minimum, maximum=all_maximum
            )
            colormap = layer.colormap.colors
            color = np.asarray(colormap[-1, 0:3]) * 255
            colors.append(color)
            # add a new line to the plot (histogram)
            self.plot.plot(hist / np.max(hist), pen=color, name=layer.name)

            # plot min/max
            contrast_limits = layer.contrast_limits
            min_idx = (
                (contrast_limits[0] - all_minimum)
                / (all_maximum - all_minimum)
                * num_bins
            )
            max_idx = (
                (contrast_limits[1] - all_minimum)
                / (all_maximum - all_minimum)
                * num_bins
            )

            arr = np.zeros(hist.shape)
            for i in range(0, len(arr)):
                if i < min_idx:
                    arr[i] = 0
                elif i > max_idx:
                    arr[i] = 1
                else:
                    arr[i] = (i - min_idx) / (max_idx - min_idx)
            # add a new line to the plot (dotted min/max line)
            self.plot.plot(arr, pen=pg.mkPen(color=color, style=Qt.DotLine))

        self.plot.hideAxis("left")
        self.plot.hideAxis("bottom")

        # update sliders
        if rebuild_gui:
            layout = self.sliders.layout()
            for i in reversed(range(layout.count())):
                layout.itemAt(i).widget().setParent(None)
            for i, layer in enumerate(self.selected_image_layers()):

                row = LayerContrastLimitsWidget(
                    layer, colors[i], all_minimum, all_maximum, self
                )

                layout.addWidget(row)

        # patch events
        selected_layers = self.selected_image_layers()
        for layer in self.viewer.layers:
            if hasattr(layer.events, "contrast_limits"):
                layer.events.contrast_limits.disconnect(self._data_changed_event)
                layer.events.data.disconnect(self._data_changed_event)
                if layer in selected_layers:
                    layer.events.contrast_limits.connect(self._data_changed_event)
                    layer.events.data.connect(self._data_changed_event)

    def _data_changed_event(self, event):
        # reset visualization in case a layer's content has changed
        selected_layers = self.selected_image_layers()
        for layer in selected_layers:
            if hasattr(event, "value") and layer.data is event.value:
                reset_histogram_cache(layer)
            self.redraw(rebuild_gui=False)
            return

    def _set_absolutes(self):
        # Set contrast limits to absolute values configured by the user
        lower = self.spinner_lower_absolute.value()
        upper = self.spinner_upper_absolute.value()
        for layer in self.selected_image_layers():
            layer.contrast_limits = [lower, upper]

        self.redraw()

    def _auto_percentiles(self):
        # Set contrast limits to percentiles configured by the user
        print(
            "auto contrast",
            self.spinner_lower_percentile.value(),
            self.spinner_upper_percentile.value(),
        )

        lower_percentile = self.spinner_lower_percentile.value() / 100
        upper_percentile = self.spinner_upper_percentile.value() / 100

        # determine intensities which correspond to the percentiles for each layer
        for layer in self.selected_image_layers():
            hist = histogram(layer, num_bins=256)
            minimum, maximum = min_max(layer.data)

            sum_hist = np.sum(hist)
            sum_it = 0

            lower_threshold = None
            upper_threshold = None

            for i, s in enumerate(hist):
                sum_it = sum_it + s
                if sum_it / sum_hist > lower_percentile and lower_threshold is None:
                    lower_threshold = minimum + (maximum - minimum) * i / len(hist)
                if sum_it / sum_hist >= upper_percentile:
                    upper_threshold = minimum + (maximum - minimum) * i / len(hist)
                    break

            print("set contrast", lower_threshold, upper_threshold)
            layer.contrast_limits = [lower_threshold, upper_threshold]

            self.redraw()

    def _set_full_range(self):
        for layer in self.selected_image_layers():
            layer.contrast_limits = min_max(layer.data)

        self.redraw()

    def selected_image_layers(self):
        return [
            layer
            for layer in self.viewer.layers.selection
            if isinstance(layer, napari.layers.Image)
        ]


class LayerContrastLimitsWidget(QWidget):
    """
    This widget corresponds to a single line represeting a layer with the option to configure min/max contrast limits.
    """

    def __init__(self, layer, color, all_minimum, all_maximum, gui):
        super().__init__(gui)

        self.setLayout(QHBoxLayout())

        lbl = QLabel(layer.name)
        lbl.setStyleSheet("color: #%02x%02x%02x" % tuple(color.astype(int)))
        self.layout().addWidget(lbl)

        # show min/max intensity
        lbl_min = QLabel()
        lbl_min.setText("{:.2f}".format(layer.contrast_limits[0]))
        lbl_max = QLabel()
        lbl_max.setText("{:.2f}".format(layer.contrast_limits[1]))

        # allow to tune min and max within one slider
        slider = QRangeSlider()
        slider.setOrientation(Qt.Horizontal)
        slider.setMinimum(all_minimum)
        slider.setMaximum(all_maximum)
        slider.setValue(layer.contrast_limits)

        # update on change
        def value_changed():
            layer.contrast_limits = slider.value()
            lbl_min.setText("{:.2f}".format(slider.value()[0]))
            lbl_max.setText("{:.2f}".format(slider.value()[1]))
            gui.redraw(rebuild_gui=False)

        slider.valueChanged.connect(value_changed)

        self.layout().addWidget(lbl_min)
        self.layout().addWidget(slider)
        self.layout().addWidget(lbl_max)


def histogram(layer, num_bins: int = 256, minimum=None, maximum=None, use_cle=True):
    """
    This function determines a histogram for a layer and caches it within the metadata of the layer. If the same
    histogram is requested, it will be taken from the cache.
    :return:
    """
    if (
        "bc_histogram_num_bins" in layer.metadata.keys()
        and "bc_histogram" in layer.metadata.keys()
    ):
        if num_bins == layer.metadata["bc_histogram_num_bins"]:
            return layer.metadata["bc_histogram"]

    data = layer.data
    if "dask" in str(type(data)):  # ugh
        data = np.asarray(data)
    intensity_range = None
    if minimum is not None and maximum is not None:
        intensity_range = (minimum, maximum)

    if use_cle:
        try:
            import pyclesperanto_prototype as cle

            hist = np.asarray(
                cle.histogram(
                    data,
                    num_bins=num_bins,
                    minimum_intensity=minimum,
                    maximum_intensity=maximum,
                    determine_min_max=False,
                )
            )
        except ImportError:
            use_cle = False
    if not use_cle:
        hist, _ = np.histogram(data, bins=num_bins, range=intensity_range)

    # cache result
    if hasattr(layer.data, "bc_histogram_num_bins") and hasattr(
        layer.data, "bc_histogram"
    ):
        if num_bins == layer.data.bc_histogram_num_bins:
            return layer.data.bc_histogram_num_bins

    # delete cache when data is changed
    def _refresh_data(event):
        reset_histogram_cache(layer)

        layer.events.data.disconnect(_refresh_data)

    layer.events.data.connect(_refresh_data)

    layer.metadata["bc_histogram_num_bins"] = num_bins
    layer.metadata["bc_histogram"] = hist

    return hist


def reset_histogram_cache(layer):
    if (
        "bc_histogram_num_bins" in layer.metadata.keys()
        and "bc_histogram" in layer.metadata.keys()
    ):
        layer.metadata.pop("bc_histogram_num_bins")
        layer.metadata.pop("bc_histogram")


def min_max(data):
    if "dask" in str(type(data)):  # ugh
        data = np.asarray(data)

    return float(data.min()), float(data.max())


@napari_hook_implementation
def napari_experimental_provide_dock_widget():
    # you can return either a single widget, or a sequence of widgets
    return [BrightnessContrast]
