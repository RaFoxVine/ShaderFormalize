# Restricted IEEE HLSL examples

All cases use empty schema 2 constraints and the profile `binary32-rne-preserve-subnormals-separate-ops-v1`. Inputs range over all binary32 storage values, including infinities, NaNs, signed zeros, and subnormals. Output equality is Lean structural equality of the complete stored value.

The normal, arithmetic, and bit-roundtrip pairs are positive controls. Reassociation, signed-zero merging, and replacing NaN self-comparison with `true` are intentional false equivalences and must finish as `UNPROVED`. `gpu_profile_matched` remains `false`: these checks do not establish agreement with a GPU compiler or hardware mode.
