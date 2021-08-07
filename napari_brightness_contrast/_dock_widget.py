from qtpy.QtWidgets import QSpacerItem, QSizePolicy
from napari_plugin_engine import napari_hook_implementation
from qtpy.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QSpinBox
from qtpy.QtCore import Qt
from superqt import QRangeSlider

import pyqtgraph as pg
import numpy as np
import napari

class Brightness_Contrast(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer
        napari_viewer.layers.selection.events.changed.connect(self._on_selection)

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

        # auto-contrast using percentiles
        percentiler = QWidget()
        percentiler.setLayout(QHBoxLayout())

        lbl = QLabel("Percentiles")
        lower = QSpinBox()
        lower.setMinimum(0)
        lower.setMaximum(100)
        lower.setValue(1)
        upper = QSpinBox()
        upper.setMinimum(0)
        upper.setMaximum(100)
        upper.setValue(99)

        btn = QPushButton("Auto")
        btn.clicked.connect(self._auto_percentiles)
        percentiler.layout().addWidget(lbl)
        percentiler.layout().addWidget(lower)
        percentiler.layout().addWidget(upper)
        percentiler.layout().addWidget(btn)
        self.lower = lower
        self.upper = upper

        # setup layout
        self.setLayout(QVBoxLayout())

        self.layout().addWidget(graph_container)
        self.layout().addWidget(min_max_widget)
        self.layout().addWidget(self.sliders)
        self.layout().addWidget(percentiler)

        verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.layout().addItem(verticalSpacer)
        self.layout().setSpacing(0)

        self.redraw()

    def _on_selection(self, event):
        # redraw when layer selection has changed
        self.redraw()

    def redraw(self, rebuild_gui=True):
        if not hasattr(self, "p2"):
            self.p2 = self.graphics_widget.addPlot()
        else:
            self.p2.clear()

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
        all_maximum = np.ceil(all_maximum) if all_maximum is not None else all_minimum + 1

        self.label_minimum.setText(str(all_minimum))
        self.label_maximum.setText(str(all_maximum))

        # visualize histograms
        num_bins = 50
        colors = []
        for layer in self.selected_image_layers():
            # plot histogram
            hist = histogram(layer.data, num_bins=num_bins, minimum=all_minimum, maximum=all_maximum)
            colormap = layer.colormap.colors
            color = np.asarray(colormap[-1, 0:3]) * 255
            colors.append(color)
            self.p2.plot(hist / np.max(hist), pen=color, name=layer.name)

            # plot min/max
            contrast_limits = layer.contrast_limits
            min_idx = (contrast_limits[0] - all_minimum) / (all_maximum - all_minimum) * num_bins
            max_idx = (contrast_limits[1] - all_minimum) / (all_maximum - all_minimum) * num_bins

            arr = np.zeros(hist.shape)
            for i in range(0, len(arr)):
                if i < min_idx:
                    arr[i] = 0
                elif i > max_idx:
                    arr[i] = 1
                else:
                    arr[i] = (i - min_idx) / (max_idx - min_idx)
            self.p2.plot(arr, pen=pg.mkPen(color=color, style=Qt.DotLine))

        self.p2.hideAxis('left')
        self.p2.hideAxis('bottom')

        # update sliders
        if rebuild_gui:
            layout = self.sliders.layout()
            for i in reversed(range(layout.count())):
                layout.itemAt(i).widget().setParent(None)
            for i, layer in enumerate(self.selected_image_layers()):

                row = LayerContrastLimitsWidget(layer, colors[i], all_minimum, all_maximum, self)

                layout.addWidget(row)



    def _auto_percentiles(self):
        print("auto contrast", self.lower.value(), self.upper.value())

        lower_percentile = self.lower.value() / 100
        upper_percentile = self.upper.value() / 100

        for layer in self.selected_image_layers():
            hist = histogram(layer.data, num_bins=256)
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

    def selected_image_layers(self):
        return [layer for layer in self.viewer.layers.selection if isinstance(layer, napari.layers.Image)]

class LayerContrastLimitsWidget(QWidget):
    def __init__(self, layer, color, all_minimum, all_maximum, gui):
        super().__init__()

        self.setLayout(QHBoxLayout())

        lbl = QLabel(layer.name)
        lbl.setStyleSheet('color: #%02x%02x%02x' % tuple(color.astype(int)))
        self.layout().addWidget(lbl)

        lbl_min = QLabel()
        lbl_min.setText("{:.2f}".format(layer.contrast_limits[0]))
        lbl_max = QLabel()
        lbl_max.setText("{:.2f}".format(layer.contrast_limits[1]))

        slider = QRangeSlider()
        slider.setOrientation(Qt.Horizontal)
        slider.setMinimum(all_minimum)
        slider.setMaximum(all_maximum)
        slider.setValue(layer.contrast_limits)

        def value_changed():
            layer.contrast_limits = slider.value()
            lbl_min.setText("{:.2f}".format(slider.value()[0]))
            lbl_max.setText("{:.2f}".format(slider.value()[1]))
            gui.redraw(rebuild_gui=False)

        slider.valueChanged.connect(value_changed)

        self.layout().addWidget(lbl_min)
        self.layout().addWidget(slider)
        self.layout().addWidget(lbl_max)

def histogram(data, num_bins : int = 256, minimum = None, maximum = None, use_cle=True):
    intensity_range = None
    if minimum is not None and maximum is not None:
        intensity_range = (minimum, maximum)

    if use_cle:
        try:
            import pyclesperanto_prototype as cle
            hist = np.asarray(cle.histogram(data, num_bins=num_bins, minimum_intensity=minimum, maximum_intensity=maximum, determine_min_max=False))
        except ImportError:
            use_cle = False
    if not use_cle:
        hist, _ = np.histogram(data, bins=num_bins, range=intensity_range)
    return hist

def min_max(data):
    return data.min(), data.max()


@napari_hook_implementation
def napari_experimental_provide_dock_widget():
    # you can return either a single widget, or a sequence of widgets
    return [Brightness_Contrast]
