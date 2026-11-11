"""V11 policy-value network + PUCT MCTS (V11.2 Kaggle bundle).

The 19-plane encoder, the 4672-action layout and ``outcome`` are the identical ``v20`` code;
only the two-player value head, the -0.1 draw utility and the Max-N search are V11-specific.

Imports stay lightweight: ``torch`` is only needed when ``policy.load_v11_policy`` runs.
"""
