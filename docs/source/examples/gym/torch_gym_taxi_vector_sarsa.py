import gym

import torch

# import the skrl components to build the RL system
from skrl.agents.torch.sarsa import SARSA, SARSA_DEFAULT_CONFIG
from skrl.envs.torch import wrap_env
from skrl.models.torch import Model, TabularMixin
from skrl.trainers.torch import SequentialTrainer
from skrl.utils import set_seed


# seed for reproducibility
set_seed()  # e.g. `set_seed(42)` for fixed seed


# define model (tabular model) using mixin
class EpilonGreedyPolicy(TabularMixin, Model):
    def __init__(self, observation_space, action_space, device, num_envs=1, epsilon=0.1):
        Model.__init__(self, observation_space, action_space, device)
        TabularMixin.__init__(self, num_envs)

        self.epsilon = epsilon
        self.q_table = torch.ones((num_envs, self.num_observations, self.num_actions),
                                  dtype=torch.float32, device=self.device)

    def compute(self, inputs, role):
        actions = torch.argmax(self.q_table[torch.arange(self.num_envs).view(-1, 1), inputs["states"]],
                               dim=-1, keepdim=True).view(-1,1)

        # choose random actions for exploration according to epsilon
        indexes = (torch.rand(inputs["states"].shape[0], device=self.device) < self.epsilon).nonzero().view(-1)
        if indexes.numel():
            actions[indexes] = torch.randint(self.num_actions, (indexes.numel(), 1), device=self.device)
        return actions, {}


# load and wrap the gym environment.
# note: the environment version may change depending on the gym version
try:
    env = gym.vector.make("Taxi-v3", num_envs=10, asynchronous=False)
except gym.error.DeprecatedEnv as e:
    env_id = [spec.id for spec in gym.envs.registry.all() if spec.id.startswith("Taxi-v")][0]
    print("Taxi-v3 not found. Trying {}".format(env_id))
    env = gym.vector.make(env_id, num_envs=10, asynchronous=False)
env = wrap_env(env)

device = env.device


# instantiate the agent's model (table)
# SARSA requires 1 model, visit its documentation for more details
# https://skrl.readthedocs.io/en/latest/api/agents/sarsa.html#models
models = {}
models["policy"] = EpilonGreedyPolicy(env.observation_space, env.action_space, device, num_envs=env.num_envs, epsilon=0.1)


# configure and instantiate the agent (visit its documentation to see all the options)
# https://skrl.readthedocs.io/en/latest/api/agents/sarsa.html#configuration-and-hyperparameters
cfg = SARSA_DEFAULT_CONFIG.copy()
cfg["discount_factor"] = 0.999
cfg["alpha"] = 0.4
# logging to TensorBoard and write checkpoints (in timesteps)
cfg["experiment"]["write_interval"] = 1600
cfg["experiment"]["checkpoint_interval"] = 8000
cfg["experiment"]["directory"] = "runs/torch/Taxi"

agent = SARSA(models=models,
              memory=None,
              cfg=cfg,
              observation_space=env.observation_space,
              action_space=env.action_space,
              device=device)


# configure and instantiate the RL trainer
cfg_trainer = {"timesteps": 80000, "headless": True}
trainer = SequentialTrainer(cfg=cfg_trainer, env=env, agents=[agent])

# start training
trainer.train()