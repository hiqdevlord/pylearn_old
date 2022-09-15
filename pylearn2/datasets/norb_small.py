import numpy
import os

from pylearn2.datasets import dense_design_matrix
from pylearn.io import filetensor
from pylearn2.datasets import retina

class NORBSmall(dense_design_matrix.DenseDesignMatrix):
    """
    A pylearn2 dataset object for the small NORB dataset (v1.0).
    """

    @classmethod
    def load(cls, which_set, desc):

        assert desc in ['dat','cat','info']

        base = '%s/norb_small/original/smallnorb-' % os.getenv('PYLEARN2_DATA_PATH')
        if which_set == 'train':
            base += '5x46789x9x18x6x2x96x96-training'
        else:
            base += '5x01235x9x18x6x2x96x96-testing'

        fp = open(base + '-%s.mat' % desc, 'r')
        data = filetensor.read(fp)
        fp.close()

        return data

    def __init__(self, which_set, center=False, multi_target = False):
        """
        :param which_set: one of ['train','test']
        :param center: data is in range [0,256], center=True subtracts 127.5.
        :param multi_target: load extra information as additional labels.
        """
        assert which_set in ['train','test']

        X = NORBSmall.load(which_set, 'dat')

        # put things in pylearn2's DenseDesignMatrix format
        X = numpy.cast['float32'](X)
        X = X.reshape(-1, 2*96*96)

        #this is uint8
        y = NORBSmall.load(which_set, 'cat')
        if multi_target:
            y_extra = NORBSmall.load(which_set, 'info')
            y = numpy.hstack((y[:,numpy.newaxis],y_extra))

        if center:
            X -= 127.5

        view_converter = dense_design_matrix.DefaultViewConverter((96,96,2))

        super(NORBSmall,self).__init__(X = X, y = y, view_converter = view_converter)


class FoveatedNORB(dense_design_matrix.DenseDesignMatrix):

    @classmethod
    def load(cls, which_set):

        base = '%s/norb_small/foveated/smallnorb-' % os.getenv('PYLEARN2_DATA_PATH')
        if which_set == 'train':
            base += '5x46789x9x18x6x2x96x96-training-dat'
        else:
            base += '5x01235x9x18x6x2x96x96-testing-dat'

        data = numpy.load(base + '.npy', 'r')
        return data

    def __init__(self, which_set, center=False, multi_target = False):
        """
        :param which_set: one of ['train','test']
        :param center: data is in range [0,256], center=True subtracts 127.5.
        :param multi_target: load extra information as additional labels.
        """
        assert which_set in ['train','test']

        X = FoveatedNORB.load(which_set)

        # put things in pylearn2's DenseDesignMatrix format
        X = numpy.cast['float32'](X)

        #this is uint8
        y = NORBSmall.load(which_set, 'cat')
        if multi_target:
            y_extra = NORBSmall.load(which_set, 'info')
            y = numpy.hstack((y[:,numpy.newaxis],y_extra))

        if center:
            X -= 127.5

        view_converter = retina.RetinaCodingViewConverter((96,96,2), (8,4,2,2))

        super(FoveatedNORB,self).__init__(X = X, y = y, view_converter = view_converter)

