# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 14:58:30 2020

@author: Vladimir Sivak
"""

import tensorflow as tf
from tensorflow.keras.backend import batch_dot
import tensorflow_probability as tfp



# TODO: For now supports only a single collapse op, add multiple
class QuantumTrajectorySim(object):
    """
    Tensorflow implementation of the Monte Carlo quantum trajectory simulator.
    
    """
    def __init__(self, Kraus, steps):
        """
        Input:
            Kraus -- dictionary of Kraus operators. Dict keys are integers. 
                     K[0] is no-jump operator, the rest are jump operators.
                     Shape of each operator is [b,NH,NH], b is batch size
            steps -- number of steps to run the trajectory
            
        """
        self.Kraus = Kraus
        self.steps = steps


    def _step(self, j, psi):
        """
        One step in the Markov chain.
        
        """
        traj, p, norm = {}, {}, {}
        cumulant = tf.zeros([psi.shape[0],1])
        prob = tf.random.uniform([psi.shape[0],1])
        state = tf.zeros(psi.shape, dtype=tf.complex64)
        for i in self.Kraus.keys():
            # State trajectory for this Kraus operator
            traj[i] = batch_dot(self.Kraus[i], psi)            # shape = [b,N]
            p[i] = batch_dot(tf.math.conj(traj[i]), traj[i])   # shape = [b,1]
            p[i] = tf.math.real(p[i])
            norm[i] = tf.math.sqrt(p[i]) + 1e-18               # shape = [b,1]
            norm[i] = tf.cast(norm[i], tf.complex64)
            traj[i] = traj[i] / norm[i]
            # Make a mask to select the correct trajectory
            mask1 = prob > cumulant 
            mask2 = prob < cumulant + p[i]
            mask1  = tf.cast(mask1, tf.complex64)
            mask2  = tf.cast(mask2, tf.complex64)
            # Update state and cumulant
            state += traj[i] * mask1 * mask2
            cumulant += p[i]

        return [j+1, state]


    # def _step(self, j, psi):
    #     """
    #     One step in the Markov chain.
        
    #     """
    #     traj, p, norm = {}, {}, {} 
    #     for i in self.Kraus.keys():
    #         traj[i] = batch_dot(self.Kraus[i], psi)            # shape = [b,N]
    #         p[i] = batch_dot(tf.math.conj(traj[i]), traj[i])   # shape = [b,1]
    #         p[i] = tf.math.real(p[i])                           
    #         norm[i] = tf.math.sqrt(p[i])                       # shape = [b,1]
    #         norm[i] = tf.cast(norm[i], dtype=tf.complex64)
    #         traj[i] = traj[i] / norm[i]
        
    #     jumps = tfp.distributions.Bernoulli(probs=p[1]/(p[0]+p[1])).sample()
    #     mask  = tf.cast(jumps, dtype=tf.complex64)
    #     state = traj[1] * mask + traj[0] * (1 - mask)
    #     return [j+1, state]

    def _cond(self, j, psi):
        return tf.less(j, self.steps)

    def normalize(self, state):
        """
        Batch normalization of the wave function.
        
        Input:
            state -- batch of state vectors; shape=[batch_size,NH]
            
        """
        norm = tf.math.real(batch_dot(tf.math.conj(state),state))
        norm = tf.cast(tf.math.sqrt(norm), tf.complex64)
        state = state / norm
        return state


    def run(self, psi):
        """
        Simulate a batch of trajectories for 'steps' steps.
        
        Input:
            psi -- batch of state vectors; shape=[b,NH]
            
        """
        psi = self.normalize(psi)
        j = tf.constant(0)
        _, psi = tf.while_loop(self._cond, self._step, 
                               loop_vars=[j, psi])
        return psi
    
    