"""
parts.jacobian
-----------------

The :code:`jacobian` module handles calculations of Jacobians in ARTS.
Functionality for computing Jacobians in ARTS is implemented through
three classes:

1. :class:`JacobianCalculation` handles the actual calculation of
   Jacobians and coordinates the interaction with the ARTS workspace.

2. :class:`JacobianQuantity` defines the general interface for quantities
   for which a Jacobian can be calculated and how to toggle the calculation
   of the Jacobian for a given quantity.

3. :class:`Jacobian` handles quantity-specific settings and results. This
   class must be defined for each Jacobian quantity separately.

Calculating Jacobians
=====================

To calculate the Jacobian of a quantity :code:`q` it suffices
to add it to the `jacobian` of the :class:`ArtsSimulation`:

::

    simulation.jacobian.add(q)

This will add the quantity :code:`q` to the quantities for which a Jacobian
should be computed. Moreover it will instantiate the :class:`Jacobian` class
of the quantity :code:`q` and set the :code:`q.jacobian` property of :code:`q`.

It is important to note that :code:`simulation.jacobian` and :code:`q.jacobian`
are of different types: :code:`simulation.jacobian` is of type
:code:`JacobianCalculation` and handles the calculation of the Jacobian for
multiple quantities whereas :code:`q.jacobian` holds the settings and results
of the Jacobian calculation for :code:`q`.

Reference
=========
"""

import scipy as sp
import numpy as np

from abc import ABCMeta, abstractmethod, abstractproperty

from parts.sensor      import ActiveSensor, PassiveSensor
from parts.arts_object import ArtsObject, arts_property
from parts.arts_object import Dimension as dim

################################################################################
# Transformations
################################################################################

class Transformation(metaclass = ABCMeta):
    """
    Abstract base class for transformations of Jacobian quantities.

    ARTS allows the calculation of certain transformations of Jacobian
    quantities. In parts, these transformations are represented by subclasses
    of the :class:`Transformation` class, which defines the general interface
    for transformations of Jacobian quantities.

    The interface consists of two functions:

    - :code:`setup`: When the :code:`setup` function is called the
      transformation object is expected to call the appropriate workspace
      function so that the transformation is added to the most recently added
      JacobianQuantity.

    - :code:`__call__`: Transformation objects should be callable and calling
      them should apply the transformation to a given numeric argument.
    """
    def __init__(self):
        pass

    @abstractmethod
    def setup(self, ws):
        pass

    @abstractmethod
    def __call__(self, x):
        pass

    @abstractmethod
    def invert(self, y):
        pass

class Log10(Transformation):
    """
    The decadal logarithm transformation $f(x) = \log_{10}(x)$.
    """
    def __init__(self):
        Transformation.__init__(self)

    def setup(self, ws):
        ws.jacobianSetFuncTransformation(transformation_func = "log10")

    def __call__(self, x):
        return np.log10(x)

    def invert(self, y):
        return 10.0 ** y

class Log(Transformation):
    """
    The natural logarithm transformation $f(x) = \log_{10}(x)$.
    """
    def __init__(self):
        pass

    def setup(self, ws):
        ws.jacobianSetFuncTransformation(transformation_func = "log")

    def __call__(self, x):
        return np.log(x)

    def invert(self, y):
        return np.exp(1) ** y

class Atanh(Transformation):

    def __init__(self):
        Transformation.__init__(self)
        ArtsObject.__init__(self)

        self.z_min = 0.0
        self.z_max = 1.0

    @arts_property("Numeric")
    def z_min(self):
        return 0.0

    @arts_property("Numeric")
    def z_max(self):
        return 1.2

    def setup(self, ws):
        ws.jacobianSetFuncTransformation(transformation_func = "atanh",
                                         z_min = self.z_min,
                                         z_max = self.z_max)

    def __call__(self, x):
        return np.arctanh(2.0 * (x - self.z_min) / (self.z_max - self.z_min) - 1)

    def invert(self, y):
        return (np.tanh(y) + 1) * 0.5 * (self.z_max - self.z_min) + self.z_min

class Identity(Transformation):
    """
    The identity transformation $f(x) = x$.
    """
    def __init__(self):
        pass

    def setup(self, ws):
        pass

    def __call__(self, x):
        return x

    def invert(self, y):
        return y

################################################################################
# JacobianCalculation
################################################################################

