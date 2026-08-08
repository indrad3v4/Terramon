"""terramon.agents — AgentCore: Generative-Agents brain for every creature.

Memory stream + reflection + daily planning + world GameMaster, adapted
from Park et al. (2023) to Terramon's constraints: lazy offline ticks,
LLM budget of a few calls per player session, deterministic templates in
the routine path and LLM only at key points. All modules are pure stdlib
and offline-testable (llm_call is always injected, never imported).
"""
