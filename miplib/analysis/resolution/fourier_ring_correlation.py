"""
Sami Koho 01/2017

Image resolution measurement by Fourier Ring Correlation.

"""

import numpy as np

import miplib.data.iterators.fourier_ring_iterators as iterators
import miplib.processing.image as imops
from miplib.data.containers.fourier_correlation_data import FourierCorrelationData, \
    FourierCorrelationDataCollection
from miplib.data.containers.image import Image
from . import analysis as fsc_analysis
from miplib.processing import windowing

def calculate_single_image_frc(image, args, average=True, trim=True, z_correction=1):
    """
    A simple utility to calculate a regular FRC with a single image input

    :param image: the image as an Image object
    :param args:  the parameters for the FRC calculation. See *miplib.ui.frc_options*
                  for details
    :return:      returns the FRC result as a FourierCorrelationData object

    """
    assert isinstance(image, Image)

    frc_data = FourierCorrelationDataCollection()

    # Hamming Windowing
    if not args.disable_hamming:
        spacing = image.spacing
        image = Image(windowing.apply_hamming_window(image), spacing)

    # Split and make sure that the images are the same siz
    image1, image2 = imops.checkerboard_split(image)
    #image1, image2 = imops.reverse_checkerboard_split(image)
    image1, image2 = imops.zero_pad_to_matching_shape(image1, image2)

    # Run FRC
    iterator = iterators.FourierRingIterator(image1.shape, args.d_bin)
    frc_task = FRC(image1, image2, iterator)
    frc_data[0] = frc_task.execute()

    if average:
        # Split and make sure that the images are the same size
        image1, image2 = imops.reverse_checkerboard_split(image)
        image1, image2 = imops.zero_pad_to_matching_shape(image1, image2)
        iterator = iterators.FourierRingIterator(image1.shape, args.d_bin)
        frc_task = FRC(image1, image2, iterator)

        frc_data[0].correlation["correlation"] *= 0.5
        frc_data[0].correlation["correlation"] += 0.5*frc_task.execute().correlation["correlation"]

    freqs = frc_data[0].correlation["frequency"].copy()
    #log_correction = np.sqrt(2)*np.log(2*freqs + 2.1)/2
    #log_correction = np.sqrt(2)*np.log(np.sqrt(2)*freqs + 2.718281828459)/2

    def func(x, a, b, c, d):
        return a * np.exp(c * (x - b)) + d

    #params = [0.87420745, 1.01606197, 9.77890561, 0.54539224]
    #params = [ 0.9126985, 0.97605337, 13.92594423, 0.55153212]
    #params = [0.87291152, 0.96833531, 14.42136703, 0.58735602]
    params = [0.95988146, 0.97979108, 13.90441896, 0.55146136]

    #log_correction = np.sqrt(2)*func(freqs, *params)
    #log_correction = 1.0

    #if trim:
     #   log_correction[log_correction > 1.0] = 1.0

    #frc_data[0].correlation["frequency"] = freqs*log_correction
    # Analyze results
    analyzer = fsc_analysis.FourierCorrelationAnalysis(frc_data, image1.spacing[0], args)

    result = analyzer.execute(z_correction=z_correction)[0]
    point = result.resolution["resolution-point"][1]

    log_correction = func(point, *params)
    result.resolution["spacing"] /= log_correction
    result.resolution["resolution"] /= log_correction

    return result

def calculate_two_image_frc(image1, image2, args, z_correction=1):
    """
    A simple utility to calculate a regular FRC with a two image input

    :param image: the image as an Image object
    :param args:  the parameters for the FRC calculation. See *miplib.ui.frc_options*
                  for details
    :return:      returns the FRC result as a FourierCorrelationData object
    """
    assert isinstance(image1, Image)
    assert isinstance(image2, Image)

    assert image1.shape == image2.shape

    frc_data = FourierCorrelationDataCollection()

    spacing = image1.spacing

    if not args.disable_hamming:

        image1 = Image(windowing.apply_hamming_window(image1), spacing)
        image2 = Image(windowing.apply_hamming_window(image2), spacing)

    # Run FRC
    iterator = iterators.FourierRingIterator(image1.shape, args.d_bin)
    frc_task = FRC(image1, image2, iterator)
    frc_data[0] = frc_task.execute()

    # Analyze results
    analyzer = fsc_analysis.FourierCorrelationAnalysis(frc_data, image1.spacing[0], args)

    return analyzer.execute(z_correction=z_correction)[0]


class FRC(object):
    """
    A class for calcuating 2D Fourier ring correlation. Contains
    methods to calculate the FRC as well as to plot the results.
    """

    def __init__(self, image1, image2, iterator):
        assert isinstance(image1, Image)
        assert isinstance(image2, Image)

        if image1.shape != image2.shape or tuple(image1.spacing) != tuple(image2.spacing):
            raise ValueError("The image dimensions do not match")
        if image1.ndim != 2:
            raise ValueError("Fourier ring correlation requires 2D images.")

        self.pixel_size = image1.spacing[0]

        # Expand to square
        image1 = imops.zero_pad_to_cube(image1)
        image2 = imops.zero_pad_to_cube(image2)

        self.iterator = iterator
        # Calculate power spectra for the input images.
        self.fft_image1 = np.fft.fftshift(np.fft.fft2(image1))
        self.fft_image2 = np.fft.fftshift(np.fft.fft2(image2))

        # Get the Nyquist frequency
        self.freq_nyq = int(np.floor(image1.shape[0] / 2.0))

    def execute(self):
        """
        Calculate the FRC
        :return: Returns the FRC results.

        """
        radii = self.iterator.radii
        c1 = np.zeros(radii.shape, dtype=np.float32)
        c2 = np.zeros(radii.shape, dtype=np.float32)
        c3 = np.zeros(radii.shape, dtype=np.float32)
        points = np.zeros(radii.shape, dtype=np.float32)

        for ind_ring, idx in self.iterator:
            subset1 = self.fft_image1[ind_ring]
            subset2 = self.fft_image2[ind_ring]
            c1[idx] = np.sum(subset1 * np.conjugate(subset2)).real
            c2[idx] = np.sum(np.abs(subset1) ** 2)
            c3[idx] = np.sum(np.abs(subset2) ** 2)

            points[idx] = len(subset1)

        # Calculate FRC
        spatial_freq = radii.astype(np.float32) / self.freq_nyq
        n_points = np.array(points)

        with np.errstate(divide="ignore", invalid="ignore"):
            frc = np.abs(c1) / np.sqrt(c2 * c3)
            frc[frc == np.inf] = 0.0
            frc = np.nan_to_num(frc)


        data_set = FourierCorrelationData()
        data_set.correlation["correlation"] = frc
        data_set.correlation["frequency"] = spatial_freq
        data_set.correlation["points-x-bin"] = n_points

        return data_set