"""Autoencoders, denoising autoencoders, and stacked DAEs."""
# Standard library imports
from itertools import izip

# Third-party imports
import numpy
import theano
from theano import tensor
from pylearn.gd.sgd import sgd_updates

# Local imports
from base import Block, Trainer
from utils import sharedX

def safe_update(dict_to, dict_from):
    """
    Like dict_to.update(dict_from), except don't overwrite any keys.
    """
    for key, val in dict(dict_from).iteritems():
        if key in dict_to:
            raise KeyError(key)
        dict_to[key] = val
    return dict_to

theano.config.warn.sum_div_dimshuffle_bug = False
floatX = theano.config.floatX

if 0:
    print 'WARNING: using SLOW rng'
    RandomStreams = tensor.shared_randomstreams.RandomStreams
else:
    import theano.sandbox.rng_mrg
    RandomStreams = theano.sandbox.rng_mrg.MRG_RandomStreams

class DenoisingAutoencoder(Block):
    """
    A denoising autoencoder learns a representation of the input by
    reconstructing a noisy version of it.
    """
    def __init__(self, corruptor, conf, rng=None):
        """Allocate a denoising autoencoder object."""
        if not hasattr(rng, 'randn'):
            rng = numpy.random.RandomState(rng)
        self.corruptor = corruptor
        self.visbias = sharedX(
            numpy.zeros(conf['n_vis']),
            name='vb',
            borrow=True
        )
        self.hidbias = sharedX(
            numpy.zeros(conf['n_hid']),
            name='hb',
            borrow=True
        )
        # TODO: use weight scaling factor if provided, Xavier's default else
        self.weights = sharedX(
            .5 * rng.rand(conf['n_vis'], conf['n_hid']) * conf['irange'],
            name='W',
            borrow=True
        )
        seed = int(rng.randint(2**30))
        self.s_rng = RandomStreams(seed)
        if conf['tied_weights']:
            self.w_prime = self.weights.T
        else:
            self.w_prime = sharedX(
                .5 * rng.rand(conf['n_hid'], conf['n_vis']) * conf['irange'],
                name='Wprime',
                borrow=True
            )

        def _resolve_callable(conf_attr):
            if conf[conf_attr] is None:
                # The identity function, for linear layers.
                return None
            # If it's a callable, use it directly.
            if hasattr(conf[conf_attr], '__call__'):
                return conf[conf_attr]
            elif hasattr(tensor.nnet, conf[conf_attr]):
                return getattr(tensor.nnet, conf[conf_attr])
            elif hasattr(tensor, conf[conf_attr]):
                return getattr(tensor, conf[conf_attr])
            else:
                raise ValueError("Couldn't interpret %s value: '%s'" %
                                 (conf_attr, conf[conf_attr]))

        self.act_enc = _resolve_callable('act_enc')
        self.act_dec = _resolve_callable('act_dec')
        self.conf = conf
        self._params = [
            self.visbias,
            self.hidbias,
            self.weights,
        ]
        if not conf['tied_weights']:
            self._params.append(self.w_prime)

    def _hidden_activation(self, x):
        """Single input pattern/minibatch activation function."""
        if self.act_enc is None:
            act_enc = lambda x: x
        else:
            act_enc = self.act_enc
        return act_enc(self.hidbias + tensor.dot(x, self.weights))

    def hidden_repr(self, inputs):
        """Hidden unit activations for each set of inputs."""
        return [self._hidden_activation(v) for v in inputs]

    def reconstruction(self, inputs):
        """Reconstructed inputs after corruption."""
        corrupted = self.corruptor(inputs)
        hiddens = self.hidden_repr(corrupted)
        if self.act_dec is None:
            act_dec = lambda x: x
        else:
            act_dec = self.act_dec
        return [
            act_dec(self.visbias + tensor.dot(h, self.w_prime))
            for h in hiddens
        ]

    def __call__(self, inputs):
        """
        Forward propagate (symbolic) input through this module, obtaining
        a representation to pass on to layers above.
        """
        return self.hidden_repr(inputs)


