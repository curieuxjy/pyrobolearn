# -*- coding: utf-8 -*-
#!/usr/bin/env python
"""Load the PR2 robot.
"""

from itertools import count
from pyrobolearn.simulators import Bullet
from pyrobolearn.worlds import BasicWorld
from pyrobolearn.robots import PR2

# Create simulator
sim = Bullet()

# create world
world = BasicWorld(sim)

# create robot
robot = PR2(sim)

# print information about the robot
robot.print_info()

# Position control using sliders
# robot.add_joint_slider()

# run simulator
for _ in count():
    # robot.update_joint_slider()
    world.step(sleep_dt=1./240)
