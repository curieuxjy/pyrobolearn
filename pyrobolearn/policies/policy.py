#!/usr/bin/env python
"""Define the basic Policy class.

A policy couples one or several learning model(s), the action, and state together. In this framework, the policy
usually represents the robot's "brain".

Dependencies:
- `pyrobolearn.states`
- `pyrobolearn.actions`
- `pyrobolearn.models`
- `pyrobolearn.approximators`
- `pyrobolearn.exploration`
"""

import collections
import pickle
import numpy as np
import torch

from pyrobolearn.states import State
from pyrobolearn.actions import Action

from pyrobolearn.models import Model
from pyrobolearn.approximators import Approximator

__author__ = "Brian Delhaisse"
__copyright__ = "Copyright 2018, PyRoboLearn"
__credits__ = ["Brian Delhaisse"]
__license__ = "MIT"
__version__ = "1.0.0"
__maintainer__ = "Brian Delhaisse"
__email__ = "briandelhaisse@gmail.com"
__status__ = "Development"


class Policy(object):
    r"""Abstract `Policy` class.

    A policy maps a state to an action, and is often denoted as :math:`\pi_{\theta}(a_t|s_t)`, where :math:`\theta`
    represents the policy parameters. It represents the cognitive part of the agent(s).

    In the PyRoboLearn (PRL) framework, the policy groups the learning model / function approximator, action, and
    state objects. Note that for some policies the state object is not required as they have an inner time state which
    allows to generate the next action each time they are called.

    Anyway, the policy is dissociated from the learning model as this last one can be used for different purposes as
    well. For instance, a neural network can be used to represent a policy but also a value function approximator, or
    a dynamic transition probability function as well. We thus separate these 2 notions (policy and learning model /
    approximator).

    The policy is also loosely dissociated from the simulator and more specifically from the agent's body, as this last
    one is seen as being part of the environment. The states and actions are what connects the policy with the
    environment (and thus the simulator). The states and actions are given to the policy, and allows to build
    automatically a learning model / approximator (if not given) by inferring the dimensions of the inputs and outputs
    of the model.

    In PRL, there are 3 abstraction layers; the learning model, a possible function approximator, and the policy.
    The learning model is completely independent on concepts such as `State` and `Action` created in this framework.
    The `Approximator` then combines the `State`, `Action`, and `Model` together. Finally, the `Policy` is just an
    instance of that `Approximator` where the input is the `State` and the output is the `Action`. Policies can
    also directly uses the learning models without defining or using an `Approximator`. Approximators make sense when
    the learning models can be used for other function approximators such as value functions, dynamic transition
    probability functions, etc. Some models such as movement primitives are too specific and are not general function
    approximators and thus general approximators for them do not exist. Also, policies have a control update rate in
    the case we are running in real-time, or a number of time steps they are inactive and return the same action in
    the case we control when the simulator / environment performs a step.

    Finally, note that in PRL, the policy is the one responsible to execute the action by calling it; i.e. `action()`.
    This is not performed by the environment nor the approximator.

    .. note::

        Exploration can be carried out by the policy, by specifying the exploration strategy (that is, exploration
        in the parameter or action space). The Exploration strategy wraps the Policy.

    Example::

        # create simulator
        simulator = BulletSim(render=True)

        # create world
        world = BasicWorld(simulator)

        # create robot
        robot = world.load_robot('robot_name')

        # create states / actions
        states = JointPositionState(robot) + JointVelocityState(robot)
        actions = JointPositionAction(robot)

        # optional: create learning model (if defined, it has to agree with the dimensions of states/actions)
        model = NN(...)

        # create policy (if learning model not defined, it will create it inside)
        policy = Policy(states, actions, model)

        # create rewards/costs (i.e. r(s,a,s')): gives robot, or state/actions
        reward = ForWardProgressReward(robot) + FallenCost(robot) + PowerConsumptionCost(robot)

        # create environment to interact with
        env = Env(world, states, rewards)

        # create and run a RL task
        task = RLTask(env, policy)
        task.run()

        # Optional: create RL algo (see RL_Algo)

    .. seealso::

        * `state.py`: describes the various states
        * `action.py`: describes the various actions
        * `model.py`: describes the abstract learning model class
        * `approximator.py`: describe the function approximator class (which is the intermediary layer between
            the policy and the learning model)
        * `exploration.py`: describes how to explore using the policy
    """

    def __init__(self, states, actions, model=None, rate=1, preprocessors=None, postprocessors=None,
                 distribution=None, *args, **kwargs):
        r"""
        Initialize a policy (and the inner approximator / learning model).

        Args:
            actions (Action): At each step, by calling `policy.act(state)`, the `actions` are computed by the policy,
                and should be given to the environment. As with the `states`, the type and size/shape of each action
                can be inferred and could be used to automatically build a policy. The `action` connects the policy
                with a controllable object (such as a robot) in the environment.
            states (State): By giving the `states` to the policy, it can automatically infer the type and size/shape
                of each state, and thus can be used to automatically build a policy. At each step, the `states`
                are filled by the environment, and read by the policy. The `state` connects the policy with one or
                several objects (including robots) in the environment. Note that some policies don't use any state
                information.
            model (Approximator, Model, None): inner model or approximator
            rate (int, float): rate (float) at which the policy operates if we are operating in real-time. If we are
                stepping deterministically in the simulator, it represents the number of ticks (int) to sleep before
                executing the model.
            preprocessors (Processor, list of Processor, None): pre-processors to be applied to the given input
            postprocessors (Processor, list of Processor, None): post-processors to be applied to the output
            distribution:
            *args (list): list of arguments
            **kwargs (dict): dictionary of arguments
        """
        self.states = states
        self.actions = actions
        self.model = model
        self.train_mode = False
        self.rate = rate
        self.cnt = 0
        self.action_data = None

        # preprocessors and postprocessors
        if preprocessors is None:
            preprocessors = []
        if not isinstance(preprocessors, collections.Iterable):
            preprocessors = [preprocessors]
        self.preprocessors = preprocessors

        if postprocessors is None:
            postprocessors = []
        if not isinstance(postprocessors, collections.Iterable):
            postprocessors = [postprocessors]
        self.postprocessors = postprocessors

    ##############
    # Properties #
    ##############

    @property
    def states(self):
        """Return the states."""
        return self._states

    @states.setter
    def states(self, states):
        """Set the states."""
        if states is not None:
            if not isinstance(states, State):
                raise TypeError("Expecting states to be an instance of State.")
        self._states = states

    @property
    def actions(self):
        """Return the actions."""
        return self._actions

    @actions.setter
    def actions(self, actions):
        """Set the actions."""
        if not isinstance(actions, Action):
            raise TypeError("Expecting actions to be an instance of Action.")
        self._actions = actions

    @property
    def model(self):
        """Return the inner approximator / learning model."""
        return self._model

    @model.setter
    def model(self, model):
        """Set the inner approximator / learning model."""
        if model is not None and not isinstance(model, Approximator):
            # Try to wrap it with the corresponding Approximator
            if isinstance(model, Model):
                model = Approximator(inputs=self.states, outputs=self.actions, model=model)
                # preprocessors=self.preprocessors, postprocessors=self.postprocessors)
            # else:
            #     raise TypeError("Expecting the model to be an instance of Model.")
        self._model = model

    @property
    def rate(self):
        """Return the rate at which the policy operates."""
        return self._rate

    @rate.setter
    def rate(self, rate):
        """Set the rate at which the policy operates."""
        if not isinstance(rate, int):
            raise TypeError("Expecting the rate to be an integer.")
        self._rate = rate

    @property
    def input_size(self):
        """Return the policy input size."""
        return self.model.input_size

    @property
    def output_size(self):
        """Return the policy output size."""
        return self.model.output_size

    @property
    def input_shape(self):
        """Return the policy input shape."""
        return self.model.input_shape

    @property
    def output_shape(self):
        """Return the policy output shape."""
        return self.model.output_shape

    @property
    def input_dim(self):
        """Return the input dimension of the policy; i.e. len(input_shape)."""
        return self.model.input_dim

    @property
    def output_dim(self):
        """Return the output dimension of the policy; i.e. len(output_shape)."""
        return self.model.output_dim

    @property
    def num_parameters(self):
        """Return the total number of parameters"""
        return self.model.num_parameters

    ###########
    # Methods #
    ###########

    def _size(self, items):
        """Compute the size of the given argument :attr:`items`."""
        size = 0
        if not isinstance(items, (list, tuple)):
            items = [items]
        for item in items:
            if isinstance(item, (State, Action)):
                for element in item:
                    if element.is_discrete():
                        size += element.space[0].n
                    else:
                        size += element.total_size()
            elif isinstance(item, np.ndarray):
                size += item.size
            elif isinstance(item, torch.Tensor):
                size += item.numel()
            elif isinstance(item, int):
                size += item
        return size

    def is_deterministic(self):
        """
        Return True if the policy is deterministic; that is, given the same states result in the same actions.

        Returns:
            bool: True if the policy is deterministic
        """
        return self.model.is_deterministic()

    def is_probabilistic(self):
        """
        Return True if the policy is stochastic; that is, given the same states can result in different actions.

        Returns:
            bool: True if the policy is stochastic
        """
        return self.model.is_probabilistic()

    def is_parametric(self):
        """
        Return True if the policy is parametric.

        Returns:
            bool: True if the policy is parametric.
        """
        return self.model.is_parametric()

    def is_linear(self):
        """
        Return True if the policy is linear (wrt the parameters). This can be for instance useful for some learning
        algorithms (some only works on linear models).

        Returns:
            bool: True if it is a linear policy
        """
        return self.model.is_linear()

    def is_recurrent(self):
        """
        Return True if the policy is recurrent. This can be for instance useful for some learning algorithms which
        change their behavior when they deal with recurrent learning models.

        Returns:
            bool: True if it is a recurrent policy.
        """
        raise self.model.is_recurrent()

    def parameters(self):
        """
        Return an iterator over the learning model parameters.
        """
        if self.model is None:
            return []
        return self.model.parameters()

    def named_parameters(self):
        """
        Return an iterator over the learning model parameters; yielding both the name and the parameter itself.
        """
        if self.model is None:
            return []
        return self.model.named_parameters()

    def list_parameters(self):
        """
        Return the learning model parameters.
        """
        if self.model is None:
            return []
        return self.model.list_parameters()

    def hyperparameters(self):
        """
        Return an iterator over the learning model hyper-parameters.
        """
        if self.model is None:
            return []
        return self.model.hyperparameters()

    def named_hyperparameters(self):
        """
        Return an iterator over the learning model hyper-parameters; yielding both the name and the hyper-parameter
        itself.
        """
        if self.model is None:
            return []
        return self.model.named_hyperparameters()

    def list_hyperparameters(self):
        """
        Return the learning model hyper-parameters
        """
        if self.model is None:
            return None
        return self.model.list_hyperparameters()

    def get_vectorized_parameters(self, to_numpy=True):
        """Get the parameters in a vectorized form."""
        return self.model.get_vectorized_parameters(to_numpy=to_numpy)

    def set_vectorized_parameters(self, vector):
        """Set the vectorized parameters."""
        self.model.set_vectorized_parameters(vector=vector)

    def __convert_to_numpy(self, x, to_numpy=True):
        """Convert the given argument to a numpy array if specified."""
        if to_numpy and isinstance(x, torch.Tensor):
            if x.requires_grad:
                return x.detach().numpy()
            return x.numpy()
        return x

    def _predict(self, state, to_numpy=False, return_logits=True, set_output_data=False):
        """Inner prediction step."""
        if isinstance(self.model, Approximator):  # inner model is an approximator
            return self.model.predict(state, to_numpy=to_numpy, return_logits=return_logits,
                                      set_output_data=set_output_data)
        # inner model is a learning model
        return self.model.predict(state, to_numpy=to_numpy)

    def act(self, state=None, deterministic=True, to_numpy=True, return_logits=False, apply_action=True):
        """Perform the action given the state.

        Args:
            state (State): current state
            deterministic (bool): True by default. It can only be set to False, if the policy is stochastic.
            to_numpy (bool): If True, it will convert the data (torch.Tensors) to numpy arrays.
            return_logits (bool): If True, in the case of discrete outputs, it will return the logits.
            apply_action (bool): If True, it will call and execute the action.

        Returns:
            (list of) np.array / torch.Tensor: action data
        """
        # if we should predict
        if (self.cnt % self.rate) == 0:

            # if no input is given, take the provided inputs at the beginning
            if state is None:
                state = self.states

            # if the input is an instance of State, get the inner merged data.
            if isinstance(state, State):
                state = state.merged_data
                if len(state) == 1:
                    state = state[0]

            # go through each preprocessor
            for processor in self.preprocessors:
                state = processor(state)

            # predict the output using the inner model
            self.action_data = self._predict(state, to_numpy=False, return_logits=True, set_output_data=False)
            # if isinstance(self.model, Approximator):  # inner model is an approximator
            #     self.action_data = self.model.predict(state, to_numpy=False, return_logits=True,
            #                                           set_output_data=False)
            # else:  # inner model is a learning model
            #     self.action_data = self.model.predict(state, to_numpy=to_numpy)

            # go through each postprocessor
            for processor in self.postprocessors:
                self.action_data = processor(self.action_data)

            # set the action data

            # if action data is not a list, make it a list as we will iterate through it
            if not isinstance(self.action_data, list):
                self.action_data = [self.action_data]

            # go through each action and data
            for idx, (action, data) in enumerate(zip(self.actions, self.action_data)):
                if action.is_discrete():  # discrete action
                    if isinstance(data, np.ndarray):  # data action is a numpy array
                        discrete_data = np.array([np.argmax(data)])
                        action.data = discrete_data
                        if not return_logits:
                            self.action_data[idx] = discrete_data
                    elif isinstance(data, torch.Tensor):  # data action is a torch.Tensor
                        discrete_data = torch.argmax(data, dim=0, keepdim=True)
                        action.torch_data = discrete_data
                        if not return_logits:
                            self.action_data[idx] = self.__convert_to_numpy(discrete_data, to_numpy=to_numpy)
                        else:
                            self.action_data[idx] = self.__convert_to_numpy(data, to_numpy=to_numpy)
                    # elif isinstance(data, (float, int)):
                    #     discrete_data = np.argmax(data)
                    #     action.data = discrete_data
                    #     if not return_logits:
                    #         self.action_data[idx] = discrete_data
                    else:
                        raise TypeError(
                            "Expecting the `data` action to be a numpy array or torch.Tensor, instead got: "
                            "{}".format(type(data)))
                else:  # continuous action
                    if isinstance(data, np.ndarray):
                        action.data = data
                    elif isinstance(data, torch.Tensor):
                        action.torch_data = data
                        self.action_data[idx] = self.__convert_to_numpy(data, to_numpy=to_numpy)
                    # elif isinstance(data, (float, int)):
                    #     pass
                    else:
                        raise TypeError(
                            "Expecting `data` to be a numpy array or torch.Tensor, instead got: "
                            "{}".format(type(data)))

            # if action_data is a list and has one element, return just that element
            if isinstance(self.action_data, list) and len(self.action_data) == 1:
                self.action_data = self.action_data[0]

        # apply action
        if apply_action:
            self.actions()

        # increment tick counter
        self.cnt += 1

        # return the action data
        return self.action_data

    def sample(self, state=None):
        """
        Given the state, sample from the policy. This only works if the inner model of the policy is stochastic.

        Args:
            state (State, array, tensor, None): current state

        Returns:
            array: sample
        """
        pass

    def train(self, mode=True):
        """
        Set the policy to train mode.

        Args:
            mode (bool): if True, set the policy in train mode.
        """
        self.train_mode = mode

    def reset(self, reset_processors=False, *args, **kwargs):
        """
        Reset the policy.
        """
        for processor in self.preprocessors:
            processor.reset()
        for processor in self.postprocessors:
            processor.reset()
        self.model.reset()

    def save(self, filename):
        """
        Save the policy in the given filename.

        Args:
            filename (str): file to save the policy into
        """
        # self.model.save(filename)
        pickle.dump(self, open(filename, 'wb'))

    @staticmethod
    def load(filename):
        """
        Load the policy from the given file.

        Args:
            filename (str): file to load the policy from

        Returns:
            Policy: the policy
        """
        # self.model.load(filename)
        return pickle.load(open(filename, 'rb'))

    #############
    # Operators #
    #############

    def __call__(self, state=None, deterministic=True, to_numpy=True, return_logits=False, apply_action=True):
        """Perform the action given the state.

        Args:
            state (State): current state
            deterministic (bool): True by default. It can only be set to False, if the policy is stochastic.
            to_numpy (bool): If True, it will convert the data (torch.Tensors) to numpy arrays.
            return_logits (bool): If True, in the case of discrete outputs, it will return the logits.
            apply_action (bool): If True, it will call and execute the action.

        Returns:
            Action: action
        """
        return self.act(*args, **kwargs)

    def __repr__(self):
        """Return representation of python object."""
        if self.__class__.__name__ == 'Policy':
            if self.model is not None:
                return "{}({})".format(self.__class__.__name__, self.model.__str__())
        return self.__class__.__name__

    def __str__(self):
        """Return string describing the policy."""
        if self.__class__.__name__ == 'Policy':
            if self.model is not None:
                return "{}({})".format(self.__class__.__name__, self.model.__str__())
        return self.__class__.__name__