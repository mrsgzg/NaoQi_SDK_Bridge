"""ALMotion / ALRobotPosture wrapper for the nao_bridge server.

All joint angles in this service's public API are in *degrees* (NAOqi's
native unit is radians) because degrees are easier for an LLM/VLM agent
or a human operator to reason about.
"""

from __future__ import print_function

import math


try:
    _STRING_TYPES = (str, unicode)  # noqa: F821 (py2 only)
except NameError:
    _STRING_TYPES = (str,)


def _to_radians(value):
    if isinstance(value, list):
        return [_to_radians(v) for v in value]
    return math.radians(value)


def _to_degrees(value):
    if isinstance(value, list):
        return [_to_degrees(v) for v in value]
    return math.degrees(value)


# Standard NAO H25 body joint names (25 actuated joints). Used by the mock
# service, and as documentation of what "Body" resolves to on a real robot.
NAO_BODY_JOINTS = [
    "HeadYaw", "HeadPitch",
    "LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw", "LHand",
    "LHipYawPitch", "LHipRoll", "LHipPitch", "LKneePitch", "LAnklePitch", "LAnkleRoll",
    "RHipYawPitch", "RHipRoll", "RHipPitch", "RKneePitch", "RAnklePitch", "RAnkleRoll",
    "RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw", "RHand",
]


class MotionService(object):
    """Wraps ALMotion + ALRobotPosture proxies."""

    def __init__(self, proxies):
        self._motion = proxies["ALMotion"]
        self._posture = proxies["ALRobotPosture"]

    def wake_up(self):
        self._motion.wakeUp()
        return {"awake": True}

    def rest(self):
        self._motion.rest()
        return {"awake": False}

    def is_awake(self):
        return {"awake": bool(self._motion.robotIsWakeUp())}

    def get_posture(self):
        return {"posture": self._posture.getPostureFamily()}

    def go_to_posture(self, posture_name, speed=0.5):
        ok = self._posture.goToPosture(posture_name, speed)
        return {"ok": bool(ok)}

    def list_joints(self, chain="Body"):
        return {"joints": list(self._motion.getBodyNames(chain))}

    def get_joint_angles(self, joints="Body", use_sensors=True):
        if isinstance(joints, _STRING_TYPES):
            names = list(self._motion.getBodyNames(joints))
        else:
            names = list(joints)
        angles = self._motion.getAngles(joints, bool(use_sensors))
        return {"joints": names, "angles_deg": _to_degrees(list(angles))}

    def set_joint_angles(self, joints, angles_deg, speed=0.1):
        """Move toward target angles at up to `speed` (fraction of max joint speed)."""
        self._motion.setAngles(joints, _to_radians(angles_deg), speed)
        return {"ok": True}

    def move_joints(self, joints, angles_deg, durations_sec, absolute=True):
        """Time-controlled motion via ALMotion.angleInterpolation (blocking).

        `angles_deg` / `durations_sec` are either a single list (one
        waypoint per joint) or a list of lists (multiple waypoints per
        joint), matching NAOqi's angleInterpolation signature.
        """
        self._motion.angleInterpolation(joints, _to_radians(angles_deg), durations_sec, bool(absolute))
        return {"ok": True}

    def set_stiffness(self, joints, value):
        self._motion.setStiffnesses(joints, value)
        return {"ok": True}

    def walk_to(self, x, y, theta=0.0):
        self._motion.moveTo(x, y, theta)
        return {"ok": True}

    def stop_walk(self):
        self._motion.stopMove()
        return {"ok": True}


class MockMotionService(object):
    """In-memory stand-in for MotionService - lets you develop the LLM/VLM
    side of the stack without a robot connected."""

    def __init__(self):
        self._awake = False
        self._posture = "Crouch"
        self._angles_deg = dict((name, 0.0) for name in NAO_BODY_JOINTS)

    def wake_up(self):
        self._awake = True
        self._posture = "Stand"
        return {"awake": True}

    def rest(self):
        self._awake = False
        self._posture = "Crouch"
        return {"awake": False}

    def is_awake(self):
        return {"awake": self._awake}

    def get_posture(self):
        return {"posture": self._posture}

    def go_to_posture(self, posture_name, speed=0.5):
        self._posture = posture_name
        return {"ok": True}

    def list_joints(self, chain="Body"):
        return {"joints": list(NAO_BODY_JOINTS)}

    def _resolve_names(self, joints):
        if joints in ("Body", "JointActuators", "Joints"):
            return list(NAO_BODY_JOINTS)
        if isinstance(joints, list):
            return list(joints)
        return [joints]

    def get_joint_angles(self, joints="Body", use_sensors=True):
        names = self._resolve_names(joints)
        return {"joints": names, "angles_deg": [self._angles_deg.get(n, 0.0) for n in names]}

    def set_joint_angles(self, joints, angles_deg, speed=0.1):
        names = self._resolve_names(joints)
        values = angles_deg if isinstance(angles_deg, list) else [angles_deg]
        for name, value in zip(names, values):
            self._angles_deg[name] = value
        return {"ok": True}

    def move_joints(self, joints, angles_deg, durations_sec, absolute=True):
        names = self._resolve_names(joints)
        values = angles_deg if isinstance(angles_deg, list) else [angles_deg]
        final_values = [v[-1] if isinstance(v, list) else v for v in values]
        for name, value in zip(names, final_values):
            self._angles_deg[name] = value
        return {"ok": True}

    def set_stiffness(self, joints, value):
        return {"ok": True}

    def walk_to(self, x, y, theta=0.0):
        return {"ok": True, "moved": {"x": x, "y": y, "theta": theta}}

    def stop_walk(self):
        return {"ok": True}
