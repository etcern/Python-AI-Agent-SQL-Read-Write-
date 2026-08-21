"""Agent registry - all available agents are automatiacally displayed here.
Ref: https://docs.python.org/3/library/importlib.html#importlib.import_module
"""
import importlib
import os
import pkgutil
from agents.base import BaseAgent

AGENTS = {}


_pkg_dir = os.path.dirname(__file__)
for _, module_name, _ in pkgutil.iter_modules([_pkg_dir]):
    if module_name == "base":
        continue
    module = importlib.import_module(f"agents.{module_name}")
    for attr_name in dir(module):
        obj = getattr(module,attr_name)
        if (isinstance(obj, type)
                and issubclass(obj, BaseAgent)
                and obj is not BaseAgent):
            AGENTS[obj.AGENT_NAME] = obj
