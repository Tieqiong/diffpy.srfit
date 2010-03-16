########################################################################
#
# diffpy.srfit      by DANSE Diffraction group
#                   Simon J. L. Billinge
#                   (c) 2010 Trustees of the Columbia University
#                   in the City of New York.  All rights reserved.
#
# File coded by:    Chris Farrow
#
# See AUTHORS.txt for a list of people who contributed.
# See LICENSE.txt for license information.
#
########################################################################
"""Form factors (characteristic functions) used in PDF nanoshape fitting.

These are used to calculate the attenuation of the PDF due to a finite size.
For a crystal-like nanoparticle, one can calculate the PDF via
Gnano(r) = f(r) Gcryst(r),
where f(r) is the nanoparticle form factor (or characteristic function) and
Gcryst(f) is the crystal PDF.

These functions are meant to be imported and added to a FitContribution using
the 'registerFunction' method of that class.

"""

__all__ = ["sphericalFF", "spheroidalFF", "spheroidalFF2",
        "lognormalSphericalFF", "sheetFF"]

import numpy
from numpy import pi, sqrt, log, exp, log2, ceil
from numpy import arctan as atan
from numpy import arctanh as atanh
from numpy.fft import ifft, fftfreq
from scipy.special import erf

from diffpy.srfit.fitbase.calculator import Calculator

def sphericalFF(r, psize):
    """Spherical nanoparticle form factor.
    
    r       --  distance of interaction
    psize   --  The particle diameter
    
    From Kodama et al., Acta Cryst. A, 62, 444-453 
    (converted from radius to diameter)

    """
    f = numpy.zeros_like(r)
    if psize > 0: 
        x = r/psize
        g = (1.0 - 1.5*x + 0.5*x*x*x)
        g[x > 1] = 0
        f += g
    return f

def spheroidalFF(r, psize, axrat):
    """Spheroidal nanoparticle form factor.

    Form factor for ellipsoid with radii (psize/2, psize/2, axrat*psize/2)
    
    r      --  distance of interaction
    psize  --  The equatorial diameter
    axrat  --  The ratio of axis lengths

    From Lei et al., Phys. Rev. B, 80, 024118 (2009)
    
    """
    pelpt = axrat

    if psize <= 0 or pelpt <= 0: 
        numpy.zeros_like(r)

    # to simplify the equations
    v = pelpt
    d = psize
    d2 = d*d
    v2 = v*v

    if v == 1: 
        return sphericalFF(r, psize)

    rx = r
    if v < 1:

        r = rx[rx <= v*psize]
        r2 = r*r
        f1 = 1 - 3*r/(4*d*v)*(1-r2/(4*d2)*(1+2.0/(3*v2))) \
                - 3*r/(4*d)*(1-r2/(4*d2))*v/sqrt(1-v2)*atanh(sqrt(1-v2))

        r = rx[numpy.logical_and(rx > v*psize, rx <= psize)]
        r2 = r*r
        f2 = (3*d/(8*r)*(1+r2/(2*d2))*sqrt(1-r2/d2) \
                - 3*r/(4*d)*(1-r2/(4*d2))*atanh(sqrt(1-r2/d2)) \
                ) * v/sqrt(1-v2)

        r = rx[rx > psize]
        f3 = numpy.zeros_like(r)

        f = numpy.concatenate((f1,f2,f3))

    elif v > 1:

        r = rx[rx <= psize]
        r2 = r*r
        f1 = 1 - 3*r/(4*d*v)*(1-r2/(4*d2)*(1+2.0/(3*v2))) \
                - 3*r/(4*d)*(1-r2/(4*d2))*v/sqrt(v2-1)*atan(sqrt(v2-1))

        r = rx[numpy.logical_and(rx > psize, rx <= v*psize)]
        r2 = r*r
        f2 = 1 - 3*r/(4*d*v)*(1-r2/(4*d2)*(1+2.0/(3*v2))) \
            - 3.0/8*(1+r2/(2*d2))*sqrt(1-d2/r2)*v/sqrt(v2-1) \
            - 3*r/(4*d)*(1-r2/(4*d2))*v/sqrt(v2-1) \
            * (atan(sqrt(v2-1)) - atan(sqrt(r2/d2-1)))

        r = rx[rx > v*psize]
        f3 = numpy.zeros_like(r)

        f = numpy.concatenate((f1,f2,f3))

    return f

def spheroidalFF2(r, erad, prad):
    """Spheroidal form factor specified using radii.

    Spheroid with radii (erad, erad, prad)

    prad    --  polar radius
    erad    --  equatorial radius

    erad < prad equates to a prolate spheroid
    erad > prad equates to a oblate spheroid
    erad == prad is a sphere

    """
    psize = 2*erad
    pelpt = prad / erad
    return spheroidalFF(r, psize, pelpt)


