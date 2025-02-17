# -*- coding: utf-8 -*-
"""
Created on Sat Nov 28 11:45:55 2020
@author: Vladimir Sivak
"""

import tensorflow as tf
from tensorflow import complex64 as c64
import tensorflow_probability as tfp


def normalize(state):
    """
    Args:
        state (Tensor([B1,...Bb,N], c64)): batch of quantum states.
    
    Returns:
        state_normalized (Tensor([B1,...Bb,N], c64)): normalized quantum state
        norm (Tensor([B1,...Bb,1], c64)): norm of the batch of states
    """
    normalized, norm = tf.linalg.normalize(state, axis=-1)
    mask = tf.math.is_nan(tf.math.real(normalized))
    state_normalized = tf.where(mask, tf.zeros_like(normalized), normalized)
    return state_normalized, norm


def basis(n, N, batch_shape=[1]):
    """
    Args:
        n (int): index of basis vector
        N (int): Dimension of Hilbert space 
        batch_shape (optional): shape for batch of identical vectors.
        
    Examples:
        basis(2,100,batch_shape=[]) -- unbatched oscillator Fock=2 state.
        basis(0,2,batch_shape=[10]) -- batch of 10 qubit 'g' states.
    """
    return tf.ones(batch_shape + [1], c64) * tf.one_hot(n, N, dtype=c64)


def Kronecker_product(states):
    """
    Kronecker product of states living in different Hilbert spaces.
    
    Args:
        states: [Tensor([B1,...Bb,N1], c64), ..., Tensor([B1,...Bb,Nk], c64)]
            list of k batched states. All states should have the same batch
            shape, and can live in different Hilbert spaces with dimensions
            N1...Nk. The final tensor-product state will have the same batch 
            shape and Hilbert space dimension prod_k(Nk).
            
    Returns:
        tensor_state (Tensor([B1,...Bb,N1*...*Nk], c64)): tensor-product state
        
    Example:
        g = basis(0,2,[30])   # batch of 30 qubit ground states
        fock5 = basis(5,100,[30])  # batch of 30 oscillator Fock=5 states
        psi = Kronecker_product([g, fock5]) # state in combined Hilbert space
    """
    # expand dims to trick the tf.linalg.LinearOperatorKronecker
    states = [tf.expand_dims(s, -1) for s in states]
    operators = list(map(tf.linalg.LinearOperatorFullMatrix, states))
    tensor_state = tf.linalg.LinearOperatorKronecker(operators).to_dense()
    return tf.squeeze(tensor_state, axis=-1)


@tf.function
def measurement(state, M_ops, sample=True):
    """
    Batch measurement projection.
    Args:
        state (Tensor([B1,...Bb,N], c64)): batch of quantum states
        M_ops (dict, Tensor([B1,...Bb,N,N], c64)): dictionary of measurement 
            operators  corresponding to 2 different qubit measurement outcomes.
        sample (bool): flag to sample or return expectation value
    Output:
        state (Tensor([B1,...Bb,N], c64)): batch of collapsed quantum states if
            sample=true, otherwise same as input state.
        obs (Tensor([B1,...Bb], float32)): measurement outcomes from {-1,1} if
            sample=true, otherwise expectation value of qubit sigma_z.
    """
    collapsed, p = {}, {}
    state, _ = normalize(state)

    for i in M_ops.keys():
        collapsed[i] = tf.linalg.matvec(M_ops[i], state)
        collapsed[i], norm = normalize(collapsed[i])
        p[i] = tf.math.real(norm) ** 2

    if sample:
        obs = tfp.distributions.Bernoulli(probs=p[1] / (p[0] + p[1])).sample()
        state = tf.where(obs == 1, collapsed[1], collapsed[0])
        obs = 1 - 2 * obs  # convert to {-1,1}
        obs = tf.cast(obs, dtype=tf.float32)
        return state, obs
    else:
        return state, (p[0] - p[1]) / (p[0] + p[1])


@tf.function
def batch_dot(state1, state2):
    """
    Batch dot-product of two states: conj(state1) * state2
    Args:
        state1, state2 (Tensor([B1,...Bb,N], c64)): batches of states. If one
            of them has batch_shape = [1] or [], will do broadcasting.
    Returns:
        dot_product (Tensor([B1,...Bb,1], c64))
    """
    return tf.math.reduce_sum(tf.math.conj(state1) * state2, axis=-1, keepdims=True)


# @tf.function
def expectation(state, operator, reduce_batch=True):
    """
    Expectation value of <operator> in <state>.
    
    Args:
        state (Tensor([B1,...Bb,N], c64)): batch of states
        operator (Tensor([B1,...Bb,N,N], c64)): operator; can be batched.
        reduce_batch (bool): flag to average result over the batch.
        
    Supports various batching options:
        
        1) state.shape = [B1,...,Bb,N]
           operator.shape  = [B1,...,Bb,N,N]
           
           Returns a batch of expectation values of shape=[B1,...,Bb,1] 
        
        2) shape.shape = [1,N] or [N]
           operator.shape  = [B1,...,Bb,N,N]
           
           Broadcasts 'state' and returns a batch of expectation values of 
           shape=[batch_size,1]
        3) state.shape = [B1,...,Bb,N]
           operator.shape  = [N,N]
           
           If reduce_batch=False returns a batch of expectation values of 
           shape=[B1,...,Bb,1]. If reduce_batch=True reduces over a batch 
           of states and returns a single expectation value of shape [].
    """
    state, _ = normalize(state)
    expect_batch = batch_dot(state, tf.linalg.matvec(operator, state))

    if reduce_batch:
        expect_batch_reduced = tf.math.reduce_mean(expect_batch)
        return expect_batch_reduced

    return expect_batch


# TODO: this is very memory-inefficient, write a custom kronecker product
def tensor(operators):
    """
    Tensor product of operators acting on different Hilbert spaces.
    """
    operators = list(map(tf.linalg.LinearOperatorFullMatrix, operators))
    tensor_prod = tf.linalg.LinearOperatorKronecker(operators).to_dense()
    return tensor_prod


# utility functions added by Alec. Will add documentation soon.
# takes a batch of states and returns a density matrix
def density_matrix(psi_batch):
    norm = tf.constant((1 / psi_batch.shape[0]), dtype=tf.complex64)
    return norm * tf.einsum("ki,kj->ij", psi_batch, tf.math.conj(psi_batch))


# basic expectation value
def expect(psi, O):
    return tf.einsum("j,ji,i->", tf.math.conj(psi), O, psi)


# Average expectation value of a batch of states
def batch_psi_expect(psi_batch, O):
    norm = tf.constant((1 / psi_batch.shape[0]), dtype=tf.complex64)
    return norm * tf.einsum("ki,ij,kj", tf.math.conj(psi_batch), O, psi_batch)


# batch of operators and batch of states --> average expectation value for each operator
def batch_expect(psi_batch, O_batch):
    norm = tf.constant((1 / psi_batch.shape[0]), dtype=tf.complex64)
    return norm * tf.einsum("ki,bij,kj->b", tf.math.conj(psi_batch), O_batch, psi_batch)


# Take single state and create batch of states for use in MC simulation.
def copy_state_to_batch(state, batch_size):
    s = tf.tile(state, [batch_size])
    return tf.reshape(s, [batch_size, state.shape[0]])
