import napari
import numpy as np

viewer = napari.Viewer()

viewer.add_image(np.random.random((200, 200)) * 10, colormap='magenta')
viewer.add_image(np.random.poisson(100, (200, 200)), colormap='green')

napari.run()