class JacobianCalculation:
    """
    The :class:`JacobianCalculation` keeps track of the quantities for which
    to compute a Jacobian and coordinates their setup.
    """
    def __init__(self):
        """
        Initialize an empty Jacobian calculation.
        """
        self.jacobian_quantities = []

    def add(self, jq):
        """
        Add a quantity to list of quantities for which the Jacobian should
        be computed.

        Arguments:

            jq(:class:`JacobianQuantity`): Add Jacobian calculation for the given
            quantity. The quantity :code:`jq` must be an instance of the
            :class:`JacobianQuantity` abstract base class.
        """
        jq.jacobian = jq.jacobian_class(jq, len(self.jacobian_quantities))
        self.jacobian_quantities += [jq]

    def setup(self, ws):
        """
        Setup the Jacobian calculations on the given workspace.

        Initializes the definition of the Jacobian on the given workspace
        :code:`ws` by calling the :code:`jacobianInit` WSV on the given
        workspace. Calls the setup method for all quantities for which
        a Jacobian should be computed and finalizes the definition of
        the Jacobian by calling the :code:`jacobianClose` WSM.

        Arguments:

            ws(:code:`typhon.arts.workspace.Workspace`): Workspace object
            on which to setup the Jacobian calculation.

        """
        if not self.jacobian_quantities:
            ws.jacobianOff()
        else:
            ws.jacobianInit()
            for jq in self.jacobian_quantities:
                jq.jacobian.setup(ws)
                jq.transformation.setup(ws)
            ws.jacobianClose()


################################################################################
# JacobianQuantity
################################################################################

class JacobianQuantity(metaclass = ABCMeta):
    """
    Abstract interface for quantities for which a Jacobian can be computed.

    Quantities for which a Jacobian can be computed must expose a
    :code:`jacobian_class` which holds all quantity-specific WSM calls and
    settings required to compute its Jacobian.

    After a quantity has been added to the Jacobian quantities of a simulation,
    the :code:`jacobian_class` object representing the settings and results of
    the Jacobian calculation for this specific object can be accessed through
    its :code:`jacobian` property.
    """

    def __init__(self):
        self._jacobian = None

    @abstractproperty
    def jacobian_class(self):
        """
        Return the class object that holds the actual implementation of the
        Jacobian calculation.
        """
        pass

    @property
    def jacobian(self):
        """
        The :code:`jacobian_class` object holding the quantity-specific settings
        and actual results of the Jacobian calculations for this quantity.
        """
        return self._jacobian

    @jacobian.setter
    def jacobian(self, j):
        if not isinstance(j, self.jacobian_class):
           #not isinstance(j, JacobianBase):
            raise ValueError("The jacobian property of a JacobianQuantity"\
                             " can only be set to an instance of the objects"\
                             "own jacobian_class.")
        else:
            self._jacobian = j

################################################################################
# JacobianBase
################################################################################

class JacobianBase(ArtsObject, metaclass = ABCMeta):
    """
    Abstract base class for the Jacobian classes that encapsulate the
    quantity-specific calls and settings of the Jacobian. This class
    muss be inherited by the :code:`jacobian_class` of each
    :code:`JacobianQuantity` object.
    """
    @arts_property("Vector", shape = (dim.Joker,))
    def p_grid(self):
        return np.zeros(0)

    @arts_property("Vector", shape = (dim.Joker,))
    def lat_grid(self):
        return np.zeros(0)

    @arts_property("Vector", shape = (dim.Joker,))
    def lon_grid(self):
        return np.zeros(0)

    def __init__(self, quantity, index):

        self.quantity = quantity
        self.index    = index
        self.quantity.transformation = Identity()

    @property
    def name(self):
        return self.quantity.name

    @abstractmethod
    def setup(self, ws):
        """
        This method should call the :code:`jacobianAdd...` method corresponding to
        the quantity on the given workspace :code:`ws`.
        """
        pass

    def get_grids(self, ws):

        if self.p_grid.size == 0:
            g1 = ws.p_grid
        else:
            g1 = self.p_grid

        if self.lat_grid.size == 0:
            g2 = ws.lat_grid
        else:
            g2 = self.lat_grid

        if self.lon_grid.size == 0:
            g3 = ws.lon_grid
        else:
            g3 = self.lon_grid

        return {"g1" : g1, "g2" : g2, "g3" : g3}

    def get_data(self, ws, data_provider, *args, **kwargs):
        self.get_data_arts_properties(ws, data_provider, *args, **kwargs)
