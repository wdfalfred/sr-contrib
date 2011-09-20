/**
 * @file   genetic_algorithm.hpp
 * @author Ugo Cupcic <ugo@shadowrobot.com>, Contact <contact@shadowrobot.com>
 * @date   Fri Sep 16 15:09:56 2011
*
* Copyright 2011 Shadow Robot Company Ltd.
*
* This program is free software: you can redistribute it and/or modify it
* under the terms of the GNU General Public License as published by the Free
* Software Foundation, either version 2 of the License, or (at your option)
* any later version.
*
* This program is distributed in the hope that it will be useful, but WITHOUT
* ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
* FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
* more details.
*
* You should have received a copy of the GNU General Public License along
* with this program.  If not, see <http://www.gnu.org/licenses/>.
*
*
 * @brief
 *
 *
 */

#ifndef _TERMINATION_CRITERION_HPP_
#define _TERMINATION_CRITERION_HPP_

namespace shadow_robot
{
  struct TerminationCriterion
  {
    double best_fitness;

    unsigned int max_iteration_number;
    unsigned int max_number_function_evaluation;

    enum TerminationReason{NO_CONVERGENCE,
                           BEST_FITNESS, MAX_ITERATION_NUMBER,
                           MAX_NUMBER_FUNCTION_EVALUATION};
  };
}

/* For the emacs weenies in the crowd.
Local Variables:
   c-basic-offset: 2
End:
*/

#endif
