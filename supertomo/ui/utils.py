"""
Various utilities that are used to convert command line parameters into
data types that the progrma understands.
"""

import numpy

def float2dtype(float_type):
    """Return numpy float dtype object from float type label.
    """
    if float_type == 'single' or float_type is None:
        return numpy.float32
    if float_type == 'double':
        return numpy.float64
    raise NotImplementedError (`float_type`)


def get_user_input(message):
    """
    A method to ask question. The answer needs to be yes or no.

    Parameters
    ----------
    :param message  string, the question

    Returns
    -------

    Return a boolean: True for Yes, False for No
    """
    while True:
        answer = raw_input(message)
        if answer in ('y', 'Y', 'yes', 'YES'):
            return True
        elif answer in ('n', 'N', 'no', 'No'):
            return False
        else:
            print "Unkown command. Please state yes or no"