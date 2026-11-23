"""Your controller.

Every controller tick (50 times per second) the harness calls ``update`` with
``observations`` (what the aircraft can see right now) and ``dt`` (seconds since
the last call). You return a ``Command`` saying where to put the control
surfaces.

Useful things:
    observations.t               sim time (s)
    observations.ref.theta       the pitch angle you're asked to hold (rad)
    observations.sensors.theta   measured pitch angle (rad)
    observations.sensors.q       measured pitch rate (rad/s)
    print(observations)          shows everything available in this chapter

    Command(elevator=...)        elevator deflection (rad)
                                 POSITIVE elevator = trailing edge down = nose DOWN

    DEG                          5 * DEG is 5 degrees in radians;
                                 angle / DEG converts radians to degrees
    self.log("name", value)      plot any value live in the viewer
"""

from flightlab import DEG, Command, ControllerBase


class Controller(ControllerBase):
    def reset(self, info):
        # Called once before each run. Set up any variables you need here.
        pass

    def update(self, observations, dt):
        # Your control law goes here.
        return Command(elevator=0 * DEG)
