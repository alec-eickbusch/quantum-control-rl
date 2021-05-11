import numpy as np

# Units: nanoseconds, GRad/s

### Test system
if True:
    # Oscillator
    chi = 2 * np.pi * 1e-6 * 80
    kappa = 1 / (1e6)

    # displacement (static for now)
    alpha = 40.0

    # qubit
    gamma_1 = 1 / (100e3)
    gamma_phi = 0

    # Hilbert space size
    N = 30

    # Hilbert space size for intermediate calculation of displacement operators for tomography
    N_large = 100

# Simulator discretization
discrete_step_duration = 1.0