def lognormalSphericalFF(r, psize, psig):
    """Spherical nanoparticle form factor with lognormal size distribution.
    
    r      --  distance of interaction
    psize  --  The mean particle diameter
    psig   --  The log-normal width of the particle diameter
    
    Here, r is the independent variable, mu is the mean of the distrubution
    (not of the particle size), and s is the width of the distribution. This
    is the form factor for the lognormal distribution of particle diameter:
    
    F(r, mu, s) = 0.5*Erfc((-mu-3*s^2+Log(r))/(sqrt(2)*s))
               + 0.25*r^3*Erfc((-mu+Log(r))/(sqrt(2)*s))*exp(-3*mu-4.5*s^2)
               - 0.75*r*Erfc((-mu-2*s^2+Log(r))/(sqrt(2)*s))*exp(-mu-2.5*s^2)
    
    The expectation value of the distribution gives the average particle
    diameter, psize. The variance of the distribution gives psig^2. mu and s
    can be expressed in terms of these as:
    
    s^2 = log((psig/psize)^2 + 1)
    mu = log(psize) - s^2/2

    Source unknown
    """
    if psize <= 0: return numpy.zeros_like(r)
    if psig <= 0: return sphericalFF(r, psize)

    erfc = lambda x: 1.0-erf(x)

    sqrt2 = sqrt(2.0)
    s = sqrt(log(psig*psig/(1.0*psize*psize) + 1))
    mu = log(psize) - s*s/2;
    print mu, s
    if mu < 0: return numpy.zeros_like(r)

    return 0.5*erfc((-mu-3*s*s+log(r))/(sqrt2*s)) \
           + 0.25*r*r*r*erfc((-mu+log(r))/(sqrt2*s))*exp(-3*mu-4.5*s*s) \
           - 0.75*r*erfc((-mu-2*s*s+log(r))/(sqrt2*s))*exp(-mu-2.5*s*s)

def sheetFF(r, sthick):
    """Nanosheet form factor
    
    r       --  distance of interaction
    sthick  --  Thickness of nanosheet
    
    From Kodama et al., Acta Cryst. A, 62, 444-453

    """
    if sthick < 0: return numpy.zeros_like(r)

    f = 0.5*sthick/r
    sel = (r <= sthick)
    f[sel] = 1 - f[sel]
    return f

class SASFormFactor(Calculator):
    """Calculator class for form factors from sans-models.

    This class wraps a sans.models.BaseModel to calculate I(Q) related to
    nanoparticle shape. This I(Q) is inverted to f(r) according to:
    f(r) = 1 / (4 pi r) * SINFT(I(Q)),
    where "SINFT" represents the sine Fourier transform.

    Attributes:
    _model      --  BaseModel object this adapts.

    Managed Parameters:
    These depend on the parameters of the BaseModel object held by _model. They
    are created from the 'params' attribute of the BaseModel. If a dispersion
    is set for the BaseModel, the dispersion "width" will be accessible under
    "<parname>_width", where <parname> is the name a parameter adjusted by
    dispersion.

    """

    def __init__(self, name, model):
        """Initialize the generator.

        name    --  A name for the SASFormFactor
        model   --  SASModel object this adapts.
        
        """
        Calculator.__init__(self, name)

        self._model = model

        from diffpy.srfit.sas.sasparameter import SASParameter
        # Wrap normal parameters
        for parname in model.params:
            par = SASParameter(parname, model)
            self.addParameter(par)

        # Wrap dispersion parameters
        for parname in model.dispersion:
            name = parname + "_width"
            parname += ".width"
            par = SASParameter(name, model, parname)
            self.addParameter(par)

        return

    def __call__(self, r):
        """Calculate the form factor from the transform of the BaseModel."""


        # Determine q-values.
        # We want very fine r-spacing so we can properly normalize f(r). This
        # equates to having a large qmax so that the Fourier transform is
        # finely spaced. We also want the calculation to be fast, so we pick
        # qmax such that the number of q-points is a power of 2. This allows us
        # to use the fft. 
        # 
        # The initial dr is somewhat arbitrary, but using dr = 0.01 allows for
        # the f(r) calculated from a particle of diameter 50, over r =
        # arange(1, 60, 0.1) to agree with the sphericalFF with Rw < 1e-4%.
        rmax = r[-1]
        dr = min(0.01, r[1] - r[0])
        dq = pi / rmax
        qmax = pi / dr
        numpoints = int(2**(ceil(log2(qmax/dq))))
        qmax = dq * numpoints

        # Calculate F(q) = q * I(q) from model
        q = fftfreq(int(qmax/dq)) * qmax
        fq = q * self._model.evalDistribution(q)

        # Calculate g(r) and the effective r-points
        rp = fftfreq(numpoints) * 2 * pi / dq
        # Note sine transform = imaginary part of ifft
        gr = ifft(fq).imag

        # Calculate full-fr for normalization
        frp = gr / rp

        # Inerpolate onto requested grid
        fr = numpy.interp(r, rp, gr) / r

        # Normalize. We approximate fr[0] by using the fact that f(r) is linear
        # at low r. By definition, fr[0] should equal 1.
        fr0 = 2*frp[2] - frp[1]
        fr /= fr0

        # Fix potential divide-by-zero issue
        if r[0] == 0:
            fr[0] = 1

        return fr


# End of file
