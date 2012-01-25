class TrainingAlgorithm(object):
    """
    An abstract superclass that defines the interface of training
    algorithms.
    """
    def setup(self, model):
        """
        Initialize the given training algorithm.

        Parameters
        ----------
        model : object
            Object that implements the Model interface defined in
            `pylearn2.models`.

        Notes
        -----
        Called by the training script prior to any calls involving data.
        This is a good place to compile theano functions for doing learning.
        """
        self.model = model

    def train(self, dataset):
        """
        Performs some amount of training, generally one "epoch" of online
        learning

        Parameters
        ----------
        dataset : object
            Object implementing the dataset interface defined in
            `pylearn2.datasets.dataset.Dataset`.

        Returns
        -------
        status : bool
            `True` if the algorithm wishes to continue for another epoch.
            `False` if the algorithm has converged.
        """
        raise NotImplementedError()
