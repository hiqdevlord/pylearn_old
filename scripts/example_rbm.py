import numpy
import theano
import matplotlib.pyplot as plt
from theano import tensor
from framework.rbm import GaussianBinaryRBM, PersistentCDSampler, \
        training_updates
from framework.optimizer import SGDOptimizer
from framework.rbm_tools import compute_log_z, compute_nll

if __name__ == "__main__":

    data_rng = numpy.random.RandomState(seed=999)
    data = data_rng.normal(size=(500, 20))

    conf = {
        'nvis': 20,
        'nhid': 30,
        'rbm_seed': 1,
        'batch_size': 100,
        'base_lr': 1e-4,
        'anneal_start': 1,
        'pcd_steps': 1,
    }

    rbm = GaussianBinaryRBM(nvis=conf['nvis'], nhid=conf['nhid'],
                            batch_size=conf['batch_size'], irange=0.5)
    rng = numpy.random.RandomState(seed=conf.get('rbm_seed', 42))
    sampler = PersistentCDSampler(rbm, data[0:100], rng,
                                  steps=conf['pcd_steps'])
    minibatch = tensor.matrix()

    optimizer = SGDOptimizer(rbm, conf['base_lr'], conf['anneal_start'])
    updates = training_updates(visible_batch=minibatch, model=rbm,
                               sampler=sampler, optimizer=optimizer)

    proxy_cost = rbm.reconstruction_error(minibatch, rng=sampler.s_rng)
    train_fn = theano.function([minibatch], proxy_cost, updates=updates)

    vis = tensor.matrix('vis')
    free_energy_fn = theano.function([vis], rbm.free_energy_given_v(vis))

    recon = []
    nlls = []
    for j in range(0, 401):
        avg_rec_error = 0

        for i in range(0, 500, 100):
            rec_error = train_fn(data[i:i+100])
            recon.append(rec_error / 100)
            avg_rec_error = (i*avg_rec_error + rec_error) / (i+100)
        print "Epoch %d: avg_rec_error = %f" % (j+1, avg_rec_error)

        if (j%50)==0:
            log_z = compute_log_z(rbm, free_energy_fn)
            nll = compute_nll(rbm, data, log_z, free_energy_fn)
            nlls.append(nll)
            print "Epoch %d: avg_nll = %f" % (j+1, nll)

    plt.subplot(2, 1, 1)
    plt.plot(range(len(recon)), recon)
    plt.xlim(0, len(recon))
    plt.title('Reconstruction error per minibatch')
    plt.xlabel('minibatch number')
    plt.ylabel('reconstruction error')
    plt.subplot(2, 1, 2)
    plt.plot(range(0, len(nlls) * 50, 50), nlls, '-d')
    plt.xlabel('Epoch')
    plt.ylabel('Average nll per data point')
    plt.show()
