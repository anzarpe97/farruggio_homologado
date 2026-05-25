# -*- coding: utf-8 -*-
# Utilidades para cálculos de préstamos (sin dependencias externas)
import math

def pmt(rate, nper, pv, fv=0, when='end'):
    if rate == 0:
        return -(pv + fv) / nper
    when_val = 1 if when == 'begin' else 0
    return -(rate * (fv + pv * (1 + rate) ** nper)) / ((1 + rate * when_val) * ((1 + rate) ** nper - 1))

def ipmt(rate, per, nper, pv, fv=0, when='end'):
    if rate == 0:
        return 0.0
    when_val = 1 if when == 'begin' else 0
    pmt_val = pmt(rate, nper, pv, fv, when)
    if when_val == 1 and per == 1:
        return 0.0
    if when_val == 1:
        per -= 1
    return -(pv * (1 + rate) ** (per - 1) * rate + pmt_val * ((1 + rate) ** (per - 1) - 1))
