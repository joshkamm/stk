"""
Defines crossover operations via the ``Crossover`` class.

Extending MMEA: Adding crossover functions.
-------------------------------------------
If a new crossover operation is to be added to MMEA it should be added
as a method in the ``Crossover`` class defined in this module. The only
requirements are that the first two arguments are ``macro_mol1`` and
``macro_mol2`` (excluding ``self`` or ``cls``) and that any offspring
are returned in a ``Population`` instance.

The naming requirement of ``macro_mol1`` and ``macro_mol2`` exists to
help users identify which arguments are handled automatically by MMEA
and which they need to define in the input file. The convention is that
if the crossover function takes arguments called  ``macro_mol1`` and
``macro_mol2`` they do not have to be specified in the input file.

If the crossover function does not fit neatly into a single function
make sure that any helper functions are private, ie that their names
start with a leading underscore.

"""

import logging
from collections import Counter
import numpy as np
from itertools import islice

from .population import Population
from .plotting import plot_counter
from ..molecular.molecules import Cage


logger = logging.getLogger(__name__)


class Crossover:
    """
    Carries out crossover operations on the population.

    Instances of the ``Population`` class delegate crossover operations
    to instances of this class. They do this by calling:

        >>> offspring_pop = pop.gen_offspring()

    which returns a new population consisting of molecules generated by
    performing crossover operations on members of ``pop``. This class
    invokes an instance of the ``Selection`` class to select the
    parent pool. Both an instance of this class and the ``Selection``
    class are held in the `ga_tools` attribute of a ``Population``
    instance.

    This class is initialized with a ``FunctionData`` instance. The
    object holds the name of the crossover function to be used by the
    population as well as any additional parameters the function may
    require. Crossover functions should be defined as methods within
    this class.

    Members of this class are also initialized with an integer which
    holds the number of crossover operations to be performed each
    generation.

    Attributes
    ----------
    funcs : list of FunctionData instances
        This lists holds all the crossover functions which are to be
        applied by the GA. One will be chosen at random when a
        crossover is desired. The likelihood that each is selected is
        given by `weights`.

    num_mutations : int
        The number of crossovers that needs to be performed each
        generation.

    weights : None or list of floats (default = None)
        When ``None`` each crossover function has equal likelihood of
        being picked. If `weights` is a list each float corresponds to
        the probability of selecting the crossover function at the
        corresponding index.

    """

    def __init__(self, funcs, num_crossovers, weights=None):
        self.funcs = funcs
        self.weights = weights
        self.num_crossovers = num_crossovers

    def __call__(self, population, counter_path=''):
        """
        Carries out crossover operations on the supplied population.

        This function selects members of the population and crosses
        them until either all possible parents have been crossed or the
        required number of successful crossover operations has been
        performed.

        The offspring generated are returned together in a
        ``Population`` instance. Any molecules that are created via
        crossover and match a molecule present in the original
        population are removed.

        Parameters
        ----------
        population : Population
            The population instance who's members are to crossed.

        counter_path : str (default = '')
            The name of the .png file showing which members were
            selected for crossover. If '' then no file is made.

        Returns
        -------
        Population
            A population with all the offspring generated held in the
            `members` attribute. This does not include offspring which
            correspond to molecules already present in `population`.

        """

        offspring_pop = Population(population.ga_tools)
        counter = Counter()

        parent_pool = islice(population.select('crossover'),
                             self.num_crossovers)
        for i, parents in enumerate(parent_pool, 1):
            logger.info('Crossover number {}. Finish when {}.'.format(
                                           i, self.num_crossovers))
            counter.update(parents)
            # Get the crossover function.
            func_data = np.random.choice(self.funcs, p=self.weights)
            func = getattr(self, func_data.name)

            try:
                # Apply the crossover function and supply any
                # additional arguments to it.
                offspring = func(*parents, **func_data.params)

                # Print the names of offspring which have been returned
                # from the cache.
                for o in offspring:
                    if o.name:
                        logger.debug(('Offspring "{}" retrieved '
                                      'from cache.').format(o.name))

                # Add the new offspring to the offspring population.
                offspring_pop.add_members(offspring)

            except Exception as ex:
                errormsg = ('Crossover function "{}()" failed on '
                            'molecules PARENTS.').format(
                            func_data.name)

                pnames = ' and '.join('"{}"'.format(p.name) for
                                      p in parents)
                errormsg = errormsg.replace('PARENTS', pnames)
                logger.error(errormsg, exc_info=True)

        # Make sure that only original molecules are left in the
        # offspring population.
        offspring_pop -= population

        if counter_path:
            # Update counter with unselected members and plot counter.
            for member in population:
                if member not in counter.keys():
                    counter.update({member: 0})
            plot_counter(counter, counter_path)

        return offspring_pop

    """
    The following crossover operations apply to ``Cage`` instances

    """

    def bb_lk_exchange(self, macro_mol1, macro_mol2):
        """
        Exchanges the building-blocks* and linkers of cages.

        This operation is basically:

            bb1-lk1 + bb2-lk2 --> bb1-lk2 + bb2-lk1,

        where bb-lk represents a building-block* - linker combination
        of a cage.

        If the parent cages do not have the same topology the pair of
        offspring are created for each topology. This means that there
        may be up to 4 offspring.

        Parameters
        ----------
        macro_mol1 : Cage
            The first parent cage. Its building-block* and linker are
            combined with those of `cage2` to form new cages.

        macro_mol2 : Cage
            The second parent cage. Its building-block* and linker are
            combined with those of `cage1` to form new cages.

        Returns
        -------
        Population
            A population of all the offspring generated by crossover of
            `macro_mol1` with `macro_mol2`.

        """

        # Make a variable for each building-block* and linker of each
        # each cage. Make a set consisting of topologies of the cages
        # provided as arguments - this automatically removes copies.
        # For each topology create two offspring cages by combining the
        # building-block* of one cage with the linker of the other.
        # Place each new cage into a ``Population`` instance and return
        # that.

        _, c1_lk = max(zip(macro_mol1.bb_counter.values(),
                        macro_mol1.bb_counter.keys()))
        _, c1_bb = min(zip(macro_mol1.bb_counter.values(),
                        macro_mol1.bb_counter.keys()))

        _, c2_lk = max(zip(macro_mol2.bb_counter.values(),
                        macro_mol2.bb_counter.keys()))
        _, c2_bb = min(zip(macro_mol2.bb_counter.values(),
                        macro_mol2.bb_counter.keys()))


        offspring_pop = Population()
        # For each topology create a new pair of offspring using the
        # building block pairings determined earlier.
        topologies = (x.topology for x in (macro_mol1, macro_mol2))
        for topology in topologies:
            offspring1 = Cage((c1_lk, c2_bb), topology)
            offspring2 = Cage((c2_lk, c1_bb), topology)
            offspring_pop.add_members((offspring1, offspring2))

        return offspring_pop