class StackedDA(Block):
    """
    A class representing a stacked model. Forward propagation passes
    (symbolic) input through each layer sequentially.
    """
    def __init__(self, corruptors, conf, rng=None):
        """Allocate a stacked denoising autoencoder object."""
        if not hasattr(rng, 'randn'):
            rng = numpy.random.RandomState(rng)
        self._layers = []
        _local = {}
        # Make sure that if we have a sequence of encoder/decoder activations
        # or corruptors, that we have exactly as many as len(conf['n_hid'])
        if hasattr(corruptors, '__len__'):
            assert len(conf['n_hid']) == len(corruptors)
        else:
            corruptors = [corruptors] * len(conf['n_hid'])
        for c in ['act_enc', 'act_dec']:
            if type(conf[c]) is not str and hasattr(conf[c], '__len__'):
                assert len(conf['n_hid']) == len(conf[c])
                _local[c] = conf[c]
            else:
                _local[c] = [conf[c]] * len(conf['n_hid'])
        n_hids = conf['n_hid']
        # The number of visible units in each layer is the initial input
        # size and the first k-1 hidden unit sizes.
        n_viss = [conf['n_vis']] + conf['n_hid'][:-1]
        seq = izip(
            xrange(len(n_hids)),
            n_hids,
            n_viss,
            _local['act_enc'],
            _local['act_dec'],
            corruptors
        )
        # Create each layer.
        for k, n_hid, n_vis, act_enc, act_dec, corr in seq:
            # Create a local configuration dictionary for this layer.
            lconf = {
                'n_hid': n_hid,
                'n_vis': n_vis,
                'act_enc': act_enc,
                'act_dec': act_dec,
                'irange': conf['irange'],
                'tied_weights': conf['tied_weights'],
            }
            da = DenoisingAutoencoder.alloc(corr, lconf, rng)
            self._layers.append(da)

    def layers(self):
        """
        The layers of this model: the individual denoising autoencoder
        objects, which can be individually pre-trained.
        """
        return list(self._layers)

    def params(self):
        """
        The parameters that are learned in this model, i.e. the concatenation
        of all the layers' weights and biases.
        """
        return sum([l.params() for l in self._layers], [])

    def __call__(self, inputs):
        """
        Forward propagate (symbolic) input through this module, obtaining
        a representation to pass on to layers above.
        """
        transformed = inputs
        # Pass the input through each layer of the hierarchy.
        for layer in self._layers:
            transformed = layer(transformed)
        return transformed

class DATrainer(Trainer):
    def __init__(self, model, cost, minibatch, conf):
        """
        Takes a DenoisingAutoencoder object, a (symbolic) cost function
        which takes the input and turns it into a scalar (somehow),
        a (symbolic) minibatch, and a configuration dictionary.
        """
        # Take care of learning rate scales for individual parameters
        learning_rates = {}
        for parameter in model.params():
            lr_name = '%s_lr' % parameter.name
            thislr = conf.get(lr_name, 1.)
            learning_rates[parameter] = sharedX(thislr, lr_name)

        # A shared variable for storing the iteration number.
        iteration = sharedX(0, 'iter')

        # A shared variable for storing the annealed base learning rate, used
        # to lower the learning rate gradually after a certain amount of time.
        annealed = sharedX(conf['base_lr'], 'annealed')

        # Instantiate the class, finally.
        self.__dict__.update(
            dict(model=model, cost=cost, conf=conf,
                 learning_rates=learning_rates, annealed=annealed,
                 iteration=iteration, minibatch=minibatch)
        )

    def updates(self):
        """Compute the updates for each of the parameter variables."""
        ups = {}
        # Base learning rate per example.
        base_lr = theano._asarray(self.conf['base_lr'], dtype=floatX)

        # Annealing coefficient. Here we're using a formula of
        # base_lr * min(0.0, max(base_lr, lr_anneal_start / (iteration + 1))
        frac = self.conf['lr_anneal_start'] / (self.iteration + 1.)
        annealed = tensor.clip(
            tensor.cast(frac, floatX),
            0.0,    # minimum learning rate
            base_lr # maximum learning rate
        )

        # Update the shared variable for the annealed learning rate.
        ups[self.annealed] = annealed
        ups[self.iteration] = self.iteration + 1

        # Calculate the learning rates for each parameter, in the order
        # they appear in model.params()
        learn_rates = [annealed * self.learning_rates[p] for p in self.model.params()]
        # Get the gradient w.r.t. cost of each parameter.
        grads = [
            tensor.grad(self.cost([self.minibatch]), p)
            for p in self.model.params()
        ]
        # Get the updates from sgd_updates, a PyLearn library function.
        p_up = dict(sgd_updates(self.model.params(), grads, learn_rates))

        # Add the things in p_up to ups
        safe_update(ups, p_up)

        # Return the updates dictionary.
        return ups

    def function(self):
        """Compile the Theano training function associated with the trainer"""
        return theano.function(
            [self.minibatch],
            self.cost([self.minibatch]), # Whatever quantities you want returned
            updates=self.updates() # How Theano should update shared vars
        )
