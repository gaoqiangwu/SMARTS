import math
from itertools import cycle

import pytest
import numpy as np

from smarts.core import seed
from smarts.core.smarts import SMARTS
from smarts.core.sumo_traffic_simulation import SumoTrafficSimulation
from smarts.core.scenario import Scenario, Mission, Start, EndlessGoal
from smarts.core.coordinates import Heading
from smarts.core.agent_interface import AgentInterface, ActionSpaceType


@pytest.fixture
def scenarios():
    mission = Mission(
        start=Start((71.65, 63.78), Heading(math.pi * 0.91)), goal=EndlessGoal()
    )
    scenario = Scenario(
        scenario_root="scenarios/loop",
        route="basic.rou.xml",
        missions={"Agent-007": mission},
    )
    return cycle([scenario])


@pytest.fixture
def smarts():
    buddha = AgentInterface(
        max_episode_steps=1000, neighborhood_vehicles=True, action=ActionSpaceType.Lane,
    )
    smarts = SMARTS(
        agent_interfaces={"Agent-007": buddha},
        traffic_sim=SumoTrafficSimulation(headless=True),
        envision=None,
    )

    yield smarts
    smarts.destroy()


def test_only_agents_reset_if_scenario_does_not_change(smarts, scenarios):
    """Upon reset, if the scenario remains the same then the agent should be reset
    ("teleported" somewhere else) but the social vehicles should continue as if
    nothing happened.
    """

    def ego_vehicle_pose(agent_obs):
        state = agent_obs.ego_vehicle_state
        start = tuple(state.position) + (state.heading,)
        return np.array(start)

    def neighborhood_vehicle_poses(agent_obs):
        neighborhood_vehicles = agent_obs.neighborhood_vehicle_states
        states = sorted(neighborhood_vehicles, key=lambda s: s.id)
        starts = [tuple(s.position) + (s.heading,) for s in states]
        if not starts:
            return np.array([])

        return np.stack(starts)

    scenario = next(scenarios)

    seed(42)
    obs = smarts.reset(scenario)

    agent_obs = obs["Agent-007"]
    ego_start_pose = ego_vehicle_pose(agent_obs)
    sv_start_poses = neighborhood_vehicle_poses(agent_obs)

    for _ in range(50):
        smarts.step({"Agent-007": "keep_lane"})

    seed(42)
    obs = smarts.reset(scenario)

    agent_obs = obs["Agent-007"]
    agent_pose_reset_to_initial = np.all(
        np.isclose(ego_start_pose, ego_vehicle_pose(agent_obs))
    )

    sv_poses = neighborhood_vehicle_poses(agent_obs)
    sv_poses_reset_to_initial = sv_poses.shape == sv_start_poses.shape
    if sv_poses_reset_to_initial:
        sv_poses_reset_to_initial = np.all(np.isclose(sv_poses, sv_start_poses))

    assert (
        agent_pose_reset_to_initial
    ), "Upon reset the agent goes back to the starting position"
    assert sv_poses_reset_to_initial, "Upon reset social vehicles are unaffected"
