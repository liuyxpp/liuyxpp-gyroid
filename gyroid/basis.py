# -*- coding: utf-8 -*-
"""
gyroid.basis
===============

:copyright: (c) 2012 by Yi-Xin Liu
:license: BSD, see LICENSE for more details.

"""

import numpy as np
from numpy.linalg import inv

from .common import BRAVAIS,CARTESIAN,EPS

__all__ = ["Basis","Star"]

class Basis(object):
    """
    """
    def __init__(self,group,grid):
        self.stars = []
        self.N = 0
        G2_pre = grid.Gsq[0] # Previous G2
        for G2 in grid.Gsq:
            if np.abs(G2-G2_pre) > EPS:
                self.stars.append(Star(group,grid,G2_pre))
                self.N += 1
                G2_pre = G2


class Star(object):
    """
    A StarSet is a collection of stars with all waves have same magnitude.
    """

    def __init__(self,group,grid,Gsq):
        if self.__check_cancel():
            raise ValueError("Check cancel failed when creating a Star.")
        self.dim = group.dim
        self.Gsq = Gsq
        waves = self.__select_waves(grid,Gsq)
        sorted_waves,phases = self.__sort_waves(waves)
        (self.waves,phases,self.iwaves,iphases) = self.__find_waves_in_star(
                                                    group,grid,sorted_waves)
        self.N = np.size(self.waves,1)
        self.c, self.ic = self.__find_coeff(phases,iphases)
        if self.iwaves is None:
            self.sign = self.__set_coeff_for_closed_star(grid)

    def __select_waves(self,grid,G2):
        (ind,) = np.where(np.abs(grid.Gsq-G2)<EPS)
        if np.max(ind) - np.min(ind) + 1 != np.size(ind):
            raise ValueError("Waves in Grid not sorted according to G^2.")
        return grid.waves[:,ind]

    def __check_cancel(self):
        """
        Not implemented yet. Since we have excluded the cancel waves in
        creating Grid.waves.
        Currently, we do not support canceled stars.
        """
        return False

    def __sort_waves(self,waves,phases=None):
        if self.dim == 1:
            if phases is None:
                if np.size(waves,1) == 1:
                    return waves,None
                return (np.fliplr(np.sort(waves)),None)
            else:
                pw = np.vstack([phases,waves])
                ind = np.lexsort(pw)
                pw_sorted = np.fliplr(pw.take(ind,axis=-1))
                return (np.array([pw_sorted[1]]),pw_sorted[0])

        if self.dim == 2:
            if phases is None:
                rw = np.vstack([waves[1],waves[0]])
                ind = np.lexsort(rw)
                return (np.fliplr(waves.take(ind,axis=-1)),None)
            else:
                prw = np.vstack([phases,waves[1],waves[0]])
                ind = np.lexsort(prw)
                prw_sorted = np.fliplr(prw.take(ind,axis=-1))
                return (np.vstack([prw_sorted[2],prw_sorted[1]]),
                        prw_sorted[0])

        if self.dim == 3:
            if phases is None:
                rw = np.vstack([waves[2],waves[1],waves[0]])
                ind = np.lexsort(rw)
                return (np.fliplr(waves.take(ind,axis=-1)),None)
            else:
                prw = np.vstack([phases,waves[2],waves[1],waves[0]])
                ind = np.lexsort(prw)
                prw_sorted = np.fliplr(prw.take(ind,axis=-1))
                return (np.vstack([
                    prw_sorted[3],prw_sorted[2],prw_sorted[1]]),
                    prw_sorted[0])

        # Following code is a shortcut but hard to read
        # ind = np.lexsort(waves.T)
        # return np.fliplr(np.fliplr(waves.T.take(ind,axis=-1)).T)

    def __calc_phase(self,G,t,basis_type):
        twopi = 2.0 * np.pi
        if basis_type == BRAVAIS:
            return twopi * np.round(np.dot(G,t)).astype(type(G[0]))
        else:
            return twopi * np.dot(G,t)

    def __calc_wave(self,G,R,basis_type):
        if basis_type == BRAVAIS:
            return np.round(np.dot(G,R)).astype(type(G[0]))
        else:
            return np.dot(G,R)

    def __form_star(self,G,group,grid,waves):
        star_waves = None
        phases = None
        for i in np.arange(group.order):
            Gn = self.__calc_wave(G,group.symm[i].R,group.type)
            # Pseudo-Spectral method
            Gn = grid.to_BZ(Gn)

            if index_waves(Gn,waves.T) is not None:
                if star_waves is None:
                    star_waves = np.array([Gn])
                    ph = self.__calc_phase(G,group.symm[i].t,group.type)
                    phases = np.array([ph])
                else:
                    if index_waves(Gn,star_waves) is None:
                        star_waves = np.append(star_waves,[Gn],axis=0)
                        ph = self.__calc_phase(G,group.symm[i].t,group.type)
                        phases = np.append(phases,[ph],axis=0)
            else:
                raise ValueError("Waves does not contain entire star.")
        return star_waves.T,phases

    def __find_waves_in_star(self,g,grid,waves):
        """
        For waves with a same |G|^2, they may form a closed star, two open
        stars, or several closed stars.
        """

        G1 = waves[:,0]
        star_waves, phases = self.__form_star(G1,g,grid,waves)
        star_waves, phases = self.__sort_waves(star_waves,phases)
        Gi = -1.0 * G1
        Gi = grid.to_BZ(Gi)
        if index_waves(Gi,star_waves.T) is not None:
            if np.size(waves,1) != np.size(star_waves,1):
                raise ValueError("Closed star expected.")
            return star_waves,phases,None,None
        else:
            invert_waves, invert_phases = self.__form_star(Gi,g,grid,waves)
            invert_waves, invert_phases = self.__sort_waves(
                                            invert_waves,invert_phases)
            l1 = np.size(star_waves,1)
            l2 = np.size(invert_waves,1)
            if np.size(waves,1) != (l1 + l2) or l1 != l2:
                raise ValueError("Open star pair expected.")
            return star_waves,phases,invert_waves,invert_phases

    def __find_coeff(self,phases,iphases):
        if iphases is None:
            # c_norm = exp(i*phi)
            c_norm = np.exp(complex(0.0,phases[0])) * np.sqrt(self.N)
            return ([np.exp(complex(0.0,phases[i]))/c_norm
                    for i in np.arange(self.N)], None)
        else:
            c_norm = np.exp(complex(0.0,phases[0])) * np.sqrt(self.N)
            ic_norm = np.exp(complex(0.0,phases[self.N-1]))*np.sqrt(self.N)
            return ([np.exp(complex(0.0,phases[i]))/c_norm
                    for i in np.arange(self.N)],
                    [np.exp(complex(0.0,iphases[i]))/ic_norm
                    for i in np.arange(self.N)]
                   )

    def __set_coeff_for_closed_star(self,grid):
        """
        For an ordered closed star, if we denote the first wave in the star G1, then its inversion (-G1) must be the last wave in the star.
        """
        G = self.waves[:,0]
        Gi = -1.0 * G
        Gi = grid.to_BZ(Gi)
        # find index of Gi in the star
        i = index_waves(Gi,self.waves.T)

        c, ci = self.c[0], self.c[i]
        if np.abs(c.imag) < EPS:
            c1 = c.real
        else:
            raise ValueError("""First coefficient in closed star has
                              imaginary part.""")
        if np.abs(ci.imag) < EPS:
            c2 = ci.real
        else:
            raise ValueError("""Last coefficient in closed star has
                              imaginary part.""")

        if np.abs(c1 - c2) < EPS:
            return 1
        elif np.abs(c1 + c2) < EPS:
            self.c = self.c * complex(0.0,-1.0)
            return -1
        else:
            raise ValueError("""Closed star is neither cosine-like nor
                             sine-like.""")
        # for inversion star pairs, the first star's sign is +1
        # the second is -1


def index_waves(w,waves):
    """
    w is a row vector.
    waves is a 2D array, each row is a row vector.
    """
    if np.size(w) != np.size(waves,1):
        return None
    i = 0
    for ww in waves:
        if np.all(np.abs(ww-w) < EPS):
            return i
        i += 1
    return None

